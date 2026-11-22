"""Background job pipeline orchestrator for local files and remote YouTube/Twitch VOD links."""
import json
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.ai_director import find_funny_moments_gemini, find_funny_moments_ollama
from backend.config import AVATARS_DIR, JOBS_DIR, MUSIC_DIR, load_settings
from backend.hardware import get_hardware_info
from backend.highlights import (
    _find_audio_peak_times,
    _make_clip_title,
    compute_audio_features,
    find_highlights,
)
from backend.ollama_ranker import enhance_highlights_with_ollama
from backend.remote import (
    download_clip_segment,
    fetch_remote_transcript,
    find_remote_highlights,
)
from backend.renderer import probe_video, render_clip
from backend.transcriber import extract_audio_wav, transcribe_russian
from backend.twitch_chat import generate_tiktok_caption

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


def _resolve_music_path(bg_music_id: Optional[str]) -> Optional[Path]:
    if not bg_music_id:
        return None
    p = MUSIC_DIR / Path(bg_music_id).name
    return p if p.exists() else None


def _resolve_avatar_path(avatar_id: Optional[str]) -> Optional[Path]:
    if not avatar_id:
        return None
    p = AVATARS_DIR / Path(avatar_id).name
    return p if p.exists() else None


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

    # Preserve previously shown clip ranges if user clicked "Shuffle" so we pick different moments!
    prev_ranges = []
    if int(options.get("shuffle_seed") or 0) > 0:
        for c in job.get("clips") or []:
            if "start" in c and "end" in c:
                prev_ranges.append((float(c["start"]), float(c["end"])))
    options = dict(options)
    options["_exclude_ranges"] = prev_ranges

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
        ai_notice=None,
        options=options,
        clips=[],
    )

    target_fn = _run_remote_pipeline if is_url else _run_local_pipeline
    thread = threading.Thread(target=target_fn, args=(job_id, options), daemon=True)
    thread.start()


def _extract_render_kwargs(options: Dict[str, Any], hook_title: str) -> Dict[str, Any]:
    show_hook = bool(options.get("show_hook_banner", True))
    use_photo = bool(options.get("use_webcam_photo", False))
    return {
        "style_id": options.get("subtitle_style", "hormozi"),
        "font_id": options.get("font_id", "montserrat"),
        "font_size": options.get("font_size", "medium"),
        "crop_mode": options.get("crop_mode", "fill"),
        "position": options.get("position", "lower_third"),
        "uppercase": options.get("uppercase", None),
        "enable_subtitles": bool(options.get("enable_subtitles", True)),
        "webcam_corner": options.get("webcam_corner", "bottom_left"),
        "webcam_size": float(options.get("webcam_size", 0.28)),
        "webcam_image_path": _resolve_avatar_path(options.get("webcam_image_id")) if use_photo else None,
        "hook_text": hook_title if show_hook else None,
        "hook_position": options.get("hook_position", "between"),
        "watermark_text": (options.get("watermark_text") or "").strip() or None,
        "watermark_opacity": float(options.get("watermark_opacity", 0.55)),
        "jump_cuts": bool(options.get("jump_cuts", False)),
        "bg_music_path": _resolve_music_path(options.get("bg_music_id")),
        "bg_music_volume": float(options.get("bg_music_volume", 0.18)),
        "target_fps": int(options.get("target_fps", 30)),
        "video_enhance": bool(options.get("video_enhance", False)),
    }


