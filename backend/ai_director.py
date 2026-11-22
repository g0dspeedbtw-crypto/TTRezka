"""Full-transcript AI Comedy & Viral Moment Director (Local Ollama on RTX GPU + optional free Gemini API)."""
import json
import re
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple


def _fmt_ts(sec: float) -> str:
    s = max(0, int(round(sec)))
    m, r = divmod(s, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{r:02d}"
    return f"{m:02d}:{r:02d}"


def _parse_ts(val: Any) -> Optional[float]:
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val or "").strip().strip("[]")
    parts = s.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(s)
    except Exception:
        return None


def _build_timestamped_transcript(segments: List[Dict[str, Any]], start_idx: int = 0, end_idx: Optional[int] = None) -> str:
    lines: List[str] = []
    slice_segs = segments[start_idx:end_idx]
    for seg in slice_segs:
        txt = (seg.get("text") or "").strip()
        if not txt:
            continue
        lines.append(f"[{_fmt_ts(seg['start'])}] {txt}")
    return "\n".join(lines)


def _snap_range_to_segments(
    start_t: float,
    end_t: float,
    segments: List[Dict[str, Any]],
    total_duration: float,
    min_dur: float,
    max_dur: float,
) -> Tuple[float, float, str]:
    if not segments:
        s = max(0.0, start_t)
        e = min(total_duration or (s + min_dur), max(s + min_dur, end_t))
        return round(s, 2), round(e, 2), ""

    n = len(segments)
    i0 = min(range(n), key=lambda k: abs(segments[k]["start"] - start_t))
    i1 = min(range(n), key=lambda k: abs(segments[k]["end"] - end_t))
    if i1 < i0:
        i1 = i0

    # Ensure duration stays nicely inside [min_dur, max_dur]
    while i1 + 1 < n and (segments[i1]["end"] - segments[i0]["start"]) < min_dur:
        i1 += 1
    while i0 > 0 and (segments[i1]["end"] - segments[i0]["start"]) < min_dur:
        i0 -= 1
    while i1 > i0 and (segments[i1]["end"] - segments[i0]["start"]) > max_dur + 4.0:
        i1 -= 1

    s = max(0.0, segments[i0]["start"] - 0.15)
    e = min(total_duration or (segments[i1]["end"] + 1.0), segments[i1]["end"] + 0.25)
    txt = " ".join(seg["text"] for seg in segments[i0 : i1 + 1]).strip()
    return round(s, 2), round(e, 2), txt


def _comedy_prompt(transcript_chunk: str, count: int, min_dur: int, max_dur: int) -> str:
    return (
        "Ты топовый монтажёр и продюсер смешных TikTok / Shorts нарезок русскоязычных стримеров и ютуберов.\n"
        f"Прочитай транскрипт с таймкодами и выбери РОВНО {count} САМЫХ СМЕШНЫХ, АБСУРДНЫХ, "
        "УГАРНЫХ или ВИРАЛЬНЫХ моментов.\n\n"
        "ЧТО ИСКАТЬ:\n"
        "- Реально смешные шутки, панчлайны, иронию, сарказм, подколы и нелепые фейлы\n"
        "- Смешные диалоги, неожиданные повороты, рейдж/истерику, шок-реакции\n"
        "- Законченную историю: завязка -> кульминация/шутка -> смех/реакция\n\n"
        "ЧТО СТРОГО ИГНОРИРОВАТЬ:\n"
        "- Приветствия, прощания, рекламу, промокоды, спонсоров, обычную скучную болтовню без панчлайна\n\n"
        f"Длина каждого клипа: строго от {min_dur} до {max_dur} секунд.\n"
        "Верни ТОЛЬКО валидный JSON массив без пояснений:\n"
        '[{"start": "MM:SS", "end": "MM:SS", "title": "Короткий смешной заголовок до 6 слов", '
        '"reason": "Почему это смешно (2-4 слова)", "score": 95}]\n\n'
        "ТРАНСКРИПТ:\n"
        + transcript_chunk
    )


def _extract_json_array(raw_text: str) -> List[Dict[str, Any]]:
    m = re.search(r"\[.*\]", raw_text or "", re.DOTALL)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
        return [x for x in arr if isinstance(x, dict)]
    except Exception:
        return []


def find_funny_moments_gemini(
    segments: List[Dict[str, Any]],
    total_duration: float,
    api_key: str,
    clip_count: int = 5,
    min_duration: float = 20.0,
    max_duration: float = 55.0,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> List[Dict[str, Any]]:
    """Use Google Gemini 2.5 Flash (free tier supported) to read the FULL Russian transcript and pick genuinely funny moments."""
    if not segments or not api_key:
        return []

    if progress_cb:
        progress_cb(0.3, "🧠 Gemini ИИ читает весь транскрипт и ищет реально смешные моменты...")

    full_transcript = _build_timestamped_transcript(segments)
    # Trim safely if > 250k chars (~6+ hour stream)
    if len(full_transcript) > 250_000:
        full_transcript = full_transcript[:250_000]

    prompt = _comedy_prompt(full_transcript, clip_count, int(min_duration), int(max_duration))
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key.strip()}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))

    candidates_resp = data.get("candidates") or []
    if not candidates_resp:
        return []
    text = (
        ((candidates_resp[0].get("content") or {}).get("parts") or [{}])[0].get("text")
        or ""
    )
    items = _extract_json_array(text)
    return _convert_llm_items_to_highlights(
        items, segments, total_duration, clip_count, min_duration, max_duration, badge="🧠 Gemini Comedy AI"
    )


