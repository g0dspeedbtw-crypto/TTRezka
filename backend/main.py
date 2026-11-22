"""FastAPI web application for TikCut Studio — local 9:16 TikTok clipper."""
import re
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.config import (
    ADS_DIR,
    AVATARS_DIR,
    BASE_DIR,
    FONTS_DIR,
    JOBS_DIR,
    MUSIC_DIR,
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
    create_custom_clip,
    create_job,
    get_job,
    list_jobs,
    load_existing_jobs,
    rerender_single_clip,
    start_processing,
)
from backend.remote import probe_remote_url
from backend.renderer import probe_video

app = FastAPI(title="TikCut Studio", version="1.0.0")

# Mount static assets and bundled fonts so live UI preview uses the exact same TTFs
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/fonts", StaticFiles(directory=str(FONTS_DIR)), name="fonts")


@app.on_event("startup")
def _startup() -> None:
    load_existing_jobs()


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
    jump_cuts: bool = Field(default=False)
    bg_music_id: Optional[str] = Field(default=None)
    bg_music_volume: float = Field(default=0.18, ge=0.05, le=0.5)
    target_fps: int = Field(default=30)
    video_enhance: bool = Field(default=False)
    enable_ad_banner: bool = Field(default=False)
    ad_mode: str = Field(default="bottom_overlay")
    ad_banner_id: Optional[str] = Field(default=None)
    ad_audio_id: Optional[str] = Field(default=None)
    search_chat_activity: bool = Field(default=True)
    search_laughter: bool = Field(default=True)
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
    jump_cuts: bool = Field(default=False)
    bg_music_id: Optional[str] = Field(default=None)
    bg_music_volume: float = Field(default=0.18, ge=0.05, le=0.5)
    target_fps: int = Field(default=30)
    video_enhance: bool = Field(default=False)
    enable_ad_banner: bool = Field(default=False)
    ad_mode: str = Field(default="bottom_overlay")
    ad_banner_id: Optional[str] = Field(default=None)
    ad_audio_id: Optional[str] = Field(default=None)
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


@app.get("/api/settings")
def api_get_settings() -> Dict[str, Any]:
    return load_settings()


@app.post("/api/settings")
def api_save_settings(req: SettingsUpdateRequest) -> Dict[str, Any]:
    updates = {}
    if req.gemini_api_key is not None:
        updates["gemini_api_key"] = clean_api_key(req.gemini_api_key)
    if req.watermark_text is not None:
        updates["watermark_text"] = req.watermark_text.strip()
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
        if ext in {".png", ".jpg", ".jpeg", ".webp"}:
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
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="Поддерживаются форматы баннера: PNG, JPG, WEBP")
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