def _run_remote_pipeline(job_id: str, options: Dict[str, Any]) -> None:
    try:
        job = get_job(job_id)
        if not job:
            return

        jdir = _job_dir(job_id)
        remote_url = job["remote_url"]
        remote_meta = json.loads((jdir / "remote_meta.json").read_text(encoding="utf-8"))

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
                else "Анализ по карте пересмотров / пикам чата стрима..."
            ),
        )

        clip_count = int(options.get("clip_count", 5))
        min_dur = float(options.get("min_duration", 20))
        max_dur = float(options.get("max_duration", 55))

        def on_hl(frac: float, msg: str) -> None:
            _update_job(job_id, stage="analyzing", progress=int(22 + frac * 18), message=msg)

        saved_cfg = load_settings()
        use_ai = bool(options.get("use_ai_director", True))
        search_chat = bool(options.get("search_chat_activity", True))
        search_laugh = bool(options.get("search_laughter", True))
        shuffle_seed = int(options.get("shuffle_seed") or 0)
        exclude_ranges = options.get("_exclude_ranges") or []

        gemini_key = (options.get("gemini_api_key") or saved_cfg.get("gemini_api_key") or "").strip() if use_ai else ""
        ollama_model = (options.get("ollama_model") or "").strip() if use_ai else ""
        highlights: List[Dict[str, Any]] = []

        # Extract top YouTube Heatmap / Twitch Chat peak centers to guide the AI Comedy Director!
        remote_heatmap = (remote_meta.get("heatmap") or []) if search_chat else []
        remote_peak_times: List[float] = []
        if remote_heatmap:
            for h in sorted(remote_heatmap, key=lambda x: float(x.get("value", 0.0)), reverse=True)[:18]:
                remote_peak_times.append((float(h["start_time"]) + float(h["end_time"])) * 0.5)

        # Priority 1: Full-transcript AI Comedy Director (unless shuffling to force fresh local picks)
        if segments and gemini_key and shuffle_seed == 0:
            try:
                highlights = find_funny_moments_gemini(
                    segments=segments,
                    total_duration=float(remote_meta.get("duration") or 0),
                    api_key=gemini_key,
                    clip_count=clip_count,
                    min_duration=min_dur,
                    max_duration=max_dur,
                    peak_times=remote_peak_times,
                    progress_cb=on_hl,
                )
            except Exception as exc:
                print(f"[ai_director] Gemini failed ({exc}), falling back to local detector")
                _update_job(job_id, ai_notice=f"Gemini не ответил ({exc}) — использован локальный отбор")
        elif gemini_key and not segments and shuffle_seed == 0:
            _update_job(job_id, ai_notice="У этого видео нет готовых субтитров на платформе — анализ по карте пересмотров/чату")

        if not highlights and segments and ollama_model and shuffle_seed == 0:
            try:
                highlights = find_funny_moments_ollama(
                    segments=segments,
                    total_duration=float(remote_meta.get("duration") or 0),
                    model_name=ollama_model,
                    clip_count=clip_count,
                    min_duration=min_dur,
                    max_duration=max_dur,
                    peak_times=remote_peak_times,
                    progress_cb=on_hl,
                )
            except Exception as exc:
                print(f"[ai_director] Ollama failed ({exc}), falling back to local detector")

        # Fallback (or Shuffle mode): Local Heatmap / Twitch Chat / Russian Laughter Detector
        if not highlights:
            highlights = find_remote_highlights(
                remote_meta=remote_meta,
                segments=segments,
                words=words,
                clip_count=clip_count,
                min_duration=min_dur,
                max_duration=max_dur,
                search_chat_activity=search_chat,
                search_laughter=search_laugh,
                shuffle_seed=shuffle_seed,
                exclude_ranges=exclude_ranges,
                progress_cb=on_hl,
            )

        whisper_model = options.get("whisper_model", "small")
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

            raw_seg_path = download_clip_segment(
                url=remote_url,
                start=hl["start"],
                end=hl["end"],
                output_mp4=jdir / f"raw_{clip_id}.mp4",
            )
            seg_meta = probe_video(raw_seg_path)
            seg_dur = float(seg_meta.get("duration") or hl["duration"])

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

            transcript_txt = " ".join(s["text"] for s in clip_segs).strip() or hl.get("transcript", "")
            clip_title = hl.get("title") or _make_clip_title(transcript_txt, idx + 1)
            if not hl.get("transcript") and transcript_txt:
                clip_title = _make_clip_title(transcript_txt, idx + 1)

            _update_job(
                job_id,
                stage="rendering",
                progress=int(base_pct + step_span * 0.68),
                message=f"Клип {idx + 1}/{n_total}: рендер 9:16 + эффекты и субтитры...",
            )
            out_mp4 = jdir / f"{clip_id}.mp4"
            out_thumb = jdir / f"{clip_id}.jpg"
            r_kwargs = _extract_render_kwargs(options, clip_title)

            render_clip(
                source_video=raw_seg_path,
                output_mp4=out_mp4,
                thumb_jpg=out_thumb,
                clip_start=0.0,
                clip_end=seg_dur,
                words=clip_words,
                **r_kwargs,
            )

            hl_out = dict(hl)
            hl_out["title"] = clip_title
            hl_out["hook_text"] = clip_title
            hl_out["transcript"] = transcript_txt
            hl_out["tiktok_caption"] = generate_tiktok_caption(
                clip_title, transcript_txt, hl.get("tags"), job.get("original_filename", "")
            )
            hl_out["raw_segment_path"] = str(raw_seg_path)
            hl_out["raw_segment_duration"] = round(seg_dur, 2)
            hl_out["trim_start"] = 0.0
            hl_out["trim_end"] = round(seg_dur, 2)
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

        if not wav_path.exists():
            _update_job(
                job_id,
                stage="extracting_audio",
                progress=5,
                message="Извлечение аудиодорожки (16 кГц)...",
            )
            extract_audio_wav(video_path, wav_path)

        # Reuse cached local transcription on Shuffle so re-picking moments is instant!
        whisper_model = options.get("whisper_model", "small")
        if words_path.exists() and int(options.get("shuffle_seed") or 0) > 0:
            cached_w = json.loads(words_path.read_text(encoding="utf-8"))
            segments = cached_w.get("segments", [])
            words = cached_w.get("words", [])
            _update_job(job_id, stage="analyzing", progress=52, words_count=len(words), message="Перемешивание и поиск новых моментов...")
        else:
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

        clip_count = int(options.get("clip_count", 5))
        min_dur = float(options.get("min_duration", 20))
        max_dur = float(options.get("max_duration", 55))

        def on_highlights(frac: float, msg: str) -> None:
            pct = int(52 + frac * 16)
            _update_job(job_id, stage="analyzing", progress=pct, message=msg)

        saved_cfg = load_settings()
        use_ai = bool(options.get("use_ai_director", True))
        search_laugh = bool(options.get("search_laughter", True))
        shuffle_seed = int(options.get("shuffle_seed") or 0)
        exclude_ranges = options.get("_exclude_ranges") or []

        gemini_key = (options.get("gemini_api_key") or saved_cfg.get("gemini_api_key") or "").strip() if use_ai else ""
        ollama_model = (options.get("ollama_model") or "").strip() if use_ai else ""
        highlights: List[Dict[str, Any]] = []

        # Compute audio laughter/excitement peaks to annotate transcript for the AI Comedy Director!
        local_peak_times: List[float] = []
        if search_laugh:
            try:
                _rms, _burst, _bsec = compute_audio_features(wav_path, bin_sec=0.25)
                local_peak_times = _find_audio_peak_times(_rms, _burst, _bsec, top_k=24)
            except Exception:
                pass

        if segments and gemini_key and shuffle_seed == 0:
            try:
                highlights = find_funny_moments_gemini(
                    segments=segments,
                    total_duration=total_duration,
                    api_key=gemini_key,
                    clip_count=clip_count,
                    min_duration=min_dur,
                    max_duration=max_dur,
                    peak_times=local_peak_times,
                    progress_cb=on_highlights,
                )
            except Exception as exc:
                print(f"[ai_director] Gemini failed ({exc}), falling back to local detector")
                _update_job(job_id, ai_notice=f"Gemini не ответил ({exc}) — использован локальный отбор")

        if not highlights and segments and ollama_model and shuffle_seed == 0:
            try:
                highlights = find_funny_moments_ollama(
                    segments=segments,
                    total_duration=total_duration,
                    model_name=ollama_model,
                    clip_count=clip_count,
                    min_duration=min_dur,
                    max_duration=max_dur,
                    peak_times=local_peak_times,
                    progress_cb=on_highlights,
                )
            except Exception as exc:
                print(f"[ai_director] Ollama failed ({exc}), falling back to local detector")

        if not highlights:
            highlights = find_highlights(
                video_path=video_path,
                wav_path=wav_path,
                total_duration=total_duration,
                segments=segments,
                words=words,
                clip_count=clip_count,
                min_duration=min_dur,
                max_duration=max_dur,
                search_laughter=search_laugh,
                shuffle_seed=shuffle_seed,
                exclude_ranges=exclude_ranges,
                progress_cb=on_highlights,
            )

        hw = get_hardware_info()
        workers = int(hw.get("max_parallel_renders", 1))
        n_total = max(1, len(highlights))

        def _render_one(idx_hl):
            idx, hl = idx_hl
            clip_id = hl["id"]
            out_mp4 = jdir / f"{clip_id}.mp4"
            out_thumb = jdir / f"{clip_id}.jpg"
            r_kwargs = _extract_render_kwargs(options, hl["title"])

            render_clip(
                source_video=video_path,
                output_mp4=out_mp4,
                thumb_jpg=out_thumb,
                clip_start=hl["start"],
                clip_end=hl["end"],
                words=words,
                **r_kwargs,
            )

            hl_out = dict(hl)
            hl_out["hook_text"] = hl["title"]
            hl_out["tiktok_caption"] = generate_tiktok_caption(
                hl["title"], hl.get("transcript", ""), hl.get("tags"), job.get("original_filename", "")
            )
            hl_out["trim_start"] = hl["start"]
            hl_out["trim_end"] = hl["end"]
            hl_out["version"] = int(time.time())
            hl_out["file_size_mb"] = round(out_mp4.stat().st_size / (1024 * 1024), 2)
            return idx, hl_out

        rendered_map: Dict[int, Dict[str, Any]] = {}
        if workers > 1 and n_total > 1:
            _update_job(
                job_id,
                stage="rendering",
                progress=70,
                message=f"Параллельный RTX NVENC рендер {n_total} клипов ({workers} потока)...",
            )
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futs = [pool.submit(_render_one, (i, hl)) for i, hl in enumerate(highlights)]
                done_cnt = 0
                for fut in as_completed(futs):
                    idx, hl_out = fut.result()
                    rendered_map[idx] = hl_out
                    done_cnt += 1
                    pct = int(68 + (done_cnt / n_total) * 30)
                    ordered = [rendered_map[k] for k in sorted(rendered_map.keys())]
                    _update_job(
                        job_id,
                        stage="rendering",
                        progress=pct,
                        message=f"RTX NVENC рендер: готово {done_cnt} из {n_total} клипов...",
                        clips=ordered,
                    )
        else:
            for idx, hl in enumerate(highlights):
                pct = int(68 + (idx / n_total) * 30)
                _update_job(
                    job_id,
                    stage="rendering",
                    progress=pct,
                    message=f"Рендеринг клипа {idx + 1} из {n_total} (9:16 + эффекты и субтитры)...",
                )
                _, hl_out = _render_one((idx, hl))
                rendered_map[idx] = hl_out
                ordered = [rendered_map[k] for k in sorted(rendered_map.keys())]
                _update_job(job_id, clips=ordered)

        rendered_clips = [rendered_map[k] for k in sorted(rendered_map.keys())]

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


