"""Twitch VOD Chat Replay viral explosion detector (zero API key) + TikTok caption/hashtag generator.

Filters out bots, !commands, giveaways, polls (1/2/+/-), and intro/outro greetings,
and uses a 2-stage concurrent radar to pinpoint REAL laugh/shock chat explosions.
"""
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

TWITCH_GQL_URL = "https://gql.twitch.tv/gql"
TWITCH_WEB_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"

BOT_LOGINS = {
    "nightbot", "streamelements", "moobot", "fossabot", "wizebot",
    "sery_bot", "streamlabs", "botrixoficial", "botrix", "kofistreambot",
    "soundalerts", "pretzelrocks", "commanderroot", "anotherttvviewer",
}

# Strict laugh / shock / viral reaction patterns (NO single-letter substrings like 'w', 'f', 'ор'!)
LAUGH_RE = re.compile(
    r"(?:аха+х|ха+ха|пха+х|хпа+х|ахха|хых|азаз|ржу|оруу*|угар|смешн|кекв*|лол|"
    r"\b(?:kekw|kek|lulw?|omegalul|icant|pepelaugh|lmao|lmfao|rofl|xdd|xd|хаха+|ахах+)\b|"
    r"[😂🤣💀😭])",
    re.IGNORECASE,
)

SHOCK_HYPE_RE = re.compile(
    r"(?:пиздец|пизд|ахуе|охуе|ебат|ебан|офиге|жесть|треш|кринж|капец|пипец|"
    r"шок|имба|легенда|красава|боже|чтооо+|чооо+|аааа+|оооо+|ураа+|"
    r"\b(?:pog|poggers|pogchamp|monkas|monkaw|wutface|based|goat|clutch|wtf|omg|ez|ggwp)\b|"
    r"[😱🤯🔥⚡💥])",
    re.IGNORECASE,
)

# Boring poll / vote / greeting / giveaway spam patterns to penalize heavily
POLL_VOTE_RE = re.compile(
    r"^(?:[+\-!?.,0-9]{1,3}|да|нет|го|не|ок|плюс|минус|yes|no|\+\+|\-\-|![a-zа-яё0-9_]+)$",
    re.IGNORECASE,
)

