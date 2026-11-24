"""v2.5.0+: Twitch Top Clips Radar (#1), Direct GQL Clip Downloader & Live Stream Clipper (#3)."""
import json
import re
import ssl
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

import yt_dlp

try:
    import certifi
except Exception:
    certifi = None

from backend.config import load_settings
from backend.remote import _apply_network_opts
from backend.twitch_chat import TWITCH_GQL_URL, TWITCH_WEB_CLIENT_ID


def _ssl_ctx() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def extract_twitch_clip_slug(url: str) -> Optional[str]:
    """Extract clip slug from clips.twitch.tv/<slug> or twitch.tv/<user>/clip/<slug>."""
    m = re.search(r"(?:clips\.twitch\.tv/|/clip/)([A-Za-z0-9_-]+)", url or "", re.IGNORECASE)
    return m.group(1) if m else None


def resolve_twitch_clip_direct_mp4(clip_url: str) -> Optional[Dict[str, Any]]:
    """
    Resolve a direct signed MP4 URL for ANY Twitch Clip via Twitch GQL (zero yt-dlp required!).
    Returns {'mp4_url', 'title', 'duration'} or None if not a Twitch clip / failed.
    """
    slug = extract_twitch_clip_slug(clip_url)
    if not slug:
        return None
    query = """
    query($slug: ID!) {
      clip(slug: $slug) {
        title
        durationSeconds
        videoQualities {
          quality
          sourceURL
        }
        playbackAccessToken(params: { platform: "web", playerBackend: "mediaplayer", playerType: "site" }) {
          signature
          value
        }
      }
    }
    """
    payload = {"query": query, "variables": {"slug": slug}}
    req = urllib.request.Request(
        TWITCH_GQL_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Client-ID": TWITCH_WEB_CLIENT_ID,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10, context=_ssl_ctx()) as resp:
        raw = json.loads(resp.read().decode("utf-8", errors="ignore"))

    clip_obj = (raw.get("data") or {}).get("clip")
    if not clip_obj:
        return None
    qualities = clip_obj.get("videoQualities") or []
    token_obj = clip_obj.get("playbackAccessToken") or {}
    sig = token_obj.get("signature") or ""
    val = token_obj.get("value") or ""
    if not qualities or not sig or not val:
        return None

    def _q_num(q: Dict[str, Any]) -> int:
        try:
            return int(re.sub(r"[^0-9]", "", str(q.get("quality") or "0")) or "0")
        except Exception:
            return 0

    qualities_sorted = sorted(qualities, key=_q_num, reverse=True)
    chosen = next((q for q in qualities_sorted if 0 < _q_num(q) <= 1080 and q.get("sourceURL")), None)
    if not chosen:
        chosen = next((q for q in qualities_sorted if q.get("sourceURL")), None)
    if not chosen:
        return None

    src = chosen["sourceURL"]
    sep = "&" if "?" in src else "?"
    signed_url = f"{src}{sep}sig={urllib.parse.quote(sig)}&token={urllib.parse.quote(val)}"
    return {
        "mp4_url": signed_url,
        "title": (clip_obj.get("title") or "Клип Twitch").strip(),
        "duration": int(round(float(clip_obj.get("durationSeconds") or 30))),
    }


def download_twitch_clip_direct(clip_url: str, output_mp4: Path) -> Optional[Path]:
    """Download a Twitch Clip directly as MP4 via Twitch GQL (bypasses yt-dlp Twitch bugs!)."""
    info = resolve_twitch_clip_direct_mp4(clip_url)
    if not info or not info.get("mp4_url"):
        return None
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_mp4.with_suffix(".dl.tmp")
    req = urllib.request.Request(
        info["mp4_url"],
        headers={"User-Agent": "Mozilla/5.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=45, context=_ssl_ctx()) as resp, tmp_path.open("wb") as out:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                out.write(chunk)
        if tmp_path.exists() and tmp_path.stat().st_size > 10_000:
            tmp_path.replace(output_mp4)
            return output_mp4
    finally:
        tmp_path.unlink(missing_ok=True)
    return None


# =====================================================================
# Feature #1: Twitch Top Clips Radar by streamer login (zero API key!)
# =====================================================================

_PERIOD_MAP = {
    "24h": "LAST_DAY",
    "7d": "LAST_WEEK",
    "30d": "LAST_MONTH",
    "all": "ALL_TIME",
}


def fetch_twitch_top_clips(streamer_login: str, period: str = "7d", limit: int = 20) -> List[Dict[str, Any]]:
    """
    Fetch top viewer-created Twitch clips for any streamer login using Twitch public GQL
    (zero API key required!).
    """
    login = re.sub(r"^https?://(?:www\.)?twitch\.tv/", "", (streamer_login or "").strip(), flags=re.IGNORECASE)
    login = login.strip("/@ ").split("/")[0].lower()
    if not login or not re.fullmatch(r"[a-z0-9_]{2,32}", login):
        raise ValueError("Введите корректный ник стримера Twitch (латиницей, например: buster или bratishkinoff)")

    gql_filter = _PERIOD_MAP.get(period, "LAST_WEEK")
    query = """
    query($login: String!, $limit: Int!, $filter: ClipsPeriod!) {
      user(login: $login) {
        displayName
        clips(first: $limit, criteria: { period: $filter }) {
          edges {
            node {
              id
              slug
              title
              url
              viewCount
              durationSeconds
              createdAt
              thumbnailURL
              game { name }
            }
          }
        }
      }
    }
    """
    payload = {
        "query": query,
        "variables": {
            "login": login,
            "limit": max(1, min(30, int(limit))),
            "filter": gql_filter,
        },
    }
    req = urllib.request.Request(
        TWITCH_GQL_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Client-ID": TWITCH_WEB_CLIENT_ID,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10, context=_ssl_ctx()) as resp:
        raw = json.loads(resp.read().decode("utf-8", errors="ignore"))

    user_obj = (raw.get("data") or {}).get("user")
    if not user_obj:
        raise ValueError(f"Канал Twitch «{login}» не найден")

    display_name = user_obj.get("displayName") or login
    edges = ((user_obj.get("clips") or {}).get("edges")) or []
    clips: List[Dict[str, Any]] = []
    for edge in edges:
        node = edge.get("node") or {}
        slug = node.get("slug")
        url = node.get("url") or (f"https://clips.twitch.tv/{slug}" if slug else "")
        if not url:
            continue
        clips.append(
            {
                "id": node.get("id") or slug,
                "slug": slug or "",
                "title": (node.get("title") or "Клип Twitch").strip(),
                "url": url,
                "views": int(node.get("viewCount") or 0),
                "duration": int(round(float(node.get("durationSeconds") or 30))),
                "created_at": (node.get("createdAt") or "")[:10],
                "thumbnail": node.get("thumbnailURL") or "",
                "game": ((node.get("game") or {}).get("name")) or "",
                "streamer": display_name,
            }
        )
    clips.sort(key=lambda c: c["views"], reverse=True)
    return clips


def resolve_clip_preview_url(clip_url: str) -> Dict[str, Any]:
    """Resolve a direct playable MP4 stream URL for a Twitch clip (or short video) WITHOUT downloading it."""
    url = (clip_url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("Некорректная ссылка на клип")

    # Fast path: Direct Twitch GQL signed MP4 (0.2s, zero yt-dlp breakage!)
    try:
        direct = resolve_twitch_clip_direct_mp4(url)
        if direct and direct.get("mp4_url"):
            return direct
    except Exception:
        pass

    ydl_opts = _apply_network_opts(
        {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "best[ext=mp4]/best",
        }
    )
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise RuntimeError("Не удалось получить поток клипа")
    mp4_url = info.get("url")
    if not mp4_url and info.get("formats"):
        mp4s = [f for f in info["formats"] if f.get("url") and f.get("ext") == "mp4"]
        if mp4s:
            mp4_url = mp4s[-1]["url"]
        else:
            any_f = [f for f in info["formats"] if f.get("url")]
            if any_f:
                mp4_url = any_f[-1]["url"]
    if not mp4_url:
        raise RuntimeError("Не удалось получить прямую ссылку на видео клипа")
    return {
        "mp4_url": mp4_url,
        "title": info.get("title") or "Предпросмотр клипа",
        "duration": int(round(float(info.get("duration") or 0))),
    }


# =====================================================================
# Feature #3: Live Stream Instant Clipper (Twitch / YouTube Live)
# =====================================================================

def capture_live_stream_clip(
    stream_url: str,
    output_mp4: Path,
    duration_sec: int = 45,
) -> Dict[str, Any]:
    """
    Resolve a live Twitch / YouTube stream HLS URL via yt-dlp and capture `duration_sec`
    seconds directly into `output_mp4` with FFmpeg so the user can clip a live broadcast!
    """
    url = (stream_url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("Введите корректную ссылку на прямой эфир Twitch или YouTube Live")

    dur = max(10, min(90, int(duration_sec or 45)))
    ydl_opts = _apply_network_opts(
        {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "best[height<=1080]/best",
        }
    )
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise RuntimeError("Не удалось подключиться к прямому эфиру (возможно, стрим офлайн)")

    media_url = info.get("url")
    if not media_url and info.get("formats"):
        # Pick best combined format <= 1080p
        fmts = [f for f in info["formats"] if f.get("url")]
        if fmts:
            media_url = fmts[-1]["url"]
    if not media_url:
        raise RuntimeError("Не удалось получить видеопоток эфира (проверьте, что стрим идёт прямо сейчас)")

    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        media_url,
        "-t",
        str(dur),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output_mp4),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=dur + 45)
    if res.returncode != 0 or not output_mp4.exists() or output_mp4.stat().st_size < 10_000:
        raise RuntimeError(f"Не удалось захватить фрагмент эфира: {res.stderr[-300:]}")

    return {
        "title": info.get("title") or info.get("uploader") or "Прямой эфир",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "duration": dur,
        "file_path": str(output_mp4),
    }
