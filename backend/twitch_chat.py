"""Twitch VOD Chat Replay peak detector (zero API key) + TikTok caption/hashtag generator."""
import json
import re
import urllib.request
from typing import Any, Dict, List, Optional

TWITCH_GQL_URL = "https://gql.twitch.tv/gql"
TWITCH_WEB_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"

HYPE_TOKENS = (
    "kekw", "lul", "lulw", "omegalul", "pog", "poggers", "pogchamp", "lmao",
    "ахах", "хаха", "ор", "ору", "шок", "жесть", "имба", "топ", "кринж",
    "красава", "легенда", "ааа", "капец", "треш", "угар", "ахаха", "gg", "w", "f",
)

HASHTAG_TOPICS = {
    "стрим": ["#стрим", "#твич", "#twitch", "#стример"],
    "игр": ["#игры", "#гейминг", "#gaming"],
    "деньг": ["#бизнес", "#деньги", "#успех"],
    "бизнес": ["#бизнес", "#мотивация", "#финансы"],
    "смеш": ["#юмор", "#прикол", "#смешно"],
    "ахах": ["#юмор", "#угар", "#мемы"],
    "шок": ["#шок", "#реакция", "#треш"],
    "секрет": ["#лайфхак", "#секрет", "#факты"],
    "ошибк": ["#советы", "#ошибки", "#разбор"],
    "истори": ["#история", "#подкаст", "#интересно"],
}


def extract_twitch_vod_id(url: str) -> Optional[str]:
    m = re.search(r"twitch\.tv/videos/(\d+)", url or "", re.IGNORECASE)
    return m.group(1) if m else None


def _query_twitch_comments_at_offset(vod_id: str, offset_sec: int) -> List[Dict[str, Any]]:
    """Fetch a page of Twitch VOD chat comments starting near `offset_sec`."""
    payload = [
        {
            "operationName": "VideoCommentsByOffsetOrCursor",
            "variables": {
                "videoID": str(vod_id),
                "contentOffsetSeconds": max(0, int(offset_sec)),
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "b70a3591ff0f4e0313d126c6a15ed4d754c9e8d20b6b78f8c7a83f9653f4b516",
                }
            },
        }
    ]
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
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))

    if not isinstance(data, list) or not data:
        return []
    comments_obj = ((data[0].get("data") or {}).get("video") or {}).get("comments") or {}
    edges = comments_obj.get("edges") or []
    result = []
    for edge in edges:
        node = edge.get("node") or {}
        off = node.get("contentOffsetSeconds")
        frags = ((node.get("message") or {}).get("fragments")) or []
        txt = " ".join((f.get("text") or "") for f in frags).strip()
        if off is not None:
            result.append({"offset": float(off), "text": txt})
    return result


def analyze_twitch_chat_peaks(
    url: str,
    total_duration: float,
    max_samples: int = 18,
) -> List[Dict[str, Any]]:
    """
    Sample Twitch VOD Chat Replay across the stream and return a heatmap-compatible
    activity curve highlighting moments where chat explodes with messages & hype emotes.
    """
    vod_id = extract_twitch_vod_id(url)
    if not vod_id or total_duration < 30:
        return []

    step = max(30.0, total_duration / max_samples)
    bins: List[Dict[str, Any]] = []
    raw_scores: List[float] = []

    offset = 15.0
    sample_idx = 0
    while offset < total_duration - 15.0 and sample_idx < max_samples:
        try:
            msgs = _query_twitch_comments_at_offset(vod_id, int(offset))
        except Exception:
            break

        if msgs:
            t_min = msgs[0]["offset"]
            t_max = max(t_min + 5.0, msgs[-1]["offset"])
            span = max(5.0, t_max - t_min)
            msg_per_sec = len(msgs) / span

            hype_hits = 0
            for m in msgs:
                low = m["text"].lower()
                if any(tok in low for tok in HYPE_TOKENS) or "!" in low or ")" * 2 in low:
                    hype_hits += 1
            hype_ratio = hype_hits / max(1, len(msgs))
            score = msg_per_sec * (1.0 + 1.4 * hype_ratio)
            bins.append(
                {
                    "start_time": round(t_min, 2),
                    "end_time": round(min(total_duration, t_min + max(25.0, span)), 2),
                    "raw_score": score,
                    "msg_count": len(msgs),
                    "source": "twitch_chat",
                }
            )
            raw_scores.append(score)

        offset += step
        sample_idx += 1

    if not bins:
        return []

    max_sc = max(raw_scores) or 1.0
    for b in bins:
        b["value"] = round(min(1.0, b["raw_score"] / max_sc), 3)

    return bins


def generate_tiktok_caption(
    title: str,
    transcript: str,
    tags: Optional[List[str]] = None,
    source_label: str = "",
) -> str:
    """Generate a ready-to-paste viral Russian TikTok / Shorts / Reels description + hashtags."""
    clean_title = (title or "Топ момент").strip()
    hashtags = ["#нарезки", "#тикток", "#рекомендации", "#shorts", "#reels"]

    combined = f"{clean_title} {transcript} {source_label}".lower()
    for kw, extra in HASHTAG_TOPICS.items():
        if kw in combined:
            for h in extra:
                if h not in hashtags:
                    hashtags.append(h)

    if tags and any("чат" in t.lower() for t in tags):
        for h in ("#твич", "#стрим", "#twitch"):
            if h not in hashtags:
                hashtags.append(h)

    tag_line = " ".join(hashtags[:9])
    return f"{clean_title} 🔥\n\nКак вам этот момент? Пишите в комментариях 👇\n\n{tag_line}"
