"""FastAPI web application for TikCut Studio — local 9:16 TikTok clipper."""
import re
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.accounts import (
    create_account,
    delete_account,
    get_account,
    increment_published,
    list_accounts,
    update_account,
)
from backend.config import (
    ADS_DIR,
    AVATARS_DIR,
    BASE_DIR,
    CUSTOM_FONTS_DIR,
    EXPORTS_DIR,
    FONTS_DIR,
    JOBS_DIR,
    LOGOS_DIR,
    MUSIC_DIR,
    OUTROS_DIR,
    SATISFYING_DIR,
    STATIC_DIR,
    UPLOADS_DIR,
    get_available_fonts,
    get_subtitle_styles,
    load_settings,
    save_settings,
)
from backend.gemini_client import clean_api_key, test_gemini_key
from backend.hardware import get_hardware_info
from backend.pipeline import (
    cancel_job,
    create_best_of_60s_clip,
    create_compilation_clip,
    create_custom_clip,
    create_job,
    delete_clip,
    delete_job,
    export_job_to_account_folder,
    get_batch_status,
    get_clip_srt,
    get_job,
    get_job_hype_timeline,
    get_studio_dashboard_stats,
    list_jobs,
    load_existing_jobs,
    mark_clip_published,
    multi_render_clip_for_accounts,
    rerender_single_clip,
    start_batch_urls,
    start_processing,
    toggle_clip_favorite,
    update_clip_title,
)
from backend.remote import _apply_network_opts, probe_remote_url
from backend.renderer import extract_preview_frame, probe_video
from backend.studio_extras import (
    add_plan_item,
    auto_cleanup_old_audio,
    cleanup_old_sources,
    cleanup_temp_cache,
    create_studio_backup_zip,
    delete_asset_file,
    delete_plan_item,
    get_disk_usage_stats,
    list_plan_items,
    restore_studio_backup_zip,
    self_heal_startup,
    update_plan_item,
)
from backend.telegram_export import (
    pull_settings_from_telegram,
    push_settings_to_telegram,
    send_clip_to_telegram,
    test_telegram_connection,
)
from backend.twitch_radar import capture_live_stream_clip, fetch_twitch_top_clips, resolve_clip_preview_url

app = FastAPI(title="TikCut Studio", version="1.0.0")

# Mount static assets and bundled fonts so live UI preview uses the exact same TTFs
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/fonts", StaticFiles(directory=str(FONTS_DIR)), name="fonts")


@app.on_event("startup")
def _startup() -> None:
    load_existing_jobs()
    import threading
    threading.Thread(target=self_heal_startup, daemon=True).start()
    # Feature #15: Auto-clean old intermediate WAV files (> 24h) on startup if enabled (default True)
    cfg = load_settings()
    if cfg.get("auto_clean_wav", True):
        threading.Thread(target=auto_cleanup_old_audio, args=(24,), daemon=True).start()


class ProcessRequest(BaseModel):
    clip_count: int = Field(default=6, ge=1, le=30)
    min_duration: float = Field(default=20.0, ge=8.0, le=90.0)
    max_duration: float = Field(default=55.0, ge=15.0, le=120.0)
    whisper_model: str = Field(default="small")
    subtitle_style: str = Field(default="hormozi")
    font_id: str = Field(default="montserrat")
    font_size: str = Field(default="medium")
    crop_mode: str = Field(default="fill")
    position: str = Field(default="lower_third")
    uppercase: Optional[bool] = Field(default=None)
    enable_subtitles: bool = Field(default=True)
    webcam_corner: str = Field(default="bottom_left")
    webcam_size: float = Field(default=0.28, ge=0.18, le=0.45)
    use_webcam_photo: bool = Field(default=False)
    webcam_image_id: Optional[str] = Field(default=None)
    show_hook_banner: bool = Field(default=True)
    hook_position: str = Field(default="between")
    hook_text_color: str = Field(default="#0C0E18")
    hook_bg_color: Optional[str] = Field(default="#FFFFFF")
    hook_border_color: str = Field(default="#FFE600")
    hook_font_size: str = Field(default="medium")
    watermark_text: Optional[str] = Field(default=None)
    watermark_opacity: float = Field(default=0.55, ge=0.15, le=1.0)
    watermark_logo_id: Optional[str] = Field(default=None)
    jump_cuts: bool = Field(default=False)
    bg_music_id: Optional[str] = Field(default=None)
    bg_music_volume: float = Field(default=0.18, ge=0.05, le=0.5)
    target_fps: int = Field(default=30)
    video_enhance: bool = Field(default=False)
    enable_ad_banner: bool = Field(default=False)
    ad_mode: str = Field(default="bottom_overlay")
    ad_banner_id: Optional[str] = Field(default=None)
    ad_audio_id: Optional[str] = Field(default=None)
    enable_satisfying_video: bool = Field(default=False)
    satisfying_video_id: Optional[str] = Field(default=None)
    uniquify_video: bool = Field(default=False)
    auto_cover: bool = Field(default=False)
    webcam_rect: Optional[Dict[str, float]] = Field(default=None)
    blur_rect: Optional[Dict[str, float]] = Field(default=None)
    low_cpu_mode: bool = Field(default=False)
    tg_auto_send: Optional[bool] = Field(default=None)
    enable_outro: bool = Field(default=False)
    outro_id: Optional[str] = Field(default=None)
    manual_timecodes: Optional[str] = Field(default=None)
    search_chat_activity: bool = Field(default=True)
    search_laughter: bool = Field(default=True)
    search_screams: bool = Field(default=True)
    use_ai_director: bool = Field(default=True)
    shuffle_seed: int = Field(default=0)
    ollama_model: Optional[str] = Field(default=None)
    gemini_api_key: Optional[str] = Field(default=None)


