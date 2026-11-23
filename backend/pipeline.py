"""Background job pipeline orchestrator for local files and remote YouTube/Twitch VOD links."""
import datetime
import json
import re
import shutil
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.accounts import list_accounts
from backend.ai_director import find_funny_moments_gemini, find_funny_moments_ollama
from backend.config import ADS_DIR, AVATARS_DIR, EXPORTS_DIR, JOBS_DIR, MUSIC_DIR, OUTROS_DIR, SATISFYING_DIR, load_settings
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
    download_lightweight_audio,
    fetch_remote_transcript,
    find_remote_highlights,
    probe_remote_url,
)
from backend.renderer import merge_clips_compilation, probe_video, render_clip
from backend.studio_extras import parse_manual_timecodes
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


def _resolve_outro_path(outro_id: Optional[str]) -> Optional[Path]:
    if not outro_id:
        return None
    p = OUTROS_DIR / Path(outro_id).name
    return p if p.exists() else None


def _resolve_avatar_path(avatar_id: Optional[str]) -> Optional[Path]:
    if not avatar_id:
        return None
    p = AVATARS_DIR / Path(avatar_id).name
    return p if p.exists() else None


def _resolve_ad_path(ad_file_id: Optional[str]) -> Optional[Path]:
    if not ad_file_id:
        return None
    p = ADS_DIR / Path(ad_file_id).name
    return p if p.exists() else None