def _realign_edited_words(
    orig_words: List[Dict[str, Any]],
    new_transcript: str,
    clip_start: float,
    clip_end: float,
) -> List[Dict[str, Any]]:
    """
    Map user-edited Russian subtitle text back onto the original word timestamps
    so fixing typos/streamer names keeps smooth karaoke timing!
    """
    new_tokens = [t.strip() for t in new_transcript.split() if t.strip()]
    if not new_tokens:
        return []

    in_range = [w for w in orig_words if w["end"] > clip_start and w["start"] < clip_end]
    if not in_range:
        dur = max(0.5, clip_end - clip_start)
        step = dur / len(new_tokens)
        return [
            {
                "word": tok,
                "start": round(clip_start + i * step, 3),
                "end": round(clip_start + (i + 1) * step, 3),
            }
            for i, tok in enumerate(new_tokens)
        ]

    # Proportional alignment across the original speech span
    t0 = in_range[0]["start"]
    t1 = in_range[-1]["end"]
    if len(new_tokens) == len(in_range):
        return [
            {"word": tok, "start": orig["start"], "end": orig["end"]}
            for tok, orig in zip(new_tokens, in_range)
        ]

    span = max(0.3, t1 - t0)
    step = span / len(new_tokens)
    return [
        {
            "word": tok,
            "start": round(t0 + i * step, 3),
            "end": round(t0 + (i + 1) * step, 3),
        }
        for i, tok in enumerate(new_tokens)
    ]