class RerenderRequest(BaseModel):
    subtitle_style: str = Field(default="hormozi")
    font_id: str = Field(default="montserrat")
    font_size: str = Field(default="medium")
    crop_mode: str = Field(default="fill")
    position: str = Field(default="lower_third")
    uppercase: Optional[bool] = Field(default=None)
    enable_subtitles: bool = Field(default=True)
    webcam_corner: str = Field(default="bottom_left")
    webcam_size: float = Field(default=0.28, ge=0.18, le=0.45)
    use_webcam_photo: bool = Field(default=False)
    webcam_image_id: Optional[str] = Field(default=None)
    show_hook_banner: bool = Field(default=True)
    hook_position: str = Field(default="between")
    hook_text_color: str = Field(default="#0C0E18")
    hook_bg_color: Optional[str] = Field(default="#FFFFFF")
    hook_border_color: str = Field(default="#FFE600")
    hook_font_size: str = Field(default="medium")
    watermark_text: Optional[str] = Field(default=None)
    watermark_opacity: float = Field(default=0.55, ge=0.15, le=1.0)
    watermark_logo_id: Optional[str] = Field(default=None)
    jump_cuts: bool = Field(default=False)
    bg_music_id: Optional[str] = Field(default=None)
    bg_music_volume: float = Field(default=0.18, ge=0.05, le=0.5)
    target_fps: int = Field(default=30)
    video_enhance: bool = Field(default=False)
    enable_ad_banner: bool = Field(default=False)
    ad_mode: str = Field(default="bottom_overlay")
    ad_banner_id: Optional[str] = Field(default=None)
    ad_audio_id: Optional[str] = Field(default=None)
    enable_satisfying_video: bool = Field(default=False)
    satisfying_video_id: Optional[str] = Field(default=None)
    uniquify_video: bool = Field(default=False)
    auto_cover: bool = Field(default=False)
    webcam_rect: Optional[Dict[str, float]] = Field(default=None)
    blur_rect: Optional[Dict[str, float]] = Field(default=None)
    low_cpu_mode: bool = Field(default=False)
    tg_auto_send: Optional[bool] = Field(default=None)
    enable_outro: bool = Field(default=False)
    outro_id: Optional[str] = Field(default=None)
    edited_transcript: Optional[str] = Field(default=None)
    edited_hook_text: Optional[str] = Field(default=None)
    trim_start: Optional[float] = Field(default=None)
    trim_end: Optional[float] = Field(default=None)
    source_start: Optional[float] = Field(default=None)
    source_end: Optional[float] = Field(default=None)
    whisper_model: str = Field(default="small")


class ProbeUrlRequest(BaseModel):
    url: str = Field(..., min_length=8)


class CheckGeminiKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=5)


class SettingsUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    watermark_text: Optional[str] = None
    yt_proxy: Optional[str] = None
    yt_cookies_browser: Optional[str] = None
    low_cpu_mode: Optional[bool] = None
    auto_clean_wav: Optional[bool] = None
    tg_bot_token: Optional[str] = None
    tg_chat_id: Optional[str] = None
    tg_auto_send: Optional[bool] = None
    favorite_streamers: Optional[List[str]] = None


@app.get("/api/settings")
def api_get_settings() -> Dict[str, Any]:
    return load_settings()


@app.post("/api/settings")
def api_save_settings(req: SettingsUpdateRequest) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    if req.gemini_api_key is not None:
        updates["gemini_api_key"] = clean_api_key(req.gemini_api_key)
    if req.watermark_text is not None:
        updates["watermark_text"] = req.watermark_text.strip()
    if req.yt_proxy is not None:
        updates["yt_proxy"] = req.yt_proxy.strip()
    if req.yt_cookies_browser is not None:
        updates["yt_cookies_browser"] = req.yt_cookies_browser.strip().lower()
    if req.low_cpu_mode is not None:
        updates["low_cpu_mode"] = bool(req.low_cpu_mode)
    if req.auto_clean_wav is not None:
        updates["auto_clean_wav"] = bool(req.auto_clean_wav)
    if req.tg_bot_token is not None:
        updates["tg_bot_token"] = req.tg_bot_token.strip()
    if req.tg_chat_id is not None:
        updates["tg_chat_id"] = req.tg_chat_id.strip()
    if req.tg_auto_send is not None:
        updates["tg_auto_send"] = bool(req.tg_auto_send)
    if req.favorite_streamers is not None:
        updates["favorite_streamers"] = [s.strip().lower() for s in req.favorite_streamers if s and s.strip()][:20]
    return save_settings(updates)


@app.post("/api/check-gemini-key")
def api_check_gemini_key(req: CheckGeminiKeyRequest) -> Dict[str, Any]:
    key = clean_api_key(req.api_key)
    result = test_gemini_key(key)
    if result.get("ok"):
        save_settings({"gemini_api_key": key})
    return result


@app.get("/api/health")
def api_health() -> Dict[str, Any]:
    return {"ok": True, "app": "TikCut Studio"}


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


class AccountCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=40)
    handle: str = Field(default="")
    color: str = Field(default="#7c5cff")
    default_hashtags: str = Field(default="#нарезки #тикток #стрим #рекомендации #shorts")
    caption_template: str = Field(default="{title} 🔥\n\n{hashtags}")
    preset: Dict[str, Any] = Field(default_factory=dict)


class AccountUpdateRequest(BaseModel):
    name: Optional[str] = None
    handle: Optional[str] = None
    color: Optional[str] = None
    default_hashtags: Optional[str] = None
    caption_template: Optional[str] = None
    preset: Optional[Dict[str, Any]] = None


class MarkPublishedRequest(BaseModel):
    account_id: str
    account_name: str = ""
    platform: str = "tiktok"


class CompilationRequest(BaseModel):
    clip_ids: List[str]
    title: str = ""


class ExportFolderRequest(BaseModel):
    account_name: str = "General"


@app.get("/api/accounts")
def api_list_accounts() -> Dict[str, Any]:
    return {"accounts": list_accounts()}


@app.post("/api/accounts")
def api_create_account(req: AccountCreateRequest) -> Dict[str, Any]:
    return create_account(
        name=req.name,
        handle=req.handle,
        color=req.color,
        default_hashtags=req.default_hashtags,
        caption_template=req.caption_template,
        preset=req.preset,
    )