def _resolve_satisfying_path(sat_id: Optional[str]) -> Optional[Path]:
    if not sat_id:
        return None
    p = SATISFYING_DIR / Path(sat_id).name
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
        "hook_text_color": options.get("hook_text_color", "#0C0E18"),
        "hook_bg_color": options.get("hook_bg_color", "#FFFFFF"),
        "hook_border_color": options.get("hook_border_color", "#FFE600"),
        "hook_font_size": options.get("hook_font_size", "medium"),
        "watermark_text": (options.get("watermark_text") or "").strip() or None,
        "watermark_opacity": float(options.get("watermark_opacity", 0.55)),
        "jump_cuts": bool(options.get("jump_cuts", False)),
        "bg_music_path": _resolve_music_path(options.get("bg_music_id")),
        "bg_music_volume": float(options.get("bg_music_volume", 0.18)),
        "target_fps": int(options.get("target_fps", 30)),
        "video_enhance": bool(options.get("video_enhance", False)),
        "ad_mode": options.get("ad_mode", "bottom_overlay") if options.get("enable_ad_banner") else None,
        "ad_banner_path": _resolve_ad_path(options.get("ad_banner_id")) if options.get("enable_ad_banner") else None,
        "ad_audio_path": _resolve_ad_path(options.get("ad_audio_id")) if options.get("enable_ad_banner") else None,
        "satisfying_video_path": _resolve_satisfying_path(options.get("satisfying_video_id")) if options.get("enable_satisfying_video") else None,
        "uniquify_video": bool(options.get("uniquify_video", False)),
        "auto_cover": bool(options.get("auto_cover", False)),
        "cover_title": hook_title,
        "webcam_rect": options.get("webcam_rect") if isinstance(options.get("webcam_rect"), dict) else None,
        "outro_path": _resolve_outro_path(options.get("outro_id")) if options.get("enable_outro") else None,
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

        # Feature #12: Manual Timecodes override (skip AI/heuristic search and cut exact ranges!)
        manual_tc_raw = (options.get("manual_timecodes") or "").strip()
        if manual_tc_raw:
            highlights = parse_manual_timecodes(manual_tc_raw, float(remote_meta.get("duration") or 0))
            if highlights:
                _update_job(job_id, stage="analyzing", progress=38, message=f"Вырезка по {len(highlights)} заданным таймкодам...")

        # Extract top YouTube Heatmap / Twitch Chat peak centers to guide the AI Comedy Director!
        remote_heatmap = (remote_meta.get("heatmap") or []) if search_chat else []
        remote_peak_times: List[float] = []
        if remote_heatmap:
            for h in sorted(remote_heatmap, key=lambda x: float(x.get("value", 0.0)), reverse=True)[:18]:
                remote_peak_times.append((float(h["start_time"]) + float(h["end_time"])) * 0.5)

        # Priority 1: Full-transcript AI Comedy Director (unless shuffling or manual timecodes)
        if not highlights and segments and gemini_key and shuffle_seed == 0:
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

        # Download ONLY lightweight audio (no video!) when search_laughter is ON so we detect REAL laughter/screams!
        light_wav: Optional[Path] = None
        if search_laugh:
            _update_job(
                job_id,
                stage="analyzing",
                progress=24,
                message="😂 Загрузка лёгкой аудиодорожки для локального поиска смеха и криков стримера...",
            )
            light_wav = download_lightweight_audio(remote_url, jdir / "light_audio.wav")

        # Fallback (or Shuffle mode): Local Acoustic Laughter + Twitch Chat / YouTube Heatmap Detector
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
                audio_wav_path=light_wav,
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

        # Feature #12: Manual Timecodes override
        manual_tc_raw = (options.get("manual_timecodes") or "").strip()
        if manual_tc_raw:
            highlights = parse_manual_timecodes(manual_tc_raw, total_duration)
            if highlights:
                for hl in highlights:
                    seg_words = [w["word"] for w in words if w["end"] >= hl["start"] and w["start"] <= hl["end"]]
                    hl["transcript"] = " ".join(seg_words).strip()
                _update_job(job_id, stage="analyzing", progress=66, message=f"Вырезка по {len(highlights)} заданным таймкодам...")

        # Compute audio laughter/excitement peaks to annotate transcript for the AI Comedy Director!
        local_peak_times: List[float] = []
        if not highlights and search_laugh:
            try:
                _rms, _burst, _bsec = compute_audio_features(wav_path, bin_sec=0.25)
                local_peak_times = _find_audio_peak_times(_rms, _burst, _bsec, top_k=24)
            except Exception:
                pass

        if not highlights and segments and gemini_key and shuffle_seed == 0:
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
    source_start: Optional[float] = None,
    source_end: Optional[float] = None,
) -> Dict[str, Any]:
    """Re-render a single clip with updated style/crop/timecode shift/edited subtitles."""
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
    total_dur = float(job.get("video_meta", {}).get("duration") or 0)

    new_abs_start = float(target_clip.get("start", 0.0))
    new_abs_end = float(target_clip.get("end", new_abs_start + target_clip.get("duration", 20.0)))
    re_downloaded = False
    new_transcript_from_whisper: Optional[str] = None

    if is_url:
        old_abs_start = float(target_clip.get("start", 0.0))
        old_abs_end = float(target_clip.get("end", old_abs_start + target_clip.get("duration", 20.0)))

        # Check if user shifted the absolute stream timecode (e.g. -10s earlier or +10s later)
        if source_start is not None or source_end is not None:
            req_s = max(0.0, float(source_start if source_start is not None else old_abs_start))
            req_e = float(source_end if source_end is not None else old_abs_end)
            if total_dur > 0:
                req_e = min(total_dur, req_e)
            if req_e - req_s < 2.0:
                req_e = req_s + 2.0
            new_abs_start, new_abs_end = req_s, req_e

            if abs(req_s - old_abs_start) > 0.25 or abs(req_e - old_abs_end) > 0.25:
                # Download the newly shifted segment directly from YouTube / Twitch!
                raw_seg_path = download_clip_segment(
                    url=job["remote_url"],
                    start=req_s,
                    end=req_e,
                    output_mp4=jdir / f"raw_{clip_id}.mp4",
                )
                seg_meta = probe_video(raw_seg_path)
                seg_dur = float(seg_meta.get("duration") or (req_e - req_s))
                clip_wav = jdir / f"raw_{clip_id}.wav"
                extract_audio_wav(raw_seg_path, clip_wav)
                whisper_model = options.get("whisper_model", "small")
                clip_segs, words = transcribe_russian(clip_wav, total_duration=seg_dur, model_size=whisper_model)
                (jdir / f"{clip_id}_words.json").write_text(
                    json.dumps({"segments": clip_segs, "words": words}, ensure_ascii=False),
                    encoding="utf-8",
                )
                # Remove stale custom_words override since timecode shifted to new audio
                stale_custom = jdir / f"{clip_id}_custom_words.json"
                if stale_custom.exists():
                    stale_custom.unlink()
                source_video = raw_seg_path
                c_start, c_end = 0.0, seg_dur
                new_transcript_from_whisper = " ".join(s["text"] for s in clip_segs).strip()
                re_downloaded = True

        if not re_downloaded:
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
        max_dur = total_dur or float(target_clip["end"])
        req_s = source_start if source_start is not None else (trim_start if trim_start is not None else target_clip.get("trim_start", target_clip["start"]))
        req_e = source_end if source_end is not None else (trim_end if trim_end is not None else target_clip.get("trim_end", target_clip["end"]))
        c_start = max(0.0, float(req_s))
        c_end = min(max_dur, float(req_e))
        new_abs_start, new_abs_end = c_start, c_end
        if source_start is not None or source_end is not None:
            w_slice = [w for w in words if w["end"] > c_start and w["start"] < c_end]
            new_transcript_from_whisper = " ".join(w["word"] for w in w_slice).strip()
            stale_custom = jdir / f"{clip_id}_custom_words.json"
            if stale_custom.exists():
                stale_custom.unlink()

    if c_end - c_start < 2.0:
        c_end = c_start + 2.0

    # Apply user-edited subtitle text if provided (unless timecode shifted to new speech)
    custom_words_path = jdir / f"{clip_id}_custom_words.json"
    if edited_transcript is not None and not re_downloaded and source_start is None and source_end is None:
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
                if new_transcript_from_whisper is not None:
                    c["transcript"] = new_transcript_from_whisper
                elif edited_transcript is not None:
                    c["transcript"] = edited_transcript.strip()
                if edited_hook_text is not None:
                    c["hook_text"] = edited_hook_text.strip()
                    if edited_hook_text.strip():
                        c["title"] = edited_hook_text.strip()
                c["start"] = round(new_abs_start, 2)
                c["end"] = round(new_abs_end, 2)
                c["trim_start"] = round(c_start, 2)
                c["trim_end"] = round(c_end, 2)
                c["duration"] = round(c_end - c_start, 2)
                if re_downloaded:
                    c["raw_segment_path"] = str(source_video)
                    c["raw_segment_duration"] = round(c_end, 2)
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


