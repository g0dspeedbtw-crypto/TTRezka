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
from backend.config import ADS_DIR, AVATARS_DIR, EXPORTS_DIR, JOBS_DIR, LOGOS_DIR, MUSIC_DIR, OUTROS_DIR, SATISFYING_DIR, load_settings
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
from backend.studio_extras import build_clip_srt, parse_manual_timecodes
from backend.telegram_export import send_clip_to_telegram
from backend.transcriber import extract_audio_wav, transcribe_russian
from backend.twitch_chat import generate_tiktok_caption

_LOCK = threading.Lock()
_JOBS: Dict[str, Dict[str, Any]] = {}
_CANCELLED_JOBS = set()


def cancel_job(job_id: str) -> bool:
    """Feature #3 (v2.6): Signal a running job to stop cleanly."""
    with _LOCK:
        if job_id not in _JOBS:
            return False
        _CANCELLED_JOBS.add(job_id)
        if _JOBS[job_id].get("status") == "processing":
            _JOBS[job_id]["message"] = "⏹ Остановка обработки..."
            _save_job(_JOBS[job_id])
    return True


def is_job_cancelled(job_id: str) -> bool:
    with _LOCK:
        return job_id in _CANCELLED_JOBS


def delete_job(job_id: str) -> bool:
    """Feature #5 (v2.6): Permanently delete a project and its files."""
    with _LOCK:
        _CANCELLED_JOBS.add(job_id)
        job = _JOBS.pop(job_id, None)
    jdir = JOBS_DIR / job_id
    if jdir.exists():
        shutil.rmtree(jdir, ignore_errors=True)
    return job is not None or not jdir.exists()


def delete_clip(job_id: str, clip_id: str) -> bool:
    """Feature #5 (v2.6): Delete a single weak clip from a project."""
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return False
        clips = job.get("clips") or []
        new_clips = [c for c in clips if c.get("id") != clip_id]
        if len(new_clips) == len(clips):
            return False
        job["clips"] = new_clips
        _save_job(job)
    jdir = JOBS_DIR / job_id
    for ext in (".mp4", ".jpg"):
        (jdir / f"{clip_id}{ext}").unlink(missing_ok=True)
    return True


def update_clip_title(job_id: str, clip_id: str, new_title: str) -> Optional[Dict[str, Any]]:
    """Feature #9 (v2.7): Inline edit clip title without re-rendering."""
    clean = (new_title or "").strip()[:90]
    if not clean:
        return None
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        updated = None
        for c in job.get("clips") or []:
            if c.get("id") == clip_id:
                c["title"] = clean
                c["hook_text"] = clean
                updated = dict(c)
                break
        if updated is not None:
            _save_job(job)
    return updated


def _auto_send_clips_to_telegram(job_id: str, rendered_clips: List[Dict[str, Any]], options: Dict[str, Any]) -> int:
    """Auto-upload rendered clips to Telegram when tg_auto_send toggle is ON."""
    cfg = load_settings()
    enabled = bool(options.get("tg_auto_send") if options.get("tg_auto_send") is not None else cfg.get("tg_auto_send", False))
    token = (cfg.get("tg_bot_token") or "").strip()
    chat_id = (cfg.get("tg_chat_id") or "").strip()
    if not enabled or not token or not chat_id or not rendered_clips:
        return 0

    jdir = _job_dir(job_id)
    sent = 0
    for idx, c in enumerate(rendered_clips, start=1):
        if is_job_cancelled(job_id):
            break
        mp4 = jdir / f"{c['id']}.mp4"
        if not mp4.exists() or mp4.stat().st_size < 10_000:
            continue
        _update_job(job_id, progress=98, message=f"✈️ Отправка клипа {idx}/{len(rendered_clips)} в Telegram...")
        try:
            send_clip_to_telegram(token, chat_id, mp4, caption=c.get("tiktok_caption") or c.get("title", ""))
            c["sent_telegram"] = True
            sent += 1
            if idx < len(rendered_clips):
                time.sleep(1.1)
        except Exception as exc:
            print(f"[telegram] auto-send clip {c['id']} failed: {exc}")
    return sent


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