@app.put("/api/accounts/{account_id}")
def api_update_account(account_id: str, req: AccountUpdateRequest) -> Dict[str, Any]:
    updated = update_account(account_id, req.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    return updated


@app.delete("/api/accounts/{account_id}")
def api_delete_account(account_id: str) -> Dict[str, Any]:
    if not delete_account(account_id):
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    return {"ok": True}


@app.get("/api/jobs/{job_id}/clips/{clip_id}/path")
def api_clip_local_path(job_id: str, clip_id: str) -> Dict[str, Any]:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", job_id) or not re.fullmatch(r"[a-zA-Z0-9_-]+", clip_id):
        raise HTTPException(status_code=400, detail="Некорректный идентификатор")
    mp4_path = JOBS_DIR / job_id / f"{clip_id}.mp4"
    if not mp4_path.exists():
        raise HTTPException(status_code=404, detail="Клип не найден")
    return {"path": str(mp4_path.resolve())}


@app.post("/api/jobs/{job_id}/clips/{clip_id}/mark-published")
def api_mark_clip_published(job_id: str, clip_id: str, req: MarkPublishedRequest) -> Dict[str, Any]:
    updated = mark_clip_published(job_id, clip_id, req.account_id, req.account_name, req.platform)
    if not updated:
        raise HTTPException(status_code=404, detail="Клип не найден")
    increment_published(req.account_id)
    return updated


@app.post("/api/jobs/{job_id}/compile")
def api_compile_clips(job_id: str, req: CompilationRequest) -> Dict[str, Any]:
    try:
        return create_compilation_clip(job_id, req.clip_ids, req.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка склейки: {exc}")


@app.post("/api/jobs/{job_id}/export-folder")
def api_export_folder(job_id: str, req: ExportFolderRequest) -> Dict[str, Any]:
    try:
        return export_job_to_account_folder(job_id, req.account_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка экспорта: {exc}")


@app.get("/api/dashboard")
def api_dashboard() -> Dict[str, Any]:
    return get_studio_dashboard_stats()


@app.get("/api/satisfying")
def api_list_satisfying() -> Dict[str, Any]:
    items = []
    for p in sorted(SATISFYING_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}:
            items.append({"id": p.name, "name": p.stem})
    return {"videos": items}


@app.post("/api/satisfying")
async def api_upload_satisfying(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Видео не выбрано")
    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp4", ".mov", ".mkv", ".webm"}:
        raise HTTPException(status_code=400, detail="Поддерживаются форматы: MP4, MOV, MKV, WEBM")
    safe_stem = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ _-]+", "", Path(file.filename).stem).strip()[:40] or "satisfying"
    fname = f"sat_{safe_stem}_{uuid.uuid4().hex[:6]}{ext}"
    dest = SATISFYING_DIR / fname
    with dest.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    return {"id": fname, "name": safe_stem}


@app.get("/api/config")
def api_config() -> Dict[str, Any]:
    return {
        "fonts": get_available_fonts(),
        "styles": get_subtitle_styles(),
        "hardware": get_hardware_info(),
        "settings": load_settings(),
    }


@app.get("/api/hardware")
def api_hardware() -> Dict[str, Any]:
    return get_hardware_info(force_refresh=True)


def _parse_changelog_md(text: str) -> Dict[str, Any]:
    releases = []
    cur_rel = None
    cur_sec = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        m_rel = re.match(r"^##\s+\[([^\]]+)\]\s*(?:[—–-]\s*(.+))?$", line)
        if m_rel:
            cur_rel = {
                "version": m_rel.group(1).strip(),
                "date": (m_rel.group(2) or "").strip(),
                "sections": [],
            }
            releases.append(cur_rel)
            cur_sec = None
            continue

        m_sec = re.match(r"^###\s+(.+)$", line)
        if m_sec and cur_rel is not None:
            cur_sec = {"title": m_sec.group(1).strip(), "items": []}
            cur_rel["sections"].append(cur_sec)
            continue

        m_item = re.match(r"^(\s*)-\s+(.+)$", line)
        if m_item and cur_sec is not None:
            indent = len(m_item.group(1))
            cur_sec["items"].append({"text": m_item.group(2).strip(), "sub": indent >= 2})

    return {"releases": releases}


@app.get("/api/changelog")
def api_changelog() -> Dict[str, Any]:
    cl_path = BASE_DIR / "CHANGELOG.md"
    if not cl_path.exists():
        return {"releases": []}
    return _parse_changelog_md(cl_path.read_text(encoding="utf-8"))


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не выбран")

    ext = Path(file.filename).suffix.lower() or ".mp4"
    if ext not in {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}:
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются видеоформаты: MP4, MOV, MKV, WEBM, M4V, AVI",
        )

    job_id = uuid.uuid4().hex[:10]
    saved_path = UPLOADS_DIR / f"{job_id}{ext}"

    try:
        with saved_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    except Exception as exc:
        if saved_path.exists():
            saved_path.unlink()
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения файла: {exc}")

    try:
        meta = probe_video(saved_path)
    except Exception as exc:
        if saved_path.exists():
            saved_path.unlink()
        raise HTTPException(status_code=400, detail=f"Не удалось прочитать видео: {exc}")

    job = create_job(
        job_id=job_id,
        original_filename=file.filename,
        video_path=saved_path,
        video_meta=meta,
        source_type="file",
    )
    return job


@app.post("/api/probe-url")
def api_probe_url(req: ProbeUrlRequest) -> Dict[str, Any]:
    url = req.url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="Введите корректную ссылку (https://...)")
    try:
        info = probe_remote_url(url)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Не удалось проанализировать ссылку: {exc}",
        )

    job_id = uuid.uuid4().hex[:10]
    video_meta = {
        "duration": info["duration"],
        "width": info["width"],
        "height": info["height"],
        "fps": info["fps"],
        "has_audio": True,
        "uploader": info["uploader"],
        "extractor": info["extractor"],
        "thumbnail": info["thumbnail"],
        "has_heatmap": info["has_heatmap"],
        "has_twitch_chat": info.get("has_twitch_chat", False),
        "has_captions": info["has_captions"],
    }
    job = create_job(
        job_id=job_id,
        original_filename=info["title"],
        video_path=None,
        video_meta=video_meta,
        source_type="url",
        remote_url=info["url"],
        remote_meta=info,
    )
    return job


@app.post("/api/process/{job_id}")
def api_process(job_id: str, req: ProcessRequest) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Проект не найден")
    if job["status"] == "processing":
        raise HTTPException(status_code=409, detail="Проект уже обрабатывается")
    if req.max_duration < req.min_duration:
        raise HTTPException(status_code=400, detail="Макс. длина должна быть больше мин. длины")

    start_processing(job_id, req.model_dump())
    return get_job(job_id) or {}


@app.get("/api/jobs")
def api_list_jobs() -> Dict[str, Any]:
    return {"jobs": list_jobs()}


@app.get("/api/jobs/{job_id}")
def api_get_job(job_id: str) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return job