def mark_clip_published(
    job_id: str,
    clip_id: str,
    account_id: str,
    account_name: str = "",
    platform: str = "tiktok",
) -> Optional[Dict[str, Any]]:
    """Mark a clip as published to a specific account & social platform (tiktok/youtube/instagram)."""
    updated = None
    with _LOCK:
        live_job = _JOBS.get(job_id)
        if not live_job:
            return None
        for c in live_job.get("clips", []):
            if c.get("id") == clip_id:
                pubs = list(c.get("published_to") or [])
                entry = {
                    "account_id": account_id,
                    "account_name": account_name or account_id,
                    "platform": platform,
                    "at": int(time.time()),
                }
                if not any(p.get("account_id") == account_id and p.get("platform", "tiktok") == platform for p in pubs):
                    pubs.append(entry)
                c["published_to"] = pubs
                updated = dict(c)
                break
        if updated is not None:
            _save_job(live_job)
    return updated


def create_compilation_clip(job_id: str, clip_ids: List[str], title: str = "") -> Dict[str, Any]:
    """Feature #3: Merge 2..6 rendered clips into a single Top Moments compilation clip."""
    job = get_job(job_id)
    if not job:
        raise ValueError("Проект не найден")
    jdir = _job_dir(job_id)
    clips_by_id = {c["id"]: c for c in job.get("clips", [])}
    selected = [clips_by_id[cid] for cid in clip_ids if cid in clips_by_id]
    if len(selected) < 2:
        raise ValueError("Выберите минимум 2 клипа для склейки")

    paths = [jdir / f"{c['id']}.mp4" for c in selected]
    comp_id = f"clip_comp_{int(time.time())}"
    out_mp4 = jdir / f"{comp_id}.mp4"
    out_thumb = jdir / f"{comp_id}.jpg"
    merge_clips_compilation(paths, out_mp4, out_thumb)

    meta = probe_video(out_mp4)
    comp_title = title.strip() or f"ТОП-{len(selected)} моментов: {selected[0].get('title', '')[:40]}"
    comp_transcript = " • ".join(c.get("title", "") for c in selected)
    comp_clip = {
        "id": comp_id,
        "index": 0,
        "start": 0.0,
        "end": round(float(meta.get("duration") or 0), 2),
        "duration": round(float(meta.get("duration") or 0), 2),
        "title": comp_title,
        "hook_text": comp_title,
        "transcript": comp_transcript,
        "viral_score": 98,
        "tags": [f"🎞 Склейка ({len(selected)} клипа)", "🔥 Подборка"],
        "tiktok_caption": generate_tiktok_caption(comp_title, comp_transcript, ["🔥 Подборка"], job.get("original_filename", "")),
        "version": int(time.time()),
        "file_size_mb": round(out_mp4.stat().st_size / (1024 * 1024), 2),
    }

    with _LOCK:
        live_job = _JOBS[job_id]
        live_job.setdefault("clips", []).insert(0, comp_clip)
        _save_job(live_job)
    return comp_clip


def export_job_to_account_folder(job_id: str, account_name: str = "General") -> Dict[str, Any]:
    """Feature #17: Export all clips + captions.txt cleanly into EXPORTS_DIR/<Account>/<YYYY-MM-DD>/."""
    job = get_job(job_id)
    if not job or not job.get("clips"):
        raise ValueError("Нет готовых клипов для экспорта")

    safe_acc = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ _-]+", "", account_name or "General").strip() or "General"
    date_str = datetime.date.today().isoformat()
    dest_dir = EXPORTS_DIR / safe_acc / f"{date_str}_{job_id}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    jdir = _job_dir(job_id)
    copied = 0
    cap_lines: List[str] = []
    for idx, c in enumerate(job["clips"], start=1):
        mp4 = jdir / f"{c['id']}.mp4"
        if mp4.exists():
            shutil.copy2(mp4, dest_dir / f"{idx:02d}_score{c.get('viral_score', 0)}_{c['id']}.mp4")
            copied += 1
        cap_lines.append(f"=== #{idx}: {c.get('title', '')} ===")
        cap_lines.append(c.get("tiktok_caption", ""))
        cap_lines.append("")

    (dest_dir / "captions_and_hashtags.txt").write_text("\n".join(cap_lines), encoding="utf-8")
    return {"folder": str(dest_dir.resolve()), "count": copied}