def rerender_single_clip(
    job_id: str,
    clip_id: str,
    options: Dict[str, Any],
    edited_transcript: Optional[str] = None,
    edited_hook_text: Optional[str] = None,
    trim_start: Optional[float] = None,
    trim_end: Optional[float] = None,
) -> Dict[str, Any]:
    """Re-render a single clip with updated style/crop/trim/edited subtitles without re-transcribing."""
    job = get_job(job_id)
    if not job:
        raise ValueError("Проект не найден")

    jdir = _job_dir(job_id)
    target_clip = next((c for c in job.get("clips", []) if c["id"] == clip_id), None)
    if not target_clip:
        raise ValueError("Клип не найден")

    out_mp4 = jdir / f"{clip_id}.mp4"
    out_thumb = jdir / f"{clip_id}.jpg"
    is_url = job.get("source_type") == "url"

    if is_url:
        source_video = Path(target_clip.get("raw_segment_path") or (jdir / f"raw_{clip_id}.mp4"))
        clip_words_path = jdir / f"{clip_id}_words.json"
        if not source_video.exists() or not clip_words_path.exists():
            raise ValueError("Исходный фрагмент клипа не найден")
        words = json.loads(clip_words_path.read_text(encoding="utf-8")).get("words", [])
        max_len = float(target_clip.get("raw_segment_duration") or target_clip["duration"])
        c_start = max(0.0, float(trim_start if trim_start is not None else target_clip.get("trim_start", 0.0)))
        c_end = min(max_len, float(trim_end if trim_end is not None else target_clip.get("trim_end", max_len)))
    else:
        words_path = jdir / "words.json"
        if not words_path.exists():
            raise ValueError("Таймкоды субтитров не найдены")
        words = json.loads(words_path.read_text(encoding="utf-8")).get("words", [])
        source_video = Path(job["video_path"])
        total_dur = float(job["video_meta"].get("duration") or target_clip["end"])
        c_start = max(0.0, float(trim_start if trim_start is not None else target_clip.get("trim_start", target_clip["start"])))
        c_end = min(total_dur, float(trim_end if trim_end is not None else target_clip.get("trim_end", target_clip["end"])))

    if c_end - c_start < 2.0:
        c_end = c_start + 2.0

    # Apply user-edited subtitle text if provided
    custom_words_path = jdir / f"{clip_id}_custom_words.json"
    if edited_transcript is not None:
        words_to_use = _realign_edited_words(words, edited_transcript, c_start, c_end)
        custom_words_path.write_text(json.dumps(words_to_use, ensure_ascii=False), encoding="utf-8")
    elif custom_words_path.exists():
        words_to_use = json.loads(custom_words_path.read_text(encoding="utf-8"))
    else:
        words_to_use = words

    hook_title = (
        edited_hook_text
        if edited_hook_text is not None
        else target_clip.get("hook_text") or target_clip.get("title") or ""
    )
    r_kwargs = _extract_render_kwargs(options, hook_title)

    render_clip(
        source_video=source_video,
        output_mp4=out_mp4,
        thumb_jpg=out_thumb,
        clip_start=c_start,
        clip_end=c_end,
        words=words_to_use,
        **r_kwargs,
    )

    updated_clip: Dict[str, Any] = {}
    with _LOCK:
        live_job = _JOBS[job_id]
        for c in live_job["clips"]:
            if c["id"] == clip_id:
                if edited_transcript is not None:
                    c["transcript"] = edited_transcript.strip()
                if edited_hook_text is not None:
                    c["hook_text"] = edited_hook_text.strip()
                    if edited_hook_text.strip():
                        c["title"] = edited_hook_text.strip()
                c["trim_start"] = round(c_start, 2)
                c["trim_end"] = round(c_end, 2)
                c["duration"] = round(c_end - c_start, 2)
                c["tiktok_caption"] = generate_tiktok_caption(
                    c.get("title", ""), c.get("transcript", ""), c.get("tags"), live_job.get("original_filename", "")
                )
                c["version"] = int(time.time())
                c["file_size_mb"] = round(out_mp4.stat().st_size / (1024 * 1024), 2)
                updated_clip = dict(c)
                break
        _save_job(live_job)

    return updated_clip