@app.get("/api/jobs/{job_id}/clips/{clip_id}/video")
def api_clip_video(job_id: str, clip_id: str) -> FileResponse:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", job_id) or not re.fullmatch(r"[a-zA-Z0-9_-]+", clip_id):
        raise HTTPException(status_code=400, detail="Некорректный идентификатор")
    mp4_path = JOBS_DIR / job_id / f"{clip_id}.mp4"
    if not mp4_path.exists():
        raise HTTPException(status_code=404, detail="Клип не найден")
    return FileResponse(path=str(mp4_path), media_type="video/mp4")


@app.get("/api/jobs/{job_id}/clips/{clip_id}/thumb")
def api_clip_thumb(job_id: str, clip_id: str) -> FileResponse:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", job_id) or not re.fullmatch(r"[a-zA-Z0-9_-]+", clip_id):
        raise HTTPException(status_code=400, detail="Некорректный идентификатор")
    jpg_path = JOBS_DIR / job_id / f"{clip_id}.jpg"
    if not jpg_path.exists():
        raise HTTPException(status_code=404, detail="Превью не найдено")
    return FileResponse(path=str(jpg_path), media_type="image/jpeg")


@app.get("/api/jobs/{job_id}/clips/{clip_id}/download")
def api_clip_download(job_id: str, clip_id: str) -> FileResponse:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", job_id) or not re.fullmatch(r"[a-zA-Z0-9_-]+", clip_id):
        raise HTTPException(status_code=400, detail="Некорректный идентификатор")
    mp4_path = JOBS_DIR / job_id / f"{clip_id}.mp4"
    if not mp4_path.exists():
        raise HTTPException(status_code=404, detail="Клип не найден")
    filename = f"tikcut_{job_id}_{clip_id}_9x16.mp4"
    return FileResponse(
        path=str(mp4_path),
        media_type="video/mp4",
        filename=filename,
    )