def get_studio_dashboard_stats() -> Dict[str, Any]:
    """Feature #17: Studio-wide analytics across all jobs, clips, accounts and social platforms."""
    all_jobs = list_jobs(limit=200)
    accounts = list_accounts()
    total_clips = 0
    pub_tiktok = 0
    pub_youtube = 0
    pub_instagram = 0
    for j in all_jobs:
        for c in j.get("clips") or []:
            total_clips += 1
            for p in c.get("published_to") or []:
                plat = p.get("platform", "tiktok")
                if plat == "youtube":
                    pub_youtube += 1
                elif plat == "instagram":
                    pub_instagram += 1
                else:
                    pub_tiktok += 1

    return {
        "total_projects": len(all_jobs),
        "total_clips": total_clips,
        "published_tiktok": pub_tiktok,
        "published_youtube": pub_youtube,
        "published_instagram": pub_instagram,
        "accounts_count": len(accounts),
        "accounts": accounts,
        "exports_dir": str(EXPORTS_DIR.resolve()),
    }


# =====================================================================
# Feature #11: Batch URL Queue (sequential unattended processing)
# =====================================================================

_BATCH_LOCK = threading.Lock()
_BATCH_STATE: Dict[str, Any] = {
    "running": False,
    "total": 0,
    "completed": 0,
    "failed": 0,
    "current_index": -1,
    "items": [],
}


def get_batch_status() -> Dict[str, Any]:
    with _BATCH_LOCK:
        return json.loads(json.dumps(_BATCH_STATE))


def start_batch_urls(urls: List[str], options: Dict[str, Any]) -> Dict[str, Any]:
    clean_urls = [u.strip() for u in urls if u and u.strip().startswith(("http://", "https://"))][:15]
    if not clean_urls:
        raise ValueError("Укажите хотя бы одну корректную ссылку (http/https)")

    with _BATCH_LOCK:
        if _BATCH_STATE["running"]:
            raise RuntimeError("Пакетная очередь уже выполняется — дождитесь завершения")
        _BATCH_STATE.update(
            {
                "running": True,
                "total": len(clean_urls),
                "completed": 0,
                "failed": 0,
                "current_index": 0,
                "items": [
                    {"url": u, "status": "queued", "job_id": None, "title": "", "error": None}
                    for u in clean_urls
                ],
            }
        )

    def _worker() -> None:
        for idx, url in enumerate(clean_urls):
            with _BATCH_LOCK:
                _BATCH_STATE["current_index"] = idx
                _BATCH_STATE["items"][idx]["status"] = "probing"
            try:
                remote_meta = probe_remote_url(url)
                job_id = f"batch_{int(time.time())}_{idx + 1}"
                job = create_remote_job(job_id, url, remote_meta)
                with _BATCH_LOCK:
                    _BATCH_STATE["items"][idx]["job_id"] = job_id
                    _BATCH_STATE["items"][idx]["title"] = job.get("original_filename", url)
                    _BATCH_STATE["items"][idx]["status"] = "processing"

                opts = dict(options)
                _update_job(
                    job_id,
                    status="processing",
                    stage="starting",
                    progress=2,
                    message="Пакетная обработка: запуск...",
                    options=opts,
                    error=None,
                )
                _run_remote_pipeline(job_id, opts)
                fin = get_job(job_id) or {}
                if fin.get("status") == "completed":
                    with _BATCH_LOCK:
                        _BATCH_STATE["items"][idx]["status"] = "completed"
                        _BATCH_STATE["completed"] += 1
                else:
                    with _BATCH_LOCK:
                        _BATCH_STATE["items"][idx]["status"] = "failed"
                        _BATCH_STATE["items"][idx]["error"] = fin.get("error") or "Ошибка обработки"
                        _BATCH_STATE["failed"] += 1
            except Exception as exc:
                with _BATCH_LOCK:
                    _BATCH_STATE["items"][idx]["status"] = "failed"
                    _BATCH_STATE["items"][idx]["error"] = str(exc)[:200]
                    _BATCH_STATE["failed"] += 1
        with _BATCH_LOCK:
            _BATCH_STATE["running"] = False
            _BATCH_STATE["current_index"] = -1

    threading.Thread(target=_worker, daemon=True).start()
    return get_batch_status()