def _resolve_logo_path(logo_id: Optional[str]) -> Optional[Path]:
    if not logo_id:
        return None
    p = LOGOS_DIR / Path(logo_id).name
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
        "watermark_logo_path": _resolve_logo_path(options.get("watermark_logo_id")),
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
        "blur_rect": options.get("blur_rect") if isinstance(options.get("blur_rect"), dict) else None,
        "low_cpu_mode": bool(options.get("low_cpu_mode", False)),
    }


def _run_remote_pipeline(job_id: str, options: Dict[str, Any]) -> None:
    try:
        with _LOCK:
            _CANCELLED_JOBS.discard(job_id)
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
        search_screams = bool(options.get("search_screams", True))
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

        # Download ONLY lightweight audio (no video!) when laughter or screams search is ON!
        light_wav: Optional[Path] = None
        if search_laugh or search_screams:
            _update_job(
                job_id,
                stage="analyzing",
                progress=24,
                message="😂 Загрузка лёгкой аудиодорожки для локального поиска смеха и криков...",
            )
            light_wav = download_lightweight_audio(remote_url, jdir / "light_audio.wav")

        # Fallback (or Shuffle mode): Local Acoustic Laughter/Screams + Twitch Chat / YouTube Heatmap Detector
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
                search_screams=search_screams,
                shuffle_seed=shuffle_seed,
                exclude_ranges=exclude_ranges,
                audio_wav_path=light_wav,
                progress_cb=on_hl,
            )

        whisper_model = options.get("whisper_model", "small")
        rendered_clips: List[Dict[str, Any]] = []
        n_total = max(1, len(highlights))
        total_recognized_words = len(words)

        # STAGE 1: Parallel download ALL clip segments at once (4 simultaneous downloads!)
        _update_job(
            job_id,
            stage="rendering",
            progress=40,
            message=f"⬇️ Параллельная загрузка всех {n_total} фрагментов сразу...",
        )
        downloaded_map: Dict[int, Path] = {}

        def _dl_one_remote(pair):
            i_idx, h_item = pair
            if is_job_cancelled(job_id):
                return i_idx, None
            c_id = h_item["id"]
            dest = jdir / f"raw_{c_id}.mp4"
            for _try in range(2):
                try:
                    p = download_clip_segment(url=remote_url, start=h_item["start"], end=h_item["end"], output_mp4=dest)
                    if p.exists() and p.stat().st_size > 10_000:
                        return i_idx, p
                except Exception as exc_dl:
                    print(f"[remote] clip {c_id} download try {_try + 1} failed: {exc_dl}")
                    time.sleep(1.2)
            return i_idx, None

        dl_done = 0
        with ThreadPoolExecutor(max_workers=min(4, n_total)) as dl_pool:
            for i_idx, p_path in dl_pool.map(_dl_one_remote, enumerate(highlights)):
                dl_done += 1
                if p_path is not None:
                    downloaded_map[i_idx] = p_path
                _update_job(
                    job_id,
                    stage="rendering",
                    progress=int(40 + (dl_done / n_total) * 20),
                    message=f"⬇️ Скачано фрагментов: {dl_done}/{n_total} (параллельно)...",
                )

        # STAGE 2: Transcribe & render all downloaded clips
        for idx, hl in enumerate(highlights):
            if is_job_cancelled(job_id):
                _update_job(job_id, status="cancelled", stage="cancelled", message="⏹ Обработка остановлена пользователем.", clips=rendered_clips)
                return
            raw_seg_path = downloaded_map.get(idx)
            if not raw_seg_path:
                continue
            clip_id = hl["id"]
            base_pct = 60 + (idx / n_total) * 38
            step_span = 38 / n_total

            seg_meta = probe_video(raw_seg_path)
            seg_dur = float(seg_meta.get("duration") or hl["duration"])

            _update_job(
                job_id,
                stage="rendering",
                progress=int(base_pct + step_span * 0.2),
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
                progress=int(base_pct + step_span * 0.65),
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
            hl_out["ad_banner_id"] = options.get("ad_banner_id") if options.get("enable_ad_banner") else None
            rendered_clips.append(hl_out)

            _update_job(job_id, clips=rendered_clips, words_count=total_recognized_words)

        tg_sent = _auto_send_clips_to_telegram(job_id, rendered_clips, options)
        tg_note = f" • ✈️ Отправлено в Telegram: {tg_sent}" if tg_sent > 0 else ""
        _update_job(
            job_id,
            status="completed",
            stage="completed",
            progress=100,
            message=f"Готово! Создано {len(rendered_clips)} клипов 9:16 без скачивания всего видео.{tg_note}",
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
        with _LOCK:
            _CANCELLED_JOBS.discard(job_id)
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
        search_screams = bool(options.get("search_screams", True))
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

        # Compute audio laughter/scream peaks to annotate transcript for the AI Comedy Director!
        local_peak_times: List[float] = []
        if not highlights and (search_laugh or search_screams):
            try:
                _rms, _burst, _bsec = compute_audio_features(wav_path, bin_sec=0.25)
                _pmode = "both" if (search_laugh and search_screams) else ("laugh" if search_laugh else "scream")
                local_peak_times = _find_audio_peak_times(_rms, _burst, _bsec, top_k=24, mode=_pmode)
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
                search_screams=search_screams,
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
        tg_sent = _auto_send_clips_to_telegram(job_id, rendered_clips, options)
        tg_note = f" • ✈️ Отправлено в Telegram: {tg_sent}" if tg_sent > 0 else ""

        _update_job(
            job_id,
            status="completed",
            stage="completed",
            progress=100,
            message=f"Готово! Создано {len(rendered_clips)} клипов 9:16 с субтитрами.{tg_note}",
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
    """Feature #17 & #48: Studio-wide analytics across jobs, clips, accounts, platforms & ad integrations."""
    all_jobs = list_jobs(limit=200)
    accounts = list_accounts()
    total_clips = 0
    pub_tiktok = 0
    pub_youtube = 0
    pub_instagram = 0
    ad_counts: Dict[str, Dict[str, int]] = {}
    for j in all_jobs:
        job_ad_fallback = (j.get("options") or {}).get("ad_banner_id") if (j.get("options") or {}).get("enable_ad_banner") else None
        for c in j.get("clips") or []:
            total_clips += 1
            pubs = c.get("published_to") or []
            for p in pubs:
                plat = p.get("platform", "tiktok")
                if plat == "youtube":
                    pub_youtube += 1
                elif plat == "instagram":
                    pub_instagram += 1
                else:
                    pub_tiktok += 1
            ad_id = c.get("ad_banner_id") or job_ad_fallback
            if ad_id:
                rec = ad_counts.setdefault(ad_id, {"rendered": 0, "published": 0})
                rec["rendered"] += 1
                if pubs:
                    rec["published"] += len(pubs)

    ad_stats = [
        {"banner_id": k, "rendered": v["rendered"], "published": v["published"]}
        for k, v in sorted(ad_counts.items(), key=lambda x: x[1]["rendered"], reverse=True)
    ]

    return {
        "total_projects": len(all_jobs),
        "total_clips": total_clips,
        "published_tiktok": pub_tiktok,
        "published_youtube": pub_youtube,
        "published_instagram": pub_instagram,
        "accounts_count": len(accounts),
        "accounts": accounts,
        "ad_stats": ad_stats,
        "exports_dir": str(EXPORTS_DIR.resolve()),
    }


def create_best_of_60s_clip(job_id: str, options: Dict[str, Any]) -> Dict[str, Any]:
    """Feature #44: Auto-compile the top 8-9 loudest 5.5s laughter/scream bursts into a ~50s Best-Of montage."""
    job = get_job(job_id)
    if not job:
        raise ValueError("Проект не найден")
    jdir = _job_dir(job_id)
    is_remote = job.get("source_type") == "remote"
    total_dur = float((job.get("video_meta") or {}).get("duration") or 0)

    # Collect peak centers from local/lightweight audio if available, otherwise from existing clips
    peaks: List[float] = []
    wav_cand = jdir / "audio.wav"
    if not wav_cand.exists():
        wav_cand = jdir / "light_audio.wav"
    if wav_cand.exists():
        try:
            rms, burst, bsec = compute_audio_features(wav_cand, bin_sec=0.25)
            peaks = _find_audio_peak_times(rms, burst, bsec, top_k=14)
        except Exception:
            peaks = []

    # Space out peaks by at least 7 seconds and keep up to 9 bursts (9 * 5.5s ≈ 49.5s)
    chosen: List[float] = []
    for p in peaks:
        if all(abs(p - c) >= 7.0 for c in chosen):
            chosen.append(p)
        if len(chosen) >= 9:
            break

    # Fallback: take center of each rendered clip if no audio file is present
    if len(chosen) < 2:
        clips = job.get("clips") or []
        if not clips:
            raise ValueError("Нет аудио или готовых клипов для сборки Best-Of")
        chosen = sorted(
            [float(c.get("start", 0)) + float(c.get("duration", 10)) * 0.5 for c in clips[:9]]
        )
    else:
        chosen.sort()

    burst_dur = 5.5
    part_paths: List[Path] = []
    r_kwargs = _extract_render_kwargs(options, "⚡ BEST-OF: ЛУЧШИЕ КРИКИ И СМЕХ")
    r_kwargs["auto_cover"] = False
    r_kwargs["outro_path"] = None
    r_kwargs["enable_subtitles"] = False

    if is_remote:
        remote_url = job.get("remote_url") or ""
        for idx, center in enumerate(chosen, start=1):
            s = max(0.0, center - burst_dur * 0.5)
            e = min(total_dur, s + burst_dur) if total_dur > 0 else (s + burst_dur)
            if e - s < 2.0:
                continue
            raw_p = jdir / f"bestof_raw_{idx}.mp4"
            out_p = jdir / f"bestof_part_{idx}.mp4"
            th_p = jdir / f"bestof_part_{idx}.jpg"
            try:
                download_clip_segment(remote_url, s, e, raw_p)
                seg_d = float(probe_video(raw_p).get("duration") or (e - s))
                render_clip(source_video=raw_p, output_mp4=out_p, thumb_jpg=th_p, clip_start=0.0, clip_end=seg_d, words=[], **r_kwargs)
                part_paths.append(out_p)
            finally:
                raw_p.unlink(missing_ok=True)
                th_p.unlink(missing_ok=True)
    else:
        vpath = Path(job.get("video_path") or "")
        if not vpath.exists():
            raise ValueError("Исходный видеофайл не найден (возможно, он был удалён в менеджере диска)")
        for idx, center in enumerate(chosen, start=1):
            s = max(0.0, center - burst_dur * 0.5)
            e = min(total_dur, s + burst_dur) if total_dur > 0 else (s + burst_dur)
            if e - s < 2.0:
                continue
            out_p = jdir / f"bestof_part_{idx}.mp4"
            th_p = jdir / f"bestof_part_{idx}.jpg"
            render_clip(source_video=vpath, output_mp4=out_p, thumb_jpg=th_p, clip_start=s, clip_end=e, words=[], **r_kwargs)
            part_paths.append(out_p)
            th_p.unlink(missing_ok=True)

    if len(part_paths) < 2:
        raise ValueError("Не удалось собрать достаточно ярких моментов для Best-Of")

    best_id = f"clip_bestof_{int(time.time())}"
    out_mp4 = jdir / f"{best_id}.mp4"
    out_thumb = jdir / f"{best_id}.jpg"
    try:
        merge_clips_compilation(part_paths, out_mp4, out_thumb)
    finally:
        for p in part_paths:
            p.unlink(missing_ok=True)

    meta = probe_video(out_mp4)
    title = f"⚡ BEST-OF: {len(part_paths)} лучших криков и смеха!"
    best_clip = {
        "id": best_id,
        "index": 0,
        "start": 0.0,
        "end": round(float(meta.get("duration") or 0), 2),
        "duration": round(float(meta.get("duration") or 0), 2),
        "title": title,
        "hook_text": title,
        "transcript": f"Авто-нарезка {len(part_paths)} самых громких моментов смеха и эмоций со всего стрима.",
        "viral_score": 99,
        "tags": ["⚡ Best-Of 60с", "😂 Топ смех/крики"],
        "tiktok_caption": generate_tiktok_caption(title, "", ["⚡ Best-Of"], job.get("original_filename", "")),
        "version": int(time.time()),
        "file_size_mb": round(out_mp4.stat().st_size / (1024 * 1024), 2),
        "ad_banner_id": options.get("ad_banner_id") if options.get("enable_ad_banner") else None,
    }
    with _LOCK:
        live_job = _JOBS[job_id]
        live_job.setdefault("clips", []).insert(0, best_clip)
        _save_job(live_job)
    return best_clip


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


def get_job_hype_timeline(job_id: str, num_bins: int = 72) -> Dict[str, Any]:
    """Feature #4: Build a normalized 0..1 visual hype timeline across the whole stream/video."""
    import numpy as np

    job = get_job(job_id)
    if not job:
        raise ValueError("Проект не найден")
    jdir = _job_dir(job_id)
    duration = float((job.get("video_meta") or {}).get("duration") or 0.0)
    if duration <= 1.0:
        return {"duration": 0.0, "bins": [], "source": "none"}

    n = max(20, min(120, int(num_bins)))
    step = duration / n
    bins = [0.0] * n
    sources: List[str] = []

    # 1. Remote heatmap (Twitch chat explosions / YouTube most replayed)
    rm_path = jdir / "remote_meta.json"
    if rm_path.exists():
        try:
            rm = json.loads(rm_path.read_text(encoding="utf-8"))
            hm = rm.get("heatmap") or []
            if hm:
                sources.append("чат/пересмотры")
                for h in hm:
                    hs = float(h.get("start_time", 0.0))
                    he = float(h.get("end_time", hs + 10.0))
                    val = float(h.get("value", 0.0))
                    i0 = max(0, min(n - 1, int(hs / step)))
                    i1 = max(i0, min(n - 1, int(he / step)))
                    for i in range(i0, i1 + 1):
                        bins[i] = max(bins[i], val)
        except Exception:
            pass

    # 2. Acoustic audio energy (local audio.wav or remote light_audio.wav)
    wav_p = jdir / "audio.wav"
    if not wav_p.exists():
        wav_p = jdir / "light_audio.wav"
    if wav_p.exists():
        try:
            rms, burst, bsec = compute_audio_features(wav_p, bin_sec=0.5)
            if len(rms) >= 4:
                sources.append("смех/крики")
                comb = 0.45 * (rms / (float(np.median(rms)) + 1e-6)) + 0.55 * (burst / (float(np.median(burst)) + 1e-6))
                p96 = float(np.percentile(comb, 96)) or 1.0
                for i in range(n):
                    a0 = max(0, int((i * step) / bsec))
                    a1 = min(len(comb), max(a0 + 1, int(((i + 1) * step) / bsec)))
                    v = min(1.0, float(np.max(comb[a0:a1])) / max(p96, 1e-5))
                    bins[i] = max(bins[i], round(v, 3)) if sources[0] != "смех/крики" else round(v, 3)
        except Exception:
            pass

    # 3. Fallback: highlight clips scores
    if not sources and job.get("clips"):
        sources.append("клипы")
        for c in job["clips"]:
            cs = float(c.get("start", 0))
            ce = float(c.get("end", cs + 10))
            sc = min(1.0, max(0.2, (float(c.get("viral_score", 70)) - 40) / 60.0))
            i0 = max(0, min(n - 1, int(cs / step)))
            i1 = max(i0, min(n - 1, int(ce / step)))
            for i in range(i0, i1 + 1):
                bins[i] = max(bins[i], sc)

    out_bins = [
        {"t": round((i + 0.5) * step, 1), "value": round(min(1.0, max(0.0, bins[i])), 3)}
        for i in range(n)
    ]
    return {"duration": round(duration, 2), "bins": out_bins, "source": " + ".join(sources) or "none"}


def toggle_clip_favorite(job_id: str, clip_id: str) -> Optional[Dict[str, Any]]:
    """Feature #12 (v3.1): Star/unstar favorite clips."""
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        updated = None
        for c in job.get("clips") or []:
            if c.get("id") == clip_id:
                c["favorite"] = not bool(c.get("favorite", False))
                updated = dict(c)
                break
        if updated is not None:
            _save_job(job)
    return updated


def get_clip_srt(job_id: str, clip_id: str) -> str:
    """Feature #18 (v3.1): Export time-aligned .SRT subtitles for CapCut / Premiere Pro."""
    job = get_job(job_id)
    if not job:
        raise ValueError("Проект не найден")
    clip = next((c for c in (job.get("clips") or []) if c.get("id") == clip_id), None)
    if not clip:
        raise ValueError("Клип не найден")
    jdir = _job_dir(job_id)
    words = []
    # Check clip-specific words first (remote), then job-level words.json (local)
    clip_w_path = jdir / f"{clip_id}_words.json"
    job_w_path = jdir / "words.json"
    if clip_w_path.exists():
        try:
            words = json.loads(clip_w_path.read_text(encoding="utf-8"))
        except Exception:
            words = []
        return build_clip_srt(words, 0.0, float(clip.get("duration") or 30.0), clip.get("transcript", ""))
    if job_w_path.exists():
        try:
            words = json.loads(job_w_path.read_text(encoding="utf-8")).get("words", [])
        except Exception:
            words = []
    return build_clip_srt(words, float(clip.get("start") or 0.0), float(clip.get("end") or 30.0), clip.get("transcript", ""))


def multi_render_clip_for_accounts(job_id: str, clip_id: str, base_options: Dict[str, Any]) -> Dict[str, Any]:
    """Feature #15 (v3.1): Render 1 winning clip into unique versions for ALL studio accounts in 1 click!"""
    job = get_job(job_id)
    if not job:
        raise ValueError("Проект не найден")
    clip = next((c for c in (job.get("clips") or []) if c.get("id") == clip_id), None)
    if not clip:
        raise ValueError("Клип не найден")
    accounts = list_accounts()
    if not accounts:
        raise ValueError("Сначала создайте хотя бы один аккаунт в верхней панели студии")

    jdir = _job_dir(job_id)
    raw_seg = Path(clip.get("raw_segment_path") or "")
    if raw_seg.exists():
        src_video = raw_seg
        s_t = float(clip.get("trim_start") or 0.0)
        e_t = float(clip.get("trim_end") or clip.get("duration") or 30.0)
    else:
        src_video = Path(job.get("video_path") or "")
        if not src_video.exists():
            raise ValueError("Исходное видео для перерендера не найдено")
        s_t = float(clip.get("start") or 0.0)
        e_t = float(clip.get("end") or 30.0)

    words = []
    job_w = jdir / "words.json"
    if job_w.exists():
        try:
            words = json.loads(job_w.read_text(encoding="utf-8")).get("words", [])
        except Exception:
            words = []

    out_dir = EXPORTS_DIR / f"MultiAccount_{job_id}_{clip_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    cap_lines: List[str] = []
    rendered_accs: List[str] = []

    for acc in accounts:
        merged_opts = dict(base_options)
        merged_opts.update(acc.get("preset") or {})
        merged_opts["uniquify_video"] = True
        if acc.get("handle") and not merged_opts.get("watermark_text"):
            merged_opts["watermark_text"] = acc["handle"]

        safe_acc = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ _-]+", "", acc.get("name") or "Account").strip() or "Account"
        out_mp4 = out_dir / f"{safe_acc}_{clip_id}.mp4"
        out_thumb = out_dir / f"{safe_acc}_{clip_id}.jpg"
        r_kwargs = _extract_render_kwargs(merged_opts, clip.get("hook_text") or clip.get("title") or "")
        render_clip(
            source_video=src_video,
            output_mp4=out_mp4,
            thumb_jpg=out_thumb,
            clip_start=s_t,
            clip_end=e_t,
            words=words,
            **r_kwargs,
        )
        rendered_accs.append(acc.get("name") or safe_acc)
        tpl = acc.get("caption_template") or "{title} 🔥\n\n{hashtags}"
        cap = tpl.replace("{title}", clip.get("title") or "").replace("{hashtags}", acc.get("default_hashtags") or "")
        cap_lines.append(f"=== {acc.get('name')} ({acc.get('handle') or ''}) ===\n{cap}\n")

    (out_dir / "captions_by_account.txt").write_text("\n".join(cap_lines), encoding="utf-8")
    return {"folder": str(out_dir.resolve()), "count": len(rendered_accs), "accounts": rendered_accs}


def start_twitch_clips_batch_job(
    clips_list: List[Dict[str, Any]],
    options: Dict[str, Any],
) -> Dict[str, Any]:
    """
    v3.2.0: Download, transcribe, and render a batch of selected Twitch clips (or short URLs)
    into ONE unified project so all clips appear together in one gallery, ZIP, folder export & Telegram!
    """
    clean_clips = [c for c in (clips_list or []) if (c.get("url") or "").strip().startswith(("http://", "https://"))][:20]
    if not clean_clips:
        raise ValueError("Выберите хотя бы один клип для пакетного рендера")

    job_id = f"pack_{int(time.time())}"
    first_streamer = (clean_clips[0].get("streamer") or "Twitch").strip()
    total_dur = sum(float(c.get("duration") or 30.0) for c in clean_clips)
    job = {
        "job_id": job_id,
        "source_type": "remote_pack",
        "original_filename": f"📦 Пачка клипов ({len(clean_clips)} шт. • {first_streamer})",
        "video_path": None,
        "remote_url": clean_clips[0]["url"],
        "video_meta": {
            "duration": round(total_dur, 1),
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "thumbnail": clean_clips[0].get("thumbnail") or "",
        },
        "status": "processing",
        "stage": "starting",
        "progress": 2,
        "message": f"Пакетный рендер {len(clean_clips)} выбранных клипов...",
        "options": dict(options),
        "clips": [],
        "words_count": 0,
        "error": None,
        "created_at": time.time(),
    }
    with _LOCK:
        _CANCELLED_JOBS.discard(job_id)
        _JOBS[job_id] = job
        _save_job(job)

    def _worker() -> None:
        try:
            jdir = _job_dir(job_id)
            whisper_model = options.get("whisper_model", "small")
            rendered_clips: List[Dict[str, Any]] = []
            total_words = 0
            n_total = len(clean_clips)

            # STAGE 1: Parallel download ALL selected Twitch clips at once (up to 4 simultaneous!)
            _update_job(
                job_id,
                stage="extracting_audio",
                progress=5,
                message=f"⬇️ Параллельная загрузка всех {n_total} выбранных клипов сразу...",
            )
            downloaded_items: Dict[int, Path] = {}

            def _dl_pack_item(pair):
                idx_1, it = pair
                if is_job_cancelled(job_id):
                    return idx_1, None
                c_id = f"clip_{idx_1:02d}"
                c_url = it["url"].strip()
                c_dur = float(it.get("duration") or 45.0)
                dest = jdir / f"raw_seg_{c_id}.mp4"
                for dl_try in range(2):
                    try:
                        p = download_clip_segment(c_url, 0.0, max(5.0, c_dur + 2.0), dest)
                        if p.exists() and p.stat().st_size > 10_000:
                            return idx_1, p
                    except Exception as dl_err:
                        print(f"[batch_pack] clip {idx_1} download try {dl_try + 1} failed: {dl_err}")
                        time.sleep(1.2)
                return idx_1, None

            dl_count = 0
            with ThreadPoolExecutor(max_workers=min(4, n_total)) as dl_pool:
                for idx_1, p_path in dl_pool.map(_dl_pack_item, enumerate(clean_clips, start=1)):
                    dl_count += 1
                    if p_path is not None:
                        downloaded_items[idx_1] = p_path
                    _update_job(
                        job_id,
                        stage="extracting_audio",
                        progress=int(5 + (dl_count / n_total) * 25),
                        message=f"⬇️ Скачано клипов: {dl_count}/{n_total} (параллельно)...",
                    )

            # STAGE 2: Transcribe & render all downloaded clips
            for idx, item in enumerate(clean_clips, start=1):
                if is_job_cancelled(job_id):
                    _update_job(job_id, status="cancelled", stage="cancelled", message="⏹ Пакетный рендер остановлен.", clips=rendered_clips)
                    return

                raw_seg_path = downloaded_items.get(idx)
                if not raw_seg_path:
                    continue

                clip_id = f"clip_{idx:02d}"
                base_pct = int(30 + ((idx - 1) / n_total) * 66)
                c_title = (item.get("title") or f"Клип #{idx}").strip()
                c_dur = float(item.get("duration") or 45.0)

                seg_meta = probe_video(raw_seg_path)
                seg_dur = float(seg_meta.get("duration") or c_dur or 20.0)

                clip_words: List[Dict[str, Any]] = []
                transcript_txt = ""
                if options.get("enable_subtitles", True):
                    _update_job(
                        job_id,
                        stage="transcribing",
                        progress=min(96, base_pct + int(25 / n_total)),
                        message=f"Клип {idx}/{n_total}: распознавание субтитров (Whisper)...",
                    )
                    seg_wav = jdir / f"seg_{clip_id}.wav"
                    try:
                        extract_audio_wav(raw_seg_path, seg_wav)
                        _, clip_words = transcribe_russian(seg_wav, total_duration=seg_dur, model_size=whisper_model)
                        transcript_txt = " ".join(w["word"] for w in clip_words).strip()
                        total_words += len(clip_words)
                        (jdir / f"{clip_id}_words.json").write_text(json.dumps(clip_words, ensure_ascii=False), encoding="utf-8")
                    except Exception as tr_err:
                        print(f"[batch_pack] transcribe error on {clip_id}: {tr_err}")
                    finally:
                        seg_wav.unlink(missing_ok=True)

                _update_job(
                    job_id,
                    stage="rendering",
                    progress=min(97, base_pct + int(50 / n_total)),
                    message=f"Клип {idx}/{n_total}: рендер 9:16 «{c_title[:36]}»...",
                )
                out_mp4 = jdir / f"{clip_id}.mp4"
                out_thumb = jdir / f"{clip_id}.jpg"
                r_kwargs = _extract_render_kwargs(options, c_title)
                try:
                    render_clip(
                        source_video=raw_seg_path,
                        output_mp4=out_mp4,
                        thumb_jpg=out_thumb,
                        clip_start=0.0,
                        clip_end=seg_dur,
                        words=clip_words,
                        **r_kwargs,
                    )
                except Exception as ren_err:
                    print(f"[batch_pack] render error on {clip_id}: {ren_err}")
                    continue
                if not out_mp4.exists() or out_mp4.stat().st_size < 10_000:
                    continue

                tags = ["📦 Пачка клипов"]
                if item.get("streamer"):
                    tags.append(f"🎮 {item['streamer']}")
                hl_out = {
                    "id": clip_id,
                    "index": idx,
                    "start": 0.0,
                    "end": round(seg_dur, 2),
                    "duration": round(seg_dur, 2),
                    "title": c_title,
                    "hook_text": c_title,
                    "transcript": transcript_txt,
                    "viral_score": min(99, max(82, 85 + min(14, int(item.get("views", 0) / 2000)))),
                    "tags": tags,
                    "tiktok_caption": generate_tiktok_caption(c_title, transcript_txt, tags, item.get("streamer", "")),
                    "raw_segment_path": str(raw_seg_path),
                    "raw_segment_duration": round(seg_dur, 2),
                    "trim_start": 0.0,
                    "trim_end": round(seg_dur, 2),
                    "version": int(time.time()),
                    "file_size_mb": round(out_mp4.stat().st_size / (1024 * 1024), 2),
                    "ad_banner_id": options.get("ad_banner_id") if options.get("enable_ad_banner") else None,
                }
                rendered_clips.append(hl_out)
                _update_job(job_id, clips=rendered_clips, words_count=total_words)

            tg_sent = _auto_send_clips_to_telegram(job_id, rendered_clips, options)
            tg_note = f" • ✈️ Отправлено в Telegram: {tg_sent}" if tg_sent > 0 else ""
            _update_job(
                job_id,
                status="completed",
                stage="completed",
                progress=100,
                message=f"Готово! Пачка из {len(rendered_clips)} клипов 9:16 собрана.{tg_note}",
                clips=rendered_clips,
                words_count=total_words,
            )
        except Exception as exc:
            traceback.print_exc()
            _update_job(job_id, status="failed", stage="failed", error=str(exc), message=f"Ошибка пакетного рендера: {exc}")

    threading.Thread(target=_worker, daemon=True).start()
    return dict(job)