def find_funny_moments_ollama(
    segments: List[Dict[str, Any]],
    total_duration: float,
    model_name: str,
    clip_count: int = 5,
    min_duration: float = 20.0,
    max_duration: float = 55.0,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> List[Dict[str, Any]]:
    """
    Use local Ollama LLM (running on RTX 4060 Ti) to scan the ENTIRE Russian transcript
    in chunks and pick genuinely funny jokes, fails, irony & punchlines!
    """
    if not segments or not model_name:
        return []

    # Split transcript into ~7-minute chunks (~4500 chars each) so 7B-9B local models read every line accurately
    chunks: List[Tuple[int, int]] = []
    cur_start = 0
    cur_chars = 0
    for idx, seg in enumerate(segments):
        cur_chars += len(seg.get("text", "")) + 12
        if cur_chars >= 4200:
            chunks.append((cur_start, idx + 1))
            cur_start = max(0, idx - 3)
            cur_chars = 0
    if cur_start < len(segments):
        chunks.append((cur_start, len(segments)))

    # Cap chunks for massive 5-hour streams so it stays fast
    if len(chunks) > 12:
        step = len(chunks) / 12.0
        chunks = [chunks[int(i * step)] for i in range(12)]

    per_chunk = max(2, min(4, (clip_count + len(chunks) - 1) // max(1, len(chunks)) + 1))
    all_items: List[Dict[str, Any]] = []

    for ci, (s_i, e_i) in enumerate(chunks):
        if progress_cb:
            progress_cb(
                0.2 + 0.7 * (ci / max(1, len(chunks))),
                f"🧠 Локальный ИИ ({model_name}) ищет смешные моменты: часть {ci + 1}/{len(chunks)}...",
            )
        chunk_txt = _build_timestamped_transcript(segments, s_i, e_i)
        prompt = _comedy_prompt(chunk_txt, per_chunk, int(min_duration), int(max_duration))
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.35, "num_predict": 700},
        }
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw = json.loads(resp.read().decode("utf-8", errors="ignore"))
            all_items.extend(_extract_json_array(raw.get("response") or ""))
        except Exception:
            continue

    return _convert_llm_items_to_highlights(
        all_items, segments, total_duration, clip_count, min_duration, max_duration, badge="🧠 RTX AI Комедия"
    )


def _convert_llm_items_to_highlights(
    items: List[Dict[str, Any]],
    segments: List[Dict[str, Any]],
    total_duration: float,
    clip_count: int,
    min_duration: float,
    max_duration: float,
    badge: str,
) -> List[Dict[str, Any]]:
    parsed: List[Dict[str, Any]] = []
    for it in items:
        st = _parse_ts(it.get("start"))
        en = _parse_ts(it.get("end"))
        if st is None or en is None or en <= st:
            continue
        s, e, txt = _snap_range_to_segments(st, en, segments, total_duration, min_duration, max_duration)
        if e - s < max(8.0, min_duration * 0.6):
            continue
        score = int(max(60, min(99, round(float(it.get("score") or 88)))))
        title = str(it.get("title") or "").strip()[:64]
        reason = str(it.get("reason") or "").strip()[:36]
        tags = [badge, "😂 Смешной момент"]
        if reason:
            tags.append(f"✨ {reason}")
        parsed.append(
            {
                "start": s,
                "end": e,
                "duration": round(e - s, 2),
                "title": title or f"Смешной момент",
                "transcript": txt,
                "viral_score": score,
                "tags": tags[:3],
            }
        )

    parsed.sort(key=lambda x: x["viral_score"], reverse=True)
    selected: List[Dict[str, Any]] = []

    def _ov(a: Dict[str, Any], b: Dict[str, Any]) -> float:
        inter = max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
        return inter / max(1.0, min(a["duration"], b["duration"]))

    for item in parsed:
        if len(selected) >= clip_count:
            break
        if all(_ov(item, s) <= 0.15 for s in selected):
            selected.append(item)

    results: List[Dict[str, Any]] = []
    for idx, item in enumerate(selected, start=1):
        results.append(
            {
                "id": f"clip_{idx}",
                "index": idx,
                "start": item["start"],
                "end": item["end"],
                "duration": item["duration"],
                "title": item["title"] or f"Смешной момент #{idx}",
                "transcript": item["transcript"],
                "viral_score": item["viral_score"],
                "tags": item["tags"],
                "metrics": {"source": badge},
            }
        )
    return results
