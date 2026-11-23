"""Telegram Bot API uploader + Smart Auto-Compress (<48MB) + Cloud Settings Sync."""
import json
import mimetypes
import ssl
import subprocess
import tempfile
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import certifi
except Exception:
    certifi = None


def _ssl_context() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def _compress_for_telegram(video_path: Path, target_mb: float = 43.0) -> Path:
    """Feature #4 (v3.0): Auto-compress MP4 cleanly below Telegram's 50 MB Bot API limit."""
    dur = 30.0
    try:
        pr = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10,
        )
        if pr.stdout.strip():
            dur = max(3.0, float(pr.stdout.strip()))
    except Exception:
        pass

    target_total_kbps = int((target_mb * 8192.0) / dur)
    audio_kbps = 128
    video_kbps = max(450, min(6000, target_total_kbps - audio_kbps))

    tmp_out = Path(tempfile.gettempdir()) / f"tikcut_tg_{uuid.uuid4().hex[:8]}.mp4"
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-c:v", "libx264", "-preset", "veryfast",
        "-b:v", f"{video_kbps}k", "-maxrate", f"{int(video_kbps * 1.15)}k", "-bufsize", f"{video_kbps * 2}k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", f"{audio_kbps}k",
        "-movflags", "+faststart",
        str(tmp_out),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
    if res.returncode != 0 or not tmp_out.exists() or tmp_out.stat().st_size < 5000:
        tmp_out.unlink(missing_ok=True)
        raise RuntimeError(f"Не удалось сжать видео для Telegram: {res.stderr[-250:]}")
    return tmp_out


def test_telegram_connection(bot_token: str, chat_id: str) -> Dict[str, Any]:
    """Verify Telegram bot token and send a quick test message to chat_id."""
    token = (bot_token or "").strip()
    cid = (chat_id or "").strip()
    if not token or ":" not in token:
        return {"ok": False, "message": "Неверный формат токена (должен быть от @BotFather: 123456:ABC...)"}
    if not cid:
        return {"ok": False, "message": "Укажите Chat ID (можно узнать у @userinfobot)"}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": cid,
            "text": "✅ TikCut Studio подключён! Готовые клипы 9:16 и синхронизация настроек работают.",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=12, context=_ssl_context()) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        if data.get("ok"):
            return {"ok": True, "message": "✅ Тестовое сообщение отправлено в Telegram!"}
        return {"ok": False, "message": data.get("description") or "Ошибка Telegram API"}
    except Exception as exc:
        return {"ok": False, "message": f"Ошибка подключения: {exc}"}


def _multipart_upload(
    url: str,
    fields: Dict[str, str],
    file_field: str,
    filename: str,
    file_bytes: bytes,
    mime_type: str = "application/octet-stream",
    timeout: int = 120,
) -> Dict[str, Any]:
    boundary = f"----TikCutBoundary{uuid.uuid4().hex}"
    parts = []
    for k, v in fields.items():
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{k}"\r\n\r\n'
            f"{v}\r\n".encode("utf-8")
        )
    file_header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8")
    closing = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = b"".join(parts) + file_header + file_bytes + closing
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def send_clip_to_telegram(
    bot_token: str,
    chat_id: str,
    video_path: Path,
    caption: str = "",
) -> Dict[str, Any]:
    """Upload a rendered MP4 clip with automatic compression if > 48 MB."""
    token = (bot_token or "").strip()
    cid = (chat_id or "").strip()
    if not token or not cid:
        raise ValueError("Не настроены токен бота или Chat ID Telegram")
    if not video_path.exists():
        raise FileNotFoundError(f"Файл клипа не найден: {video_path}")

    send_path = video_path
    compressed_tmp: Optional[Path] = None
    try:
        size_mb = video_path.stat().st_size / (1024 * 1024)
        if size_mb > 48.0:
            compressed_tmp = _compress_for_telegram(video_path, target_mb=43.0)
            send_path = compressed_tmp

        fields = {"chat_id": cid, "supports_streaming": "true"}
        if caption:
            fields["caption"] = caption[:1020]
        mime = mimetypes.guess_type(str(send_path))[0] or "video/mp4"
        data = _multipart_upload(
            f"https://api.telegram.org/bot{token}/sendVideo",
            fields=fields,
            file_field="video",
            filename=video_path.name,
            file_bytes=send_path.read_bytes(),
            mime_type=mime,
            timeout=150,
        )
        if not data.get("ok"):
            raise RuntimeError(data.get("description") or "Telegram API вернул ошибку")
        return {
            "ok": True,
            "message_id": (data.get("result") or {}).get("message_id"),
            "compressed": compressed_tmp is not None,
        }
    finally:
        if compressed_tmp is not None:
            compressed_tmp.unlink(missing_ok=True)