GREETING_OUTRO_RE = re.compile(
    r"\b(?:привет|прив|здаров|дарова|хай|ку|куку|здравствуй|пока|бб|спокойной|удачи|доброе утро|добрый вечер|"
    r"hello|hi|bye|gn|gg|рейд|raid|подарил|подписался|гифт|розыгрыш|giveaway|дроп)\b",
    re.IGNORECASE,
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
    """Fetch a page of Twitch VOD chat comments starting near `offset_sec`, excluding bots & !commands."""
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
        commenter = node.get("commenter") or {}
        login = (commenter.get("login") or "").lower()
        if login in BOT_LOGINS or login.endswith("bot"):
            continue
        frags = ((node.get("message") or {}).get("fragments")) or []
        txt = " ".join((f.get("text") or "") for f in frags).strip()
        if not txt or txt.startswith("!"):
            continue
        if off is not None:
            result.append({"offset": float(off), "text": txt, "user": login})
    return result


def _score_chat_sample(msgs: List[Dict[str, Any]], total_duration: float) -> Optional[Dict[str, Any]]:
    """Score a batch of chat messages strictly for REAL laugh/shock viral explosions (rejecting polls/spam)."""
    if len(msgs) < 4:
        return None

    t_min = msgs[0]["offset"]
    t_max = max(t_min + 3.0, msgs[-1]["offset"])
    span = max(3.0, t_max - t_min)
    msg_per_sec = len(msgs) / span

    # Count unique chatters so 1 spammer copy-pasting doesn't fake a chat explosion
    unique_users = len({m["user"] for m in msgs if m.get("user")}) or len(msgs)
    diversity = min(1.0, unique_users / max(1.0, len(msgs) * 0.7))

    laugh_hits = 0
    shock_hits = 0
    poll_hits = 0
    greet_hits = 0

    for m in msgs:
        txt = m["text"].strip()
        if POLL_VOTE_RE.match(txt):
            poll_hits += 1
            continue
        if GREETING_OUTRO_RE.search(txt):
            greet_hits += 1
        if LAUGH_RE.search(txt):
            laugh_hits += 1
        elif SHOCK_HYPE_RE.search(txt):
            shock_hits += 1

    n = len(msgs)
    laugh_ratio = laugh_hits / n
    shock_ratio = shock_hits / n
    emotion_ratio = (laugh_hits + shock_hits) / n
    poll_ratio = poll_hits / n
    greet_ratio = greet_hits / n

    # Heavy penalty for polls (1/2/+/-), giveaways, or hello/bye chat!
    spam_penalty = 1.0
    if poll_ratio >= 0.30:
        spam_penalty *= 0.15
    elif poll_ratio >= 0.18:
        spam_penalty *= 0.45
    if greet_ratio >= 0.25:
        spam_penalty *= 0.20

    # Penalize intro/outro edges on long streams (> 20 min)
    edge_mult = 1.0
    if total_duration > 1200:
        if t_min < 180.0 or t_min > (total_duration - 180.0):
            edge_mult = 0.25

    # Core viral formula: speed * diversity * (STRONG laugh/shock emotion multiplier)
    # Plain fast talking in chat with almost zero laughs/shock gets severely damped!
    emotion_mult = 0.25 + 4.2 * laugh_ratio + 2.8 * shock_ratio
    if emotion_ratio < 0.10:
        emotion_mult *= 0.35

    raw_score = msg_per_sec * diversity * emotion_mult * spam_penalty * edge_mult

    return {
        "start_time": round(t_min, 2),
        "end_time": round(min(total_duration, t_min + min(28.0, max(12.0, span))), 2),
        "raw_score": raw_score,
        "msg_per_sec": round(msg_per_sec, 2),
        "laugh_ratio": round(laugh_ratio, 3),
        "shock_ratio": round(shock_ratio, 3),
        "emotion_ratio": round(emotion_ratio, 3),
        "msg_count": n,
        "source": "twitch_chat",
    }


def analyze_twitch_chat_peaks(
    url: str,
    total_duration: float,
    max_samples: int = 120,
) -> List[Dict[str, Any]]:
    """
    2-stage concurrent Twitch VOD Chat Replay radar:
      Stage 1: Scan up to 120 points across the VOD (filtering bots, !commands, polls, greetings).
      Stage 2: Zoom in (-18s, -8s, +10s) around the top 12 hotspots to pinpoint the EXACT explosion second!
    """
    vod_id = extract_twitch_vod_id(url)
    if not vod_id or total_duration < 30:
        return []

    margin = 150.0 if total_duration > 1200 else 15.0
    usable = max(30.0, total_duration - margin * 2)
    step = max(18.0, usable / max(1, max_samples))
    offsets: List[int] = []
    cur = margin
    while cur < total_duration - margin and len(offsets) < max_samples:
        offsets.append(int(cur))
        cur += step

    def _sample_one(off: int) -> Optional[Dict[str, Any]]:
        try:
            msgs = _query_twitch_comments_at_offset(vod_id, off)
        except Exception:
            return None
        return _score_chat_sample(msgs, total_duration)

    bins: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        for res in pool.map(_sample_one, offsets):
            if res is not None:
                bins.append(res)

    if not bins:
        return []

    # Stage 2: Zoom-in refinement around top 12 hotspots to catch the exact peak moment
    top_hotspots = sorted(bins, key=lambda b: b["raw_score"], reverse=True)[:12]
    zoom_offsets: List[int] = []
    seen_off = set(offsets)
    for h in top_hotspots:
        base_t = int(h["start_time"])
        for delta in (-18, -8, 10):
            cand = max(10, min(int(total_duration - 15), base_t + delta))
            if all(abs(cand - s) >= 6 for s in seen_off):
                seen_off.add(cand)
                zoom_offsets.append(cand)

    if zoom_offsets:
        with ThreadPoolExecutor(max_workers=10) as pool:
            for res in pool.map(_sample_one, zoom_offsets):
                if res is not None:
                    bins.append(res)

    raw_scores = [b["raw_score"] for b in bins]
    sorted_raw = sorted(raw_scores)
    med = sorted_raw[len(sorted_raw) // 2] or 0.01
    p95 = sorted_raw[int(len(sorted_raw) * 0.95)] or max(raw_scores) or 1.0
    max_sc = max(raw_scores) or 1.0

    for b in bins:
        # Emphasize sharp spikes ABOVE the stream's normal median chat emotion score!
        rel_spike = b["raw_score"] / max(med, 0.02)
        norm = (
            0.50 * min(1.0, b["raw_score"] / max(p95, max_sc * 0.75))
            + 0.35 * min(1.0, max(0.0, (rel_spike - 1.2) / 4.0))
            + 0.15 * min(1.0, b.get("emotion_ratio", 0.0) * 2.2)
        )
        b["value"] = round(min(1.0, max(0.0, norm)), 3)

    bins.sort(key=lambda b: b["start_time"])
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