def create_custom_clip(
    job_id: str,
    start_sec: float,
    end_sec: float,
    options: Dict[str, Any],
    custom_title: str = "",
) -> Dict[str, Any]:
    """Cut & render any custom [start_sec, end_sec] timestamp from a loaded video or remote YouTube/Twitch link."""
    job = get_job(job_id)
    if not job:
        raise ValueError("Проект не найден")
    if end_sec <= start_sec + 2.0:
        raise ValueError("Конец клипа должен быть хотя бы на 2 секунды позже начала")

    jdir = _job_dir(job_id)
    clip_num = len(job.get("clips", [])) + 1
    clip_id = f"clip_custom_{int(time.time())}"
    out_mp4 = jdir / f"{clip_id}.mp4"
    out_thumb = jdir / f"{clip_id}.jpg"
    whisper_model = options.get("whisper_model", "small")

    if job.get("source_type") == "url":
        raw_seg_path = download_clip_segment(
            url=job["remote_url"],
            start=start_sec,
            end=end_sec,
            output_mp4=jdir / f"raw_{clip_id}.mp4",
        )
        seg_meta = probe_video(raw_seg_path)
        seg_dur = float(seg_meta.get("duration") or (end_sec - start_sec))
        clip_wav = jdir / f"raw_{clip_id}.wav"
        extract_audio_wav(raw_seg_path, clip_wav)
        clip_segs, clip_words = transcribe_russian(clip_wav, total_duration=seg_dur, model_size=whisper_model)
        (jdir / f"{clip_id}_words.json").write_text(
            json.dumps({"segments": clip_segs, "words": clip_words}, ensure_ascii=False),
            encoding="utf-8",
        )
        transcript_txt = " ".join(s["text"] for s in clip_segs).strip()
        title = custom_title.strip() or _make_clip_title(transcript_txt, clip_num)
        r_kwargs = _extract_render_kwargs(options, title)
        render_clip(
            source_video=raw_seg_path,
            output_mp4=out_mp4,
            thumb_jpg=out_thumb,
            clip_start=0.0,
            clip_end=seg_dur,
            words=clip_words,
            **r_kwargs,
        )
        new_clip = {
            "id": clip_id,
            "index": clip_num,
            "start": round(start_sec, 2),
            "end": round(end_sec, 2),
            "duration": round(seg_dur, 2),
            "title": title,
            "hook_text": title,
            "transcript": transcript_txt,
            "viral_score": 95,
            "tags": ["✂️ Ручной выбор"],
            "tiktok_caption": generate_tiktok_caption(title, transcript_txt, ["✂️ Ручной выбор"], job.get("original_filename", "")),
            "raw_segment_path": str(raw_seg_path),
            "raw_segment_duration": round(seg_dur, 2),
            "trim_start": 0.0,
            "trim_end": round(seg_dur, 2),
            "version": int(time.time()),
            "file_size_mb": round(out_mp4.stat().st_size / (1024 * 1024), 2),
        }
    else:
        video_path = Path(job["video_path"])
        words_path = jdir / "words.json"
        if words_path.exists():
            words = json.loads(words_path.read_text(encoding="utf-8")).get("words", [])
        else:
            clip_wav = jdir / f"raw_{clip_id}.wav"
            extract_audio_wav(video_path, clip_wav)
            _, words = transcribe_russian(clip_wav, total_duration=float(job["video_meta"].get("duration") or end_sec), model_size=whisper_model)
        clip_words = [w for w in words if w["end"] > start_sec and w["start"] < end_sec]
        transcript_txt = " ".join(w["word"] for w in clip_words).strip()
        title = custom_title.strip() or _make_clip_title(transcript_txt, clip_num)
        r_kwargs = _extract_render_kwargs(options, title)
        render_clip(
            source_video=video_path,
            output_mp4=out_mp4,
            thumb_jpg=out_thumb,
            clip_start=start_sec,
            clip_end=end_sec,
            words=words,
            **r_kwargs,
        )
        new_clip = {
            "id": clip_id,
            "index": clip_num,
            "start": round(start_sec, 2),
            "end": round(end_sec, 2),
            "duration": round(end_sec - start_sec, 2),
            "title": title,
            "hook_text": title,
            "transcript": transcript_txt,
            "viral_score": 95,
            "tags": ["✂️ Ручной выбор"],
            "tiktok_caption": generate_tiktok_caption(title, transcript_txt, ["✂️ Ручной выбор"], job.get("original_filename", "")),
            "trim_start": round(start_sec, 2),
            "trim_end": round(end_sec, 2),
            "version": int(time.time()),
            "file_size_mb": round(out_mp4.stat().st_size / (1024 * 1024), 2),
        }

    with _LOCK:
        live_job = _JOBS[job_id]
        live_job.setdefault("clips", []).insert(0, new_clip)
        if live_job.get("status") == "uploaded":
            live_job["status"] = "completed"
        _save_job(live_job)

    return new_clip