def push_settings_to_telegram(bot_token: str, chat_id: str, bundle: Dict[str, Any]) -> Dict[str, Any]:
    """Cloud Sync Push: upload all studio settings, accounts & content plan as tikcut_sync.json to Telegram."""
    token = (bot_token or "").strip()
    cid = (chat_id or "").strip()
    if not token or not cid:
        raise ValueError("Сначала укажите Telegram Bot Token и Chat ID")

    raw_bytes = json.dumps(bundle, ensure_ascii=False, indent=2).encode("utf-8")
    data = _multipart_upload(
        f"https://api.telegram.org/bot{token}/sendDocument",
        fields={
            "chat_id": cid,
            "caption": "#tikcut_sync — Облачная синхронизация TikCut Studio (аккаунты, пресеты, настройки и контент-план)",
        },
        file_field="document",
        filename="tikcut_sync.json",
        file_bytes=raw_bytes,
        mime_type="application/json",
        timeout=30,
    )
    if not data.get("ok"):
        raise RuntimeError(data.get("description") or "Не удалось отправить синхронизацию в Telegram")
    doc = ((data.get("result") or {}).get("document")) or {}
    return {"ok": True, "file_id": doc.get("file_id") or ""}


def pull_settings_from_telegram(
    bot_token: str,
    chat_id: str,
    fallback_file_id: str = "",
) -> Dict[str, Any]:
    """
    Cloud Sync Pull: locate the latest tikcut_sync.json in Telegram bot updates (or fallback_file_id),
    download it via getFile, and return the parsed bundle!
    """
    token = (bot_token or "").strip()
    if not token:
        raise ValueError("Укажите Telegram Bot Token")

    file_id = ""
    try:
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/getUpdates?limit=50")
        with urllib.request.urlopen(req, timeout=12, context=_ssl_context()) as resp:
            upd = json.loads(resp.read().decode("utf-8", errors="ignore"))
        for item in reversed(upd.get("result") or []):
            msg = item.get("message") or item.get("channel_post") or {}
            doc = msg.get("document") or {}
            fname = (doc.get("file_name") or "").lower()
            cap = (msg.get("caption") or "").lower()
            if doc.get("file_id") and ("tikcut_sync" in fname or "#tikcut_sync" in cap):
                file_id = doc["file_id"]
                break
    except Exception:
        pass

    if not file_id:
        file_id = (fallback_file_id or "").strip()
    if not file_id:
        raise ValueError(
            "Не найден файл tikcut_sync.json в последних сообщениях бота. "
            "Перешлите файл tikcut_sync.json боту в чат (или сначала нажмите «☁️ Выгрузить в Telegram»)."
        )

    req_f = urllib.request.Request(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}")
    with urllib.request.urlopen(req_f, timeout=12, context=_ssl_context()) as resp:
        finfo = json.loads(resp.read().decode("utf-8", errors="ignore"))
    fpath = ((finfo.get("result") or {}).get("file_path")) or ""
    if not fpath:
        raise RuntimeError("Не удалось получить ссылку на файл синхронизации в Telegram")

    dl_url = f"https://api.telegram.org/file/bot{token}/{fpath}"
    with urllib.request.urlopen(dl_url, timeout=20, context=_ssl_context()) as resp:
        bundle = json.loads(resp.read().decode("utf-8", errors="ignore"))
    if not isinstance(bundle, dict):
        raise RuntimeError("Некорректный формат файла синхронизации")
    return bundle