@app.get("/api/music")
def api_list_music() -> Dict[str, Any]:
    tracks: List[Dict[str, Any]] = []
    for p in sorted(MUSIC_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg", ".flac"}:
            tracks.append({"id": p.name, "name": p.stem})
    return {"tracks": tracks}


@app.post("/api/music")
async def api_upload_music(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Аудиофайл не выбран")
    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp3", ".wav", ".m4a", ".ogg", ".flac"}:
        raise HTTPException(status_code=400, detail="Поддерживаются форматы: MP3, WAV, M4A, OGG")
    safe_stem = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ _-]+", "", Path(file.filename).stem).strip()[:40] or "track"
    fname = f"{safe_stem}_{uuid.uuid4().hex[:6]}{ext}"
    dest = MUSIC_DIR / fname
    with dest.open("wb") as out:
        while True:
            chunk = await file.read(512 * 1024)
            if not chunk:
                break
            out.write(chunk)
    return {"id": fname, "name": safe_stem}


@app.get("/api/avatars")
def api_list_avatars() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for p in sorted(AVATARS_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            items.append({"id": p.name, "name": p.stem, "url": f"/api/avatars/{p.name}"})
    return {"avatars": items}


@app.post("/api/avatars")
async def api_upload_avatar(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Фото не выбрано")
    ext = Path(file.filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="Поддерживаются форматы: PNG, JPG, WEBP")
    safe_stem = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ _-]+", "", Path(file.filename).stem).strip()[:40] or "streamer"
    fname = f"{safe_stem}_{uuid.uuid4().hex[:6]}{ext}"
    dest = AVATARS_DIR / fname
    with dest.open("wb") as out:
        while True:
            chunk = await file.read(512 * 1024)
            if not chunk:
                break
            out.write(chunk)
    return {"id": fname, "name": safe_stem, "url": f"/api/avatars/{fname}"}


@app.get("/api/avatars/{avatar_id}")
def api_get_avatar(avatar_id: str) -> FileResponse:
    safe_name = Path(avatar_id).name
    p = AVATARS_DIR / safe_name
    if not p.exists():
        raise HTTPException(status_code=404, detail="Фото не найдено")
    return FileResponse(path=str(p))


@app.get("/api/ads")
def api_list_ads() -> Dict[str, Any]:
    banners: List[Dict[str, Any]] = []
    audios: List[Dict[str, Any]] = []
    for p in sorted(ADS_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        ext = p.suffix.lower()
        if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            banners.append({"id": p.name, "name": p.stem, "url": f"/api/ads/{p.name}"})
        elif ext in {".mp3", ".wav", ".m4a", ".ogg", ".flac"}:
            dur = 0.0
            try:
                dur = float(probe_video(p).get("duration") or 0.0)
            except Exception:
                pass
            audios.append({"id": p.name, "name": p.stem, "duration": round(dur, 1)})
    return {"banners": banners, "audios": audios}


@app.post("/api/ads/banner")
async def api_upload_ad_banner(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Баннер не выбран")
    ext = Path(file.filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        raise HTTPException(status_code=400, detail="Поддерживаются форматы баннера: PNG, JPG, WEBP, GIF")
    safe_stem = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ _-]+", "", Path(file.filename).stem).strip()[:40] or "banner"
    fname = f"banner_{safe_stem}_{uuid.uuid4().hex[:6]}{ext}"
    dest = ADS_DIR / fname
    with dest.open("wb") as out:
        while True:
            chunk = await file.read(512 * 1024)
            if not chunk:
                break
            out.write(chunk)
    return {"id": fname, "name": safe_stem, "url": f"/api/ads/{fname}"}


@app.post("/api/ads/audio")
async def api_upload_ad_audio(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Озвучка не выбрана")
    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp3", ".wav", ".m4a", ".ogg", ".flac"}:
        raise HTTPException(status_code=400, detail="Поддерживаются форматы озвучки: MP3, WAV, M4A, OGG")
    safe_stem = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ _-]+", "", Path(file.filename).stem).strip()[:40] or "voiceover"
    fname = f"voice_{safe_stem}_{uuid.uuid4().hex[:6]}{ext}"
    dest = ADS_DIR / fname
    with dest.open("wb") as out:
        while True:
            chunk = await file.read(512 * 1024)
            if not chunk:
                break
            out.write(chunk)
    dur = 0.0
    try:
        dur = float(probe_video(dest).get("duration") or 0.0)
    except Exception:
        pass
    return {"id": fname, "name": safe_stem, "duration": round(dur, 1)}


@app.get("/api/ads/{filename}")
def api_get_ad_file(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    p = ADS_DIR / safe_name
    if not p.exists():
        raise HTTPException(status_code=404, detail="Файл рекламы не найден")
    return FileResponse(path=str(p))


@app.get("/api/jobs/{job_id}/download-all")
def api_download_all_clips(job_id: str) -> FileResponse:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", job_id):
        raise HTTPException(status_code=400, detail="Некорректный идентификатор")
    job = get_job(job_id)
    if not job or not job.get("clips"):
        raise HTTPException(status_code=404, detail="Клипы не найдены")

    jdir = JOBS_DIR / job_id
    zip_path = jdir / f"tikcut_{job_id}_all_clips.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
        for idx, c in enumerate(job["clips"], start=1):
            mp4 = jdir / f"{c['id']}.mp4"
            if mp4.exists():
                zf.write(mp4, arcname=f"clip_{idx}_score{c.get('viral_score', 0)}_9x16.mp4")
        # Also include a ready-to-paste captions.txt file!
        captions_lines = []
        for idx, c in enumerate(job["clips"], start=1):
            captions_lines.append(f"=== КЛИП #{idx}: {c.get('title', '')} ===")
            captions_lines.append(c.get("tiktok_caption", ""))
            captions_lines.append("")
        zf.writestr("captions_and_hashtags.txt", "\n".join(captions_lines))

    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=f"tikcut_{job_id}_all_clips.zip",
    )


class CustomClipRequest(RerenderRequest):
    start_sec: float = Field(..., ge=0.0)
    end_sec: float = Field(..., gt=0.0)
    whisper_model: str = Field(default="small")
    custom_title: str = Field(default="")


@app.post("/api/jobs/{job_id}/custom-clip")
def api_custom_clip(job_id: str, req: CustomClipRequest) -> Dict[str, Any]:
    try:
        return create_custom_clip(
            job_id=job_id,
            start_sec=req.start_sec,
            end_sec=req.end_sec,
            options=req.model_dump(),
            custom_title=req.custom_title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка нарезки момента: {exc}")


@app.post("/api/jobs/{job_id}/clips/{clip_id}/rerender")
def api_rerender_clip(job_id: str, clip_id: str, req: RerenderRequest) -> Dict[str, Any]:
    try:
        updated = rerender_single_clip(
            job_id=job_id,
            clip_id=clip_id,
            options=req.model_dump(),
            edited_transcript=req.edited_transcript,
            edited_hook_text=req.edited_hook_text,
            trim_start=req.trim_start,
            trim_end=req.trim_end,
            source_start=req.source_start,
            source_end=req.source_end,
        )
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка перерендера: {exc}")


# =====================================================================
# v2.2.0 Endpoints: Custom Webcam Frame (#14), Outro CTA (#20),
# Batch URL Queue (#11), Disk Manager (#18), Content Plan (#19)
# =====================================================================

@app.get("/api/jobs/{job_id}/preview-frame")
def api_job_preview_frame(job_id: str) -> FileResponse:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", job_id):
        raise HTTPException(status_code=400, detail="Некорректный идентификатор")
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Проект не найден")
    jdir = JOBS_DIR / job_id
    frame_jpg = jdir / "preview_frame.jpg"
    if not frame_jpg.exists():
        vpath_str = job.get("video_path")
        if vpath_str and Path(vpath_str).exists():
            extract_preview_frame(Path(vpath_str), frame_jpg)
        elif job.get("remote_url"):
            # v3.0: Grab a REAL 16:9 in-stream frame directly from YouTube/Twitch without downloading the full VOD!
            import subprocess
            import urllib.request
            import yt_dlp

            remote_url = job["remote_url"]
            dur = float((job.get("video_meta") or {}).get("duration") or 60.0)
            at_sec = min(max(15.0, dur * 0.15), max(1.0, dur - 5.0))
            grabbed = False
            try:
                ydl_opts = _apply_network_opts({
                    "quiet": True,
                    "no_warnings": True,
                    "noplaylist": True,
                    "format": "bestvideo[height<=720][ext=mp4]/best[height<=720]/best",
                })
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(remote_url, download=False)
                stream_url = info.get("url") if info else None
                if stream_url:
                    cmd = [
                        "ffmpeg", "-y",
                        "-ss", f"{at_sec:.1f}",
                        "-i", stream_url,
                        "-vframes", "1",
                        "-vf", "scale=960:-2",
                        "-q:v", "3",
                        str(frame_jpg),
                    ]
                    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=18)
                    if r.returncode == 0 and frame_jpg.exists() and frame_jpg.stat().st_size > 2000:
                        grabbed = True
            except Exception:
                pass
            if not grabbed:
                thumb_url = (job.get("video_meta") or {}).get("thumbnail")
                if thumb_url:
                    try:
                        urllib.request.urlretrieve(thumb_url, str(frame_jpg))
                        grabbed = frame_jpg.exists() and frame_jpg.stat().st_size > 1000
                    except Exception:
                        pass
            if not grabbed:
                raise HTTPException(status_code=404, detail="Не удалось получить кадр из стрима")
        else:
            raise HTTPException(status_code=404, detail="Сначала выберите видео или ссылку")
    return FileResponse(path=str(frame_jpg), media_type="image/jpeg")


@app.get("/api/outros")
def api_list_outros() -> Dict[str, Any]:
    items = []
    for f in sorted(OUTROS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix.lower() in (".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".webp"):
            items.append({"id": f.name, "name": f.stem, "ext": f.suffix.lower()})
    return {"items": items}


@app.post("/api/outros")
async def api_upload_outro(file: UploadFile = File(...)) -> Dict[str, Any]:
    ext = Path(file.filename or "outro.mp4").suffix.lower()
    if ext not in (".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(status_code=400, detail="Поддерживаются MP4, MOV, WEBM, PNG, JPG, WEBP")
    safe_stem = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ_-]+", "_", Path(file.filename or "outro").stem)[:36] or "outro"
    fname = f"{safe_stem}_{uuid.uuid4().hex[:6]}{ext}"
    dest = OUTROS_DIR / fname
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    return {"id": fname, "name": safe_stem, "ext": ext}


class BatchUrlsRequest(BaseModel):
    urls: List[str]
    options: Dict[str, Any] = Field(default_factory=dict)


@app.post("/api/batch-urls")
def api_start_batch_urls(req: BatchUrlsRequest) -> Dict[str, Any]:
    try:
        return start_batch_urls(req.urls, req.options)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/api/batch-urls")
def api_get_batch_urls() -> Dict[str, Any]:
    return get_batch_status()


@app.get("/api/disk")
def api_disk_usage() -> Dict[str, Any]:
    return get_disk_usage_stats()


class CleanupSourcesRequest(BaseModel):
    older_than_days: int = Field(default=7, ge=0, le=365)


@app.post("/api/disk/cleanup-sources")
def api_cleanup_sources(req: CleanupSourcesRequest) -> Dict[str, Any]:
    return cleanup_old_sources(older_than_days=req.older_than_days)


@app.post("/api/disk/cleanup-cache")
def api_cleanup_cache() -> Dict[str, Any]:
    return cleanup_temp_cache()


class PlanCreateRequest(BaseModel):
    title: str
    account_id: str = ""
    account_name: str = "Основной"
    platform: str = "tiktok"
    scheduled_date: str = ""
    scheduled_time: str = "18:00"
    job_id: str = ""
    clip_id: str = ""
    notes: str = ""


class PlanUpdateRequest(BaseModel):
    title: Optional[str] = None
    account_id: Optional[str] = None
    account_name: Optional[str] = None
    platform: Optional[str] = None
    scheduled_date: Optional[str] = None
    scheduled_time: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


@app.get("/api/plan")
def api_list_plan() -> Dict[str, Any]:
    return {"items": list_plan_items()}


@app.post("/api/plan")
def api_add_plan(req: PlanCreateRequest) -> Dict[str, Any]:
    return add_plan_item(**req.model_dump())


@app.put("/api/plan/{item_id}")
def api_update_plan(item_id: str, req: PlanUpdateRequest) -> Dict[str, Any]:
    updated = update_plan_item(item_id, req.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return updated


@app.delete("/api/plan/{item_id}")
def api_delete_plan(item_id: str) -> Dict[str, Any]:
    if not delete_plan_item(item_id):
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return {"ok": True}


@app.post("/api/jobs/{job_id}/best-of-60s")
def api_best_of_60s(job_id: str, req: RerenderRequest) -> Dict[str, Any]:
    try:
        return create_best_of_60s_clip(job_id=job_id, options=req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка сборки Best-Of 60с: {exc}")


@app.get("/api/dashboard/export-csv")
def api_export_dashboard_csv() -> Response:
    import csv
    import datetime
    import io

    all_jobs = list_jobs(limit=300)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["Дата", "Проект", "Клип", "Длительность (с)", "Оценка", "Рекламный баннер", "Опубликовано"])
    for j in all_jobs:
        dt = datetime.datetime.fromtimestamp(float(j.get("created_at") or 0)).strftime("%Y-%m-%d %H:%M") if j.get("created_at") else ""
        proj = j.get("original_filename", j.get("job_id", ""))
        job_ad = (j.get("options") or {}).get("ad_banner_id") if (j.get("options") or {}).get("enable_ad_banner") else ""
        for c in j.get("clips") or []:
            pubs = ", ".join(
                f"{p.get('account_name', '')} ({p.get('platform', 'tiktok')})"
                for p in (c.get("published_to") or [])
            )
            writer.writerow([
                dt,
                proj,
                c.get("title", ""),
                c.get("duration", ""),
                c.get("viral_score", ""),
                c.get("ad_banner_id") or job_ad or "",
                pubs or "Нет",
            ])
    csv_bytes = ("\ufeff" + buf.getvalue()).encode("utf-8")
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="tikcut_studio_report.csv"'},
    )


# =====================================================================
# v2.5.0 Endpoints: Twitch Clips Radar (#1), Live Stream Clipper (#3),
# Visual Hype Timeline (#4)
# =====================================================================

class TwitchClipsSearchRequest(BaseModel):
    streamer: str
    period: str = Field(default="7d")
    limit: int = Field(default=20, ge=1, le=30)


@app.post("/api/twitch-clips/search")
def api_twitch_clips_search(req: TwitchClipsSearchRequest) -> Dict[str, Any]:
    try:
        clips = fetch_twitch_top_clips(req.streamer, period=req.period, limit=req.limit)
        return {"clips": clips, "count": len(clips)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка радара Twitch: {exc}")


class ClipPreviewUrlRequest(BaseModel):
    url: str


@app.post("/api/twitch-clips/preview-url")
def api_twitch_clip_preview_url(req: ClipPreviewUrlRequest) -> Dict[str, Any]:
    try:
        return resolve_clip_preview_url(req.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Не удалось открыть предпросмотр: {exc}")


class LiveClipRequest(BaseModel):
    url: str
    duration_sec: int = Field(default=45, ge=10, le=90)
    options: Dict[str, Any] = Field(default_factory=dict)


@app.post("/api/live-clip")
def api_capture_live_clip(req: LiveClipRequest) -> Dict[str, Any]:
    try:
        job_id = f"live_{uuid.uuid4().hex[:8]}"
        dest = UPLOADS_DIR / f"{job_id}.mp4"
        info = capture_live_stream_clip(req.url, dest, duration_sec=req.duration_sec)
        meta = probe_video(dest)
        job = create_job(job_id=job_id, original_filename=f"🔴 LIVE: {info['title']}", video_path=dest, video_meta=meta)
        opts = dict(req.options or {})
        opts["clip_count"] = 1
        opts["min_duration"] = min(15.0, max(8.0, float(meta.get("duration") or 30) - 2.0))
        opts["max_duration"] = float(meta.get("duration") or 60) + 2.0
        start_processing(job_id, opts)
        return job
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка захвата эфира: {exc}")


@app.get("/api/jobs/{job_id}/hype-timeline")
def api_job_hype_timeline(job_id: str) -> Dict[str, Any]:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", job_id):
        raise HTTPException(status_code=400, detail="Некорректный идентификатор")
    try:
        return get_job_hype_timeline(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# =====================================================================
# v2.6.0 Polish Endpoints: Cancel (#3), Delete Job/Clip (#5),
# Music Preview (#6), System Health (#8)
# =====================================================================

@app.post("/api/jobs/{job_id}/cancel")
def api_cancel_job(job_id: str) -> Dict[str, Any]:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", job_id):
        raise HTTPException(status_code=400, detail="Некорректный идентификатор")
    if not cancel_job(job_id):
        raise HTTPException(status_code=404, detail="Проект не найден")
    return {"ok": True}


@app.delete("/api/jobs/{job_id}")
def api_delete_job(job_id: str) -> Dict[str, Any]:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", job_id):
        raise HTTPException(status_code=400, detail="Некорректный идентификатор")
    delete_job(job_id)
    return {"ok": True}


@app.delete("/api/jobs/{job_id}/clips/{clip_id}")
def api_delete_clip(job_id: str, clip_id: str) -> Dict[str, Any]:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", job_id) or not re.fullmatch(r"[a-zA-Z0-9_-]+", clip_id):
        raise HTTPException(status_code=400, detail="Некорректный идентификатор")
    if not delete_clip(job_id, clip_id):
        raise HTTPException(status_code=404, detail="Клип не найден")
    return {"ok": True}


@app.get("/api/music/{filename}")
def api_get_music_file(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    p = MUSIC_DIR / safe_name
    if not p.exists():
        raise HTTPException(status_code=404, detail="Трек не найден")
    return FileResponse(path=str(p))


@app.get("/api/system-health")
def api_system_health() -> Dict[str, Any]:
    import subprocess
    import yt_dlp

    hw = get_hardware_info()
    disk = get_disk_usage_stats()
    ff_ver = "Не найден"
    ff_ok = False
    try:
        r = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=4)
        if r.returncode == 0 and r.stdout:
            ff_ok = True
            ff_ver = r.stdout.splitlines()[0].split("Copyright")[0].strip()[:42]
    except Exception:
        pass
    return {
        "ffmpeg_ok": ff_ok,
        "ffmpeg_version": ff_ver,
        "ytdlp_version": getattr(yt_dlp.version, "__version__", "unknown"),
        "gpu_name": hw.get("gpu_name") or "CPU",
        "has_nvenc": bool(hw.get("has_nvenc")),
        "has_videotoolbox": bool(hw.get("has_videotoolbox")),
        "has_cuda": bool(hw.get("has_cuda")),
        "disk_total_mb": disk.get("total_mb", 0),
    }


# =====================================================================
# v2.7.0 Endpoints: Telegram Auto-Send & Manual Send + Inline Title Edit (#9)
# =====================================================================

class TelegramTestRequest(BaseModel):
    bot_token: str
    chat_id: str


@app.post("/api/telegram/test")
def api_test_telegram(req: TelegramTestRequest) -> Dict[str, Any]:
    res = test_telegram_connection(req.bot_token, req.chat_id)
    if res.get("ok"):
        save_settings({"tg_bot_token": req.bot_token.strip(), "tg_chat_id": req.chat_id.strip()})
    return res


@app.post("/api/jobs/{job_id}/clips/{clip_id}/send-telegram")
def api_send_clip_telegram(job_id: str, clip_id: str) -> Dict[str, Any]:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", job_id) or not re.fullmatch(r"[a-zA-Z0-9_-]+", clip_id):
        raise HTTPException(status_code=400, detail="Некорректный идентификатор")
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Проект не найден")
    clip = next((c for c in (job.get("clips") or []) if c.get("id") == clip_id), None)
    if not clip:
        raise HTTPException(status_code=404, detail="Клип не найден")
    cfg = load_settings()
    token = (cfg.get("tg_bot_token") or "").strip()
    chat_id = (cfg.get("tg_chat_id") or "").strip()
    if not token or not chat_id:
        raise HTTPException(status_code=400, detail="Сначала укажите Telegram Bot Token и Chat ID во вкладке «⚙️ Система»")
    mp4 = JOBS_DIR / job_id / f"{clip_id}.mp4"
    try:
        return send_clip_to_telegram(token, chat_id, mp4, caption=clip.get("tiktok_caption") or clip.get("title", ""))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка отправки в Telegram: {exc}")


class ClipTitleRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=90)


@app.patch("/api/jobs/{job_id}/clips/{clip_id}/title")
def api_update_clip_title(job_id: str, clip_id: str, req: ClipTitleRequest) -> Dict[str, Any]:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", job_id) or not re.fullmatch(r"[a-zA-Z0-9_-]+", clip_id):
        raise HTTPException(status_code=400, detail="Некорректный идентификатор")
    updated = update_clip_title(job_id, clip_id, req.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Клип не найден")
    return updated


# =====================================================================
# v3.0.0 Endpoints: Full Studio Backup/Restore (#5) & Telegram Cloud Sync
# =====================================================================

@app.get("/api/backup/export")
def api_backup_export() -> Response:
    import datetime
    zbytes = create_studio_backup_zip()
    fname = f"tikcut_studio_backup_{datetime.date.today().isoformat()}.zip"
    return Response(
        content=zbytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.post("/api/backup/restore")
async def api_backup_restore(file: UploadFile = File(...)) -> Dict[str, Any]:
    raw = await file.read()
    try:
        return restore_studio_backup_zip(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Некорректный архив бэкапа: {exc}")


class TelegramSyncPushRequest(BaseModel):
    ui_preset: Dict[str, Any] = Field(default_factory=dict)


@app.post("/api/telegram/sync-push")
def api_telegram_sync_push(req: TelegramSyncPushRequest) -> Dict[str, Any]:
    from backend.config import DATA_DIR
    import json

    cfg = load_settings()
    token = (cfg.get("tg_bot_token") or "").strip()
    chat_id = (cfg.get("tg_chat_id") or "").strip()
    if not token or not chat_id:
        raise HTTPException(status_code=400, detail="Сначала укажите Telegram Bot Token и Chat ID")

    accounts_data = []
    acc_file = DATA_DIR / "accounts.json"
    if acc_file.exists():
        try:
            accounts_data = json.loads(acc_file.read_text(encoding="utf-8"))
        except Exception:
            accounts_data = []

    bundle = {
        "schema": "tikcut_sync_v1",
        "settings": cfg,
        "accounts": accounts_data,
        "content_plan": list_plan_items(),
        "ui_preset": req.ui_preset or {},
    }
    try:
        res = push_settings_to_telegram(token, chat_id, bundle)
        if res.get("file_id"):
            save_settings({"tg_last_sync_file_id": res["file_id"]})
        return {"ok": True, "message": "☁️ Все настройки, аккаунты и контент-план выгружены в Telegram!"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/telegram/sync-pull")
def api_telegram_sync_pull() -> Dict[str, Any]:
    from backend.config import CONTENT_PLAN_FILE, DATA_DIR
    import json

    cfg = load_settings()
    token = (cfg.get("tg_bot_token") or "").strip()
    chat_id = (cfg.get("tg_chat_id") or "").strip()
    fallback_id = (cfg.get("tg_last_sync_file_id") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Сначала укажите Telegram Bot Token")

    try:
        bundle = pull_settings_from_telegram(token, chat_id, fallback_file_id=fallback_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка синхронизации: {exc}")

    # Restore settings (preserve current tg token/chat_id if present), accounts & content plan
    if isinstance(bundle.get("settings"), dict):
        merged = dict(bundle["settings"])
        if token:
            merged["tg_bot_token"] = token
        if chat_id:
            merged["tg_chat_id"] = chat_id
        save_settings(merged)
    if isinstance(bundle.get("accounts"), list):
        (DATA_DIR / "accounts.json").write_text(json.dumps(bundle["accounts"], ensure_ascii=False, indent=2), encoding="utf-8")
    if isinstance(bundle.get("content_plan"), list):
        CONTENT_PLAN_FILE.write_text(json.dumps(bundle["content_plan"], ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "ui_preset": bundle.get("ui_preset") or {},
        "message": "☁️ Настройки, аккаунты и контент-план успешно синхронизированы из Telegram!",
    }


# =====================================================================
# v3.1.0 Endpoints: yt-dlp Update (#7), Asset Delete (#9), Favorite (#12),
# PNG Logos & Custom Fonts (#14), Multi-Account Render (#15),
# Streamer Monitor (#17), SRT Export (#18)
# =====================================================================

@app.post("/api/system/update-ytdlp")
def api_update_ytdlp() -> Dict[str, Any]:
    import subprocess
    import sys

    if getattr(sys, "frozen", False):
        return {
            "ok": False,
            "message": "В собранном приложении yt-dlp обновляется через кнопку «Обновления» сверху (OTA).",
        }
    try:
        res = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90,
        )
        if res.returncode == 0:
            return {"ok": True, "message": "✅ yt-dlp успешно обновлён! Перезапустите приложение."}
        return {"ok": False, "message": f"Не удалось обновить: {res.stderr[-180:]}"}
    except Exception as exc:
        return {"ok": False, "message": f"Ошибка обновления: {exc}"}


@app.delete("/api/assets/{kind}/{filename}")
def api_delete_asset(kind: str, filename: str) -> Dict[str, Any]:
    if not delete_asset_file(kind, filename):
        raise HTTPException(status_code=404, detail="Файл не найден")
    return {"ok": True}


@app.get("/api/logos")
def api_list_logos() -> Dict[str, Any]:
    items = []
    for f in sorted(LOGOS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix.lower() in (".png", ".webp", ".jpg", ".jpeg"):
            items.append({"id": f.name, "name": f.stem})
    return {"items": items}


@app.post("/api/logos")
async def api_upload_logo(file: UploadFile = File(...)) -> Dict[str, Any]:
    ext = Path(file.filename or "logo.png").suffix.lower()
    if ext not in (".png", ".webp", ".jpg", ".jpeg"):
        raise HTTPException(status_code=400, detail="Поддерживаются PNG, WEBP, JPG")
    safe_stem = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ_-]+", "_", Path(file.filename or "logo").stem)[:32] or "logo"
    fname = f"{safe_stem}_{uuid.uuid4().hex[:6]}{ext}"
    dest = LOGOS_DIR / fname
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    return {"id": fname, "name": safe_stem}


@app.get("/api/logos/{filename}")
def api_get_logo(filename: str) -> FileResponse:
    p = LOGOS_DIR / Path(filename).name
    if not p.exists():
        raise HTTPException(status_code=404, detail="Логотип не найден")
    return FileResponse(path=str(p))


@app.post("/api/custom-fonts")
async def api_upload_custom_font(file: UploadFile = File(...)) -> Dict[str, Any]:
    ext = Path(file.filename or "font.ttf").suffix.lower()
    if ext not in (".ttf", ".otf"):
        raise HTTPException(status_code=400, detail="Поддерживаются только шрифты .TTF и .OTF")
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", Path(file.filename or "font").stem)[:32] or "custom_font"
    fname = f"{safe_stem}_{uuid.uuid4().hex[:5]}{ext}"
    dest = CUSTOM_FONTS_DIR / fname
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    return {"id": f"custom:{fname}", "name": safe_stem, "fonts": get_available_fonts()}


@app.get("/api/custom-fonts/{filename}")
def api_get_custom_font(filename: str) -> FileResponse:
    p = CUSTOM_FONTS_DIR / Path(filename).name
    if not p.exists():
        raise HTTPException(status_code=404, detail="Шрифт не найден")
    return FileResponse(path=str(p))


@app.patch("/api/jobs/{job_id}/clips/{clip_id}/favorite")
def api_toggle_favorite(job_id: str, clip_id: str) -> Dict[str, Any]:
    updated = toggle_clip_favorite(job_id, clip_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Клип не найден")
    return updated


@app.post("/api/jobs/{job_id}/clips/{clip_id}/multi-render")
def api_multi_render_clip(job_id: str, clip_id: str, req: RerenderRequest) -> Dict[str, Any]:
    try:
        return multi_render_clip_for_accounts(job_id, clip_id, req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка мульти-рендера: {exc}")


@app.get("/api/jobs/{job_id}/clips/{clip_id}/srt")
def api_export_clip_srt(job_id: str, clip_id: str) -> Response:
    try:
        srt_text = get_clip_srt(job_id, clip_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return Response(
        content=srt_text.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{clip_id}.srt"'},
    )


class MonitorStreamersRequest(BaseModel):
    streamers: List[str]
    period: str = Field(default="24h")


@app.post("/api/twitch-clips/monitor")
def api_monitor_favorite_streamers(req: MonitorStreamersRequest) -> Dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor

    logins = [s.strip().lower() for s in req.streamers if s and s.strip()][:15]
    if not logins:
        raise HTTPException(status_code=400, detail="Добавьте хотя бы одного стримера")

    all_clips: List[Dict[str, Any]] = []

    def _fetch(lg: str) -> List[Dict[str, Any]]:
        try:
            return fetch_twitch_top_clips(lg, period=req.period, limit=5)
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=6) as pool:
        for res in pool.map(_fetch, logins):
            all_clips.extend(res)

    all_clips.sort(key=lambda c: int(c.get("views") or 0), reverse=True)
    return {"clips": all_clips[:24], "count": len(all_clips[:24])}
