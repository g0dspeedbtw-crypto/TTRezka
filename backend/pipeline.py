"""Background job pipeline orchestrator for local files and remote YouTube/Twitch VOD links."""
import json
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import JOBS_DIR
from backend.highlights import _make_clip_title, find_highlights
from backend.remote import (
    download_clip_segment,
    fetch_remote_transcript,
    find_remote_highlights,
)
from backend.renderer import probe_video, render_clip
from backend.transcriber import extract_audio_wav, transcribe_russian

_LOCK = threading.Lock()
_JOBS: Dict[str, Dict[str, Any]] = {}


def _job_dir(job_id: str) -> Path:
    d = JOBS_DIR / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_path(job_id: str) -> Path:
    return _job_dir(job_id) / "state.json"


def _save_job(job: Dict[str, Any]) -> None:
    path = _state_path(job["job_id"])
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_existing_jobs() -> None:
    """Restore saved jobs from disk on server startup."""
    with _LOCK:
        for state_file in sorted(
            JOBS_DIR.glob("*/state.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                jid = data.get("job_id")
                if not jid:
                    continue
                if data.get("status") == "processing":
                    data["status"] = "failed"
                    data["error"] = "Обработка была прервана перезапуском приложения"
                _JOBS[jid] = data
            except Exception:
                continue


def create_job(
    job_id: str,
    original_filename: str,
    video_path: Optional[Path],
    video_meta: Dict[str, Any],
    source_type: str = "file",
    remote_url: Optional[str] = None,
    remote_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    job = {
        "job_id": job_id,
        "created_at": int(time.time()),
        "source_type": source_type,
        "remote_url": remote_url,
        "original_filename": original_filename,
        "video_path": str(video_path) if video_path else None,
        "video_meta": video_meta,
        "status": "uploaded",
        "stage": "uploaded",
        "progress": 0,
        "message": (
            "Ссылка проанализирована и готова к ИИ-нарезке без скачивания всего видео"
            if source_type == "url"
            else "Видео загружено и готово к нарезке"
        ),
        "error": None,
        "options": {},
        "clips": [],
        "words_count": 0,
    }
    if remote_meta is not None:
        # Save full remote metadata (including heatmap/caption track) separately to keep state.json light
        (_job_dir(job_id) / "remote_meta.json").write_text(
            json.dumps(remote_meta, ensure_ascii=False),
            encoding="utf-8",
        )
    with _LOCK:
        _JOBS[job_id] = job
        _save_job(job)
    return job


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job:
            return json.loads(json.dumps(job))
    return None


def list_jobs(limit: int = 15) -> List[Dict[str, Any]]:
    with _LOCK:
        items = sorted(_JOBS.values(), key=lambda x: x.get("created_at", 0), reverse=True)[:limit]
        return [json.loads(json.dumps(x)) for x in items]


def _update_job(job_id: str, **fields: Any) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job.update(fields)
        _save_job(job)


def start_processing(job_id: str, options: Dict[str, Any]) -> None:
    job = get_job(job_id)
    if not job:
        raise ValueError("Job not found")

    is_url = job.get("source_type") == "url"
    _update_job(
        job_id,
        status="processing",
        stage="transcribing" if is_url else "extracting_audio",
        progress=3,
        message=(
            "Получение транскрипта и данных стрима без скачивания видео..."
            if is_url
            else "Извлечение аудиодорожки из видео..."
        ),
        error=None,
        options=options,
        clips=[],
    )

    target_fn = _run_remote_pipeline if is_url else _run_local_pipeline
    thread = threading.Thread(target=target_fn, args=(job_id, options), daemon=True)
    thread.start()


def _run_remote_pipeline(job_id: str, options: Dict[str, Any]) -> None:
    """
    Zero-full-download pipeline for YouTube videos & Twitch/YouTube past streams:
    1. Fetch lightweight captions + heatmap (KB, not GB)
    2. AI-score and select top N highlights across the whole stream in ~2s
    3. Surgically download ONLY the chosen 20-55s segments
    4. Run fast local Whisper on each short clip for exact word timestamps & render 9:16
    """
    try:
        job = get_job(job_id)
        if not job:
            return

        jdir = _job_dir(job_id)
        remote_url = job["remote_url"]
        remote_meta_path = jdir / "remote_meta.json"
        remote_meta = json.loads(remote_meta_path.read_text(encoding="utf-8"))

        # Stage 1: Fetch lightweight captions without downloading video (5% -> 22%)
        _update_job(
            job_id,
            stage="transcribing",
            progress=10,
            message="Загрузка субтитров/транскрипта по ссылке (без скачивания видео)...",
        )
        segments, words = [], []
        try:
            segments, words = fetch_remote_transcript(remote_meta.get("caption_track"))
        except Exception:
            segments, words = [], []

        _update_job(
            job_id,
            words_count=len(words),
            progress=22,
            message=(
                f"Получен транскрипт ({len(words)} слов) без скачивания видео"
                if words
                else "Субтитры на платформе не найдены — анализ по карте пересмотров и структуре..."
            ),
        )

        # Stage 2: Analyze full video/stream & pick top highlights (22% -> 40%)
        clip_count = int(options.get("clip_count", 5))
        min_dur = float(options.get("min_duration", 20))
        max_dur = float(options.get("max_duration", 55))

        def on_hl(frac: float, msg: str) -> None:
            _update_job(job_id, stage="analyzing", progress=int(22 + frac * 18), message=msg)

        highlights = find_remote_highlights(
            remote_meta=remote_meta,
            segments=segments,
            words=words,
            clip_count=clip_count,
            min_duration=min_dur,
            max_duration=max_dur,
            progress_cb=on_hl,
        )

        # Stage 3: Surgically download ONLY each selected clip + Whisper + 9:16 render (40% -> 100%)
        whisper_model = options.get("whisper_model", "small")
        style_id = options.get("subtitle_style", "hormozi")
        font_id = options.get("font_id", "montserrat")
        font_size = options.get("font_size", "medium")
        crop_mode = options.get("crop_mode", "fill")
        position = options.get("position", "lower_third")
        uppercase = options.get("uppercase", None)

        rendered_clips: List[Dict[str, Any]] = []
        n_total = max(1, len(highlights))
        total_recognized_words = len(words)

        for idx, hl in enumerate(highlights):
            clip_id = hl["id"]
            base_pct = 40 + (idx / n_total) * 58
            step_span = 58 / n_total

            _update_job(
                job_id,
                stage="rendering",
                progress=int(base_pct),
                message=f"Клип {idx + 1}/{n_total}: загрузка только фрагмента ({int(hl['duration'])} сек)...",
            )

            raw_seg_path = jdir / f"raw_{clip_id}.mp4"
            raw_seg_path = download_clip_segment(
                url=remote_url,
                start=hl["start"],
                end=hl["end"],
                output_mp4=raw_seg_path,
            )
            seg_meta = probe_video(raw_seg_path)
            seg_dur = float(seg_meta.get("duration") or hl["duration"])

            # Run fast local Whisper on ONLY this short 20-55s clip for razor-sharp Russian word timing!
            _update_job(
                job_id,
                stage="rendering",
                progress=int(base_pct + step_span * 0.35),
                message=f"Клип {idx + 1}/{n_total}: точные русские авто-субтитры (Whisper)...",
            )
            clip_wav = jdir / f"raw_{clip_id}.wav"
            extract_audio_wav(raw_seg_path, clip_wav)
            clip_segs, clip_words = transcribe_russian(
                clip_wav,
                total_duration=seg_dur,
                model_size=whisper_model,
            )
            (jdir / f"{clip_id}_words.json").write_text(
                json.dumps({"segments": clip_segs, "words": clip_words}, ensure_ascii=False),
                encoding="utf-8",
            )
            if not words:
                total_recognized_words += len(clip_words)

            # Render final 9:16 MP4 with TikTok subtitles
            _update_job(
                job_id,
                stage="rendering",
                progress=int(base_pct + step_span * 0.68),
                message=f"Клип {idx + 1}/{n_total}: рендер 9:16 + вшивание субтитров...",
            )
            out_mp4 = jdir / f"{clip_id}.mp4"
            out_thumb = jdir / f"{clip_id}.jpg"
            render_clip(
                source_video=raw_seg_path,
                output_mp4=out_mp4,
                thumb_jpg=out_thumb,
                clip_start=0.0,
                clip_end=seg_dur,
                words=clip_words,
                style_id=style_id,
                font_id=font_id,
                font_size=font_size,
                crop_mode=crop_mode,
                position=position,
                uppercase=uppercase,
            )

            transcript_txt = " ".join(s["text"] for s in clip_segs).strip() or hl.get("transcript", "")
            hl_out = dict(hl)
            hl_out["transcript"] = transcript_txt
            if not hl.get("transcript") and transcript_txt:
                hl_out["title"] = _make_clip_title(transcript_txt, idx + 1)
            hl_out["raw_segment_path"] = str(raw_seg_path)
            hl_out["raw_segment_duration"] = round(seg_dur, 2)
            hl_out["style_id"] = style_id
            hl_out["font_id"] = font_id
            hl_out["font_size"] = font_size
            hl_out["crop_mode"] = crop_mode
            hl_out["position"] = position
            hl_out["version"] = int(time.time())
            hl_out["file_size_mb"] = round(out_mp4.stat().st_size / (1024 * 1024), 2)
            rendered_clips.append(hl_out)

            _update_job(job_id, clips=rendered_clips, words_count=total_recognized_words)

        _update_job(
            job_id,
            status="completed",
            stage="completed",
            progress=100,
            message=f"Готово! Создано {len(rendered_clips)} клипов 9:16 без скачивания всего видео.",
            clips=rendered_clips,
            words_count=total_recognized_words,
        )
    except Exception as exc:
        traceback.print_exc()
        _update_job(
            job_id,
            status="failed",
            stage="failed",
            error=str(exc),
            message=f"Ошибка обработки ссылки: {exc}",
        )


def _run_local_pipeline(job_id: str, options: Dict[str, Any]) -> None:
    try:
        job = get_job(job_id)
        if not job:
            return

        video_path = Path(job["video_path"])
        total_duration = float(job["video_meta"].get("duration") or 0)
        jdir = _job_dir(job_id)
        wav_path = jdir / "audio.wav"
        words_path = jdir / "words.json"

        # Stage 1: Extract audio (0% -> 10%)
        if not wav_path.exists():
            _update_job(
                job_id,
                stage="extracting_audio",
                progress=5,
                message="Извлечение аудиодорожки (16 кГц)...",
            )
            extract_audio_wav(video_path, wav_path)

        # Stage 2: Russian Speech Recognition via faster-whisper (10% -> 52%)
        whisper_model = options.get("whisper_model", "small")
        _update_job(
            job_id,
            stage="transcribing",
            progress=10,
            message=f"Запуск локального Whisper ({whisper_model}) для русского языка...",
        )

        def on_transcribe(frac: float, msg: str) -> None:
            pct = int(10 + frac * 42)
            _update_job(job_id, stage="transcribing", progress=pct, message=msg)

        segments, words = transcribe_russian(
            wav_path,
            total_duration=total_duration,
            model_size=whisper_model,
            progress_cb=on_transcribe,
        )
        words_path.write_text(
            json.dumps({"segments": segments, "words": words}, ensure_ascii=False),
            encoding="utf-8",
        )
        _update_job(job_id, words_count=len(words))

        # Stage 3: Local Highlight Detection (52% -> 68%)
        clip_count = int(options.get("clip_count", 5))
        min_dur = float(options.get("min_duration", 20))
        max_dur = float(options.get("max_duration", 55))

        def on_highlights(frac: float, msg: str) -> None:
            pct = int(52 + frac * 16)
            _update_job(job_id, stage="analyzing", progress=pct, message=msg)

        highlights = find_highlights(
            video_path=video_path,
            wav_path=wav_path,
            total_duration=total_duration,
            segments=segments,
            words=words,
            clip_count=clip_count,
            min_duration=min_dur,
            max_duration=max_dur,
            progress_cb=on_highlights,
        )

        # Stage 4: Render 9:16 Clips with Styled Subtitles (68% -> 100%)
        style_id = options.get("subtitle_style", "hormozi")
        font_id = options.get("font_id", "montserrat")
        font_size = options.get("font_size", "medium")
        crop_mode = options.get("crop_mode", "fill")
        position = options.get("position", "lower_third")
        uppercase = options.get("uppercase", None)

        rendered_clips: List[Dict[str, Any]] = []
        n_total = max(1, len(highlights))
        for idx, hl in enumerate(highlights):
            pct = int(68 + (idx / n_total) * 30)
            _update_job(
                job_id,
                stage="rendering",
                progress=pct,
                message=f"Рендеринг клипа {idx + 1} из {n_total} (9:16 + авто-субтитры)...",
            )
            clip_id = hl["id"]
            out_mp4 = jdir / f"{clip_id}.mp4"
            out_thumb = jdir / f"{clip_id}.jpg"

            render_clip(
                source_video=video_path,
                output_mp4=out_mp4,
                thumb_jpg=out_thumb,
                clip_start=hl["start"],
                clip_end=hl["end"],
                words=words,
                style_id=style_id,
                font_id=font_id,
                font_size=font_size,
                crop_mode=crop_mode,
                position=position,
                uppercase=uppercase,
            )

            hl_out = dict(hl)
            hl_out["style_id"] = style_id
            hl_out["font_id"] = font_id
            hl_out["font_size"] = font_size
            hl_out["crop_mode"] = crop_mode
            hl_out["position"] = position
            hl_out["version"] = int(time.time())
            hl_out["file_size_mb"] = round(out_mp4.stat().st_size / (1024 * 1024), 2)
            rendered_clips.append(hl_out)
            _update_job(job_id, clips=rendered_clips)

        _update_job(
            job_id,
            status="completed",
            stage="completed",
            progress=100,
            message=f"Готово! Создано {len(rendered_clips)} клипов 9:16 с субтитрами.",
            clips=rendered_clips,
        )
    except Exception as exc:
        traceback.print_exc()
        _update_job(
            job_id,
            status="failed",
            stage="failed",
            error=str(exc),
            message=f"Ошибка обработки: {exc}",
        )


def rerender_single_clip(
    job_id: str,
    clip_id: str,
    style_id: str,
    font_id: str,
    font_size: str,
    crop_mode: str,
    position: str,
    uppercase: Optional[bool] = None,
) -> Dict[str, Any]:
    """Re-render a single clip with updated subtitle style/font/crop without re-transcribing."""
    job = get_job(job_id)
    if not job:
        raise ValueError("Проект не найден")

    jdir = _job_dir(job_id)
    target_clip = next((c for c in job.get("clips", []) if c["id"] == clip_id), None)
    if not target_clip:
        raise ValueError("Клип не найден")

    out_mp4 = jdir / f"{clip_id}.mp4"
    out_thumb = jdir / f"{clip_id}.jpg"

    if job.get("source_type") == "url":
        raw_seg = Path(target_clip.get("raw_segment_path") or (jdir / f"raw_{clip_id}.mp4"))
        clip_words_path = jdir / f"{clip_id}_words.json"
        if not raw_seg.exists() or not clip_words_path.exists():
            raise ValueError("Исходный фрагмент клипа не найден")
        words = json.loads(clip_words_path.read_text(encoding="utf-8")).get("words", [])
        seg_dur = float(target_clip.get("raw_segment_duration") or target_clip["duration"])
        render_clip(
            source_video=raw_seg,
            output_mp4=out_mp4,
            thumb_jpg=out_thumb,
            clip_start=0.0,
            clip_end=seg_dur,
            words=words,
            style_id=style_id,
            font_id=font_id,
            font_size=font_size,
            crop_mode=crop_mode,
            position=position,
            uppercase=uppercase,
        )
    else:
        words_path = jdir / "words.json"
        if not words_path.exists():
            raise ValueError("Таймкоды субтитров не найдены")
        words = json.loads(words_path.read_text(encoding="utf-8")).get("words", [])
        video_path = Path(job["video_path"])
        render_clip(
            source_video=video_path,
            output_mp4=out_mp4,
            thumb_jpg=out_thumb,
            clip_start=target_clip["start"],
            clip_end=target_clip["end"],
            words=words,
            style_id=style_id,
            font_id=font_id,
            font_size=font_size,
            crop_mode=crop_mode,
            position=position,
            uppercase=uppercase,
        )

    updated_clip: Dict[str, Any] = {}
    with _LOCK:
        live_job = _JOBS[job_id]
        for c in live_job["clips"]:
            if c["id"] == clip_id:
                c["style_id"] = style_id
                c["font_id"] = font_id
                c["font_size"] = font_size
                c["crop_mode"] = crop_mode
                c["position"] = position
                c["version"] = int(time.time())
                c["file_size_mb"] = round(out_mp4.stat().st_size / (1024 * 1024), 2)
                updated_clip = dict(c)
                break
        _save_job(live_job)

    return updated_clip
