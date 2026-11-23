"""Telegram Bot API uploader (pure stdlib + certifi SSL) for auto-sending rendered 9:16 clips."""
import json
import mimetypes
import ssl
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
            "text": "✅ TikCut Studio подключён! Готовые клипы 9:16 будут приходить сюда автоматически.",
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


def send_clip_to_telegram(
    bot_token: str,
    chat_id: str,
    video_path: Path,
    caption: str = "",
) -> Dict[str, Any]:
    """Upload a rendered MP4 clip (up to 50 MB Bot API limit) with caption directly to Telegram."""
    token = (bot_token or "").strip()
    cid = (chat_id or "").strip()
    if not token or not cid:
        raise ValueError("Не настроены токен бота или Chat ID Telegram")
    if not video_path.exists():
        raise FileNotFoundError(f"Файл клипа не найден: {video_path}")

    size_mb = video_path.stat().st_size / (1024 * 1024)
    if size_mb > 49.5:
        raise ValueError(f"Файл слишком большой для Telegram Bot API ({size_mb:.1f} МБ > 50 МБ)")

    boundary = f"----TikCutBoundary{uuid.uuid4().hex}"
    parts = []

    def _add_field(name: str, value: str) -> None:
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode("utf-8")
        )

    _add_field("chat_id", cid)
    _add_field("supports_streaming", "true")
    if caption:
        _add_field("caption", caption[:1020])

    mime = mimetypes.guess_type(str(video_path))[0] or "video/mp4"
    file_header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="video"; filename="{video_path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8")
    file_bytes = video_path.read_bytes()
    closing = f"\r\n--{boundary}--\r\n".encode("utf-8")

    body = b"".join(parts) + file_header + file_bytes + closing
    url = f"https://api.telegram.org/bot{token}/sendVideo"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120, context=_ssl_context()) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    if not data.get("ok"):
        raise RuntimeError(data.get("description") or "Telegram API вернул ошибку")
    return {"ok": True, "message_id": (data.get("result") or {}).get("message_id")}
