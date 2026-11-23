"""v2.5.0: Twitch Top Clips Radar (#1) & Live Stream Instant Clipper (#3)."""
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

import yt_dlp

from backend.config import load_settings
from backend.remote import _apply_network_opts
from backend.twitch_chat import TWITCH_GQL_URL, TWITCH_WEB_CLIENT_ID


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
    with urllib.request.urlopen(req, timeout=10) as resp:
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
