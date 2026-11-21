"""Zero-full-download analyzer & surgical clip downloader for YouTube / Twitch VODs."""
import json
import math
import re
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yt_dlp
from yt_dlp.utils import download_range_func

from backend.highlights import RUSSIAN_HOOK_WORDS, RUSSIAN_OPENER_WORDS, _make_clip_title


def probe_remote_url(url: str) -> Dict[str, Any]:
    """
    Fetch metadata, heatmap, chapters, and caption URLs from YouTube / Twitch VODs
    WITHOUT downloading the video file.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise RuntimeError("Не удалось получить данные по этой ссылке")

    # Handle playlist/channel URLs gracefully by taking first entry if present
    if "entries" in info and info["entries"]:
        info = info["entries"][0]

    duration = float(info.get("duration") or 0)
    width = int(info.get("width") or 1920)
    height = int(info.get("height") or 1080)
    fps = float(info.get("fps") or 30.0)
    heatmap = info.get("heatmap") or []
    chapters = info.get("chapters") or []

    # Check available Russian captions (manual first, then auto-captions)
    caption_info = _pick_caption_track(info)

    return {
        "url": info.get("webpage_url") or url,
        "title": info.get("title") or "Видео по ссылке",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "extractor": info.get("extractor_key") or info.get("extractor") or "remote",
        "thumbnail": info.get("thumbnail") or "",
        "duration": round(duration, 2),
        "width": width,
        "height": height,
        "fps": round(fps, 2),
        "has_audio": True,
        "has_heatmap": len(heatmap) > 0,
        "heatmap": heatmap,
        "chapters": chapters,
        "has_captions": caption_info is not None,
        "caption_track": caption_info,
    }


def _pick_caption_track(info: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Find the best Russian (or fallback) caption track URL in json3 or vtt format."""
    sources = [info.get("subtitles") or {}, info.get("automatic_captions") or {}]
    preferred_langs = ["ru", "ru-RU", "ru-orig", "uk", "en"]

    for src in sources:
        if not isinstance(src, dict):
            continue
        # Match exact preferred lang or prefix
        langs_to_try = [l for l in preferred_langs if l in src]
        for k in src.keys():
            if k.startswith("ru") and k not in langs_to_try:
                langs_to_try.insert(0, k)

        for lang in langs_to_try:
            tracks = src.get(lang) or []
            for fmt in ("json3", "vtt"):
                for t in tracks:
                    if t.get("ext") == fmt and t.get("url"):
                        return {"lang": lang, "ext": fmt, "url": t["url"]}
    return None


def _parse_vtt_time(ts: str) -> float:
    parts = ts.replace(",", ".").split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


def fetch_remote_transcript(
    caption_track: Optional[Dict[str, str]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Download ONLY the tiny subtitle file (~50-200 KB) and parse it into
    (segments, words) without touching the video or audio stream.
    """
    if not caption_track or not caption_track.get("url"):
        return [], []

    req = urllib.request.Request(
        caption_track["url"],
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")

    if caption_track.get("ext") == "json3":
        return _parse_json3(raw)
    return _parse_vtt(raw)


def _parse_json3(raw: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    data = json.loads(raw)
    segments: List[Dict[str, Any]] = []
    words: List[Dict[str, Any]] = []

    for ev in data.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        t_start_ms = float(ev.get("tStartMs", 0))
        d_dur_ms = float(ev.get("dDurationMs", 2500))
        seg_start = t_start_ms / 1000.0
        seg_end = (t_start_ms + d_dur_ms) / 1000.0

        seg_words: List[Dict[str, Any]] = []
        full_parts: List[str] = []

        for s in segs:
            txt = (s.get("utf8") or "").replace("\n", " ").strip()
            if not txt:
                continue
            off_ms = float(s.get("tOffsetMs", 0))
            w_start = (t_start_ms + off_ms) / 1000.0
            full_parts.append(txt)
            # Split multi-word seg token cleanly
            sub_tokens = txt.split()
            for ti, tok in enumerate(sub_tokens):
                ws = w_start + ti * 0.18
                we = min(seg_end, ws + 0.35)
                w_item = {"word": tok, "start": round(ws, 3), "end": round(max(ws + 0.08, we), 3)}
                seg_words.append(w_item)
                words.append(w_item)

        seg_text = re.sub(r"\s+", " ", " ".join(full_parts)).strip()
        if seg_text:
            segments.append(
                {
                    "start": round(seg_start, 3),
                    "end": round(seg_end, 3),
                    "text": seg_text,
                    "words": seg_words,
                }
            )

    # Fix overlapping word end times
    for i in range(len(words) - 1):
        if words[i]["end"] > words[i + 1]["start"]:
            words[i]["end"] = max(words[i]["start"] + 0.05, words[i + 1]["start"])

    return segments, words


def _parse_vtt(raw: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    segments: List[Dict[str, Any]] = []
    words: List[Dict[str, Any]] = []

    blocks = re.split(r"\r?\n\r?\n", raw)
    time_re = re.compile(r"(\d{1,2}:\d{2}:\d{2}[.,]\d{3}|\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{3}|\d{2}:\d{2}[.,]\d{3})")

    for blk in blocks:
        lines = [l.strip() for l in blk.splitlines() if l.strip()]
        m = None
        text_lines: List[str] = []
        for line in lines:
            if m is None:
                m = time_re.search(line)
            else:
                clean = re.sub(r"<[^>]+>", "", line).strip()
                if clean:
                    text_lines.append(clean)
        if not m or not text_lines:
            continue
        start = _parse_vtt_time(m.group(1))
        end = max(start + 0.2, _parse_vtt_time(m.group(2)))
        text = re.sub(r"\s+", " ", " ".join(text_lines)).strip()
        if not text:
            continue
        toks = text.split()
        step = (end - start) / max(1, len(toks))
        seg_words = []
        for idx, tok in enumerate(toks):
            ws = round(start + idx * step, 3)
            we = round(start + (idx + 1) * step, 3)
            w_item = {"word": tok, "start": ws, "end": we}
            seg_words.append(w_item)
            words.append(w_item)
        segments.append({"start": round(start, 3), "end": round(end, 3), "text": text, "words": seg_words})

    return segments, words


def _heatmap_score_in_window(heatmap: List[Dict[str, Any]], start: float, end: float) -> float:
    if not heatmap:
        return 0.0
    vals = [
        float(h.get("value", 0.0))
        for h in heatmap
        if float(h.get("end_time", 0.0)) >= start and float(h.get("start_time", 0.0)) <= end
    ]
    if not vals:
        return 0.0
    return min(1.0, 0.55 * max(vals) + 0.45 * (sum(vals) / len(vals)))


def find_remote_highlights(
    remote_meta: Dict[str, Any],
    segments: List[Dict[str, Any]],
    words: List[Dict[str, Any]],
    clip_count: int = 5,
    min_duration: float = 20.0,
    max_duration: float = 55.0,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> List[Dict[str, Any]]:
    """
    Analyze a remote video or multi-hour stream WITHOUT downloading it!
    Combines YouTube Most Replayed Heatmap + Russian transcript hooks + speech pacing.
    """
    total_duration = float(remote_meta.get("duration") or 0)
    heatmap = remote_meta.get("heatmap") or []
    has_heatmap = len(heatmap) > 0

    if progress_cb:
        progress_cb(0.25, "ИИ-анализ транскрипта и тепловой карты пересмотров...")

    candidates: List[Dict[str, Any]] = []

    if segments:
        # For very long streams (e.g. 3+ hours), stride smartly so analysis finishes in <2 seconds
        n_seg = len(segments)
        stride = 1 if n_seg <= 450 else max(1, n_seg // 400)

        for i in range(0, n_seg, stride):
            start_t = max(0.0, segments[i]["start"] - 0.15)
            prev_end = segments[i - 1]["end"] if i > 0 else 0.0
            starts_after_pause = (i == 0) or ((segments[i]["start"] - prev_end) >= 0.4)

            acc_text: List[str] = []
            acc_words: List[Dict[str, Any]] = []
            for j in range(i, n_seg):
                acc_text.append(segments[j]["text"])
                acc_words.extend(segments[j].get("words", []))
                end_t = min(total_duration or (segments[j]["end"] + 1.0), segments[j]["end"] + 0.25)
                dur = end_t - start_t
                if dur < min_duration:
                    continue
                if dur > max_duration + 4.0:
                    break

                txt = " ".join(acc_text).strip()
                sc = _score_remote_window(start_t, end_t, txt, acc_words, heatmap, starts_after_pause)
                candidates.append(
                    {
                        "start": round(start_t, 2),
                        "end": round(end_t, 2),
                        "duration": round(dur, 2),
                        "text": txt,
                        "score_data": sc,
                    }
                )
                # Keep one optimal window per start anchor on huge streams
                if n_seg > 450 and dur >= (min_duration + max_duration) * 0.45:
                    break

    # If no captions exist (e.g. Twitch VOD or music stream), use heatmap peaks or evenly spaced windows
    if not candidates:
        target_dur = min(max_duration, max(min_duration, 35.0))
        if has_heatmap:
            # Rank heatmap buckets directly
            sorted_hm = sorted(heatmap, key=lambda h: float(h.get("value", 0)), reverse=True)
            for h in sorted_hm[: clip_count * 6]:
                center = (float(h["start_time"]) + float(h["end_time"])) / 2.0
                s = max(0.0, center - target_dur * 0.4)
                e = min(total_duration, s + target_dur)
                if e - s < min_duration * 0.7:
                    continue
                val = float(h.get("value", 0.5))
                sc = {
                    "viral_score": int(round(min(99, 55 + val * 44))),
                    "raw_total": val,
                    "tags": ["📈 Пик пересмотров", "🔥 Топ момент стрима"],
                }
                candidates.append(
                    {
                        "start": round(s, 2),
                        "end": round(e, 2),
                        "duration": round(e - s, 2),
                        "text": "",
                        "score_data": sc,
                    }
                )
        else:
            # Evenly distribute candidate windows across the stream
            usable = max(target_dur, total_duration - 20.0)
            step = max(target_dur, usable / max(1, clip_count + 1))
            t = min(10.0, total_duration * 0.05)
            idx_c = 0
            while t + min_duration <= total_duration and idx_c < clip_count * 3:
                e = min(total_duration, t + target_dur)
                candidates.append(
                    {
                        "start": round(t, 2),
                        "end": round(e, 2),
                        "duration": round(e - t, 2),
                        "text": "",
                        "score_data": {
                            "viral_score": max(65, 86 - idx_c * 3),
                            "raw_total": 0.7 - idx_c * 0.03,
                            "tags": ["🎬 Фрагмент стрима"],
                        },
                    }
                )
                t += step
                idx_c += 1

    if progress_cb:
        progress_cb(0.85, "Отбор лучших непересекающихся моментов...")

    candidates.sort(key=lambda c: c["score_data"]["raw_total"], reverse=True)
    selected: List[Dict[str, Any]] = []

    def _overlap(a: Dict[str, Any], b: Dict[str, Any]) -> float:
        inter = max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
        return inter / max(1.0, min(a["duration"], b["duration"]))

    for max_ov in (0.05, 0.2):
        for c in candidates:
            if len(selected) >= clip_count:
                break
            if all(_overlap(c, s) <= max_ov for s in selected):
                selected.append(c)
        if len(selected) >= clip_count:
            break

    selected.sort(key=lambda c: c["score_data"]["raw_total"], reverse=True)

    results: List[Dict[str, Any]] = []
    for idx, item in enumerate(selected, start=1):
        sc = item["score_data"]
        results.append(
            {
                "id": f"clip_{idx}",
                "index": idx,
                "start": item["start"],
                "end": item["end"],
                "duration": item["duration"],
                "title": _make_clip_title(item["text"], idx),
                "transcript": item["text"],
                "viral_score": sc["viral_score"],
                "tags": sc["tags"],
                "metrics": sc,
            }
        )

    if progress_cb:
        progress_cb(1.0, f"ИИ отобрал {len(results)} лучших моментов без скачивания всего видео")

    return results


def _score_remote_window(
    start: float,
    end: float,
    text: str,
    window_words: List[Dict[str, Any]],
    heatmap: List[Dict[str, Any]],
    starts_after_pause: bool,
) -> Dict[str, Any]:
    duration = max(1.0, end - start)
    hm_score = _heatmap_score_in_window(heatmap, start, end)

    # Speech pacing
    wps = len(window_words) / duration
    if wps < 0.4:
        speech_score = 0.15
    elif wps <= 3.8:
        speech_score = min(1.0, 0.25 + (wps / 3.2) * 0.75)
    else:
        speech_score = 0.72

    # Russian linguistic & emotional hook score
    lower_text = text.lower()
    tokens = re.findall(r"[а-яёa-z0-9]+", lower_text)
    hook_hits = sum(1 for t in tokens if t in RUSSIAN_HOOK_WORDS)
    excl_quest = text.count("!") + text.count("?")
    num_hits = len(re.findall(r"\b\d+\b", text))
    opening_str = " ".join(tokens[:8])
    opener_bonus = 0.22 if any(opening_str.startswith(op) or f" {op}" in opening_str for op in RUSSIAN_OPENER_WORDS) else 0.0
    pause_bonus = 0.08 if starts_after_pause else 0.0

    hook_density = hook_hits / max(1.0, len(tokens) / 25.0)
    ling_score = min(
        1.0,
        0.15
        + min(0.45, hook_density * 0.16)
        + min(0.22, excl_quest * 0.08)
        + min(0.10, num_hits * 0.04)
        + opener_bonus
        + pause_bonus,
    )

    if heatmap:
        raw_total = 0.45 * hm_score + 0.38 * ling_score + 0.17 * speech_score
    else:
        raw_total = 0.68 * ling_score + 0.32 * speech_score

    viral_score = int(round(min(99, max(50, 44 + raw_total * 55))))

    tags: List[str] = []
    if heatmap and hm_score >= 0.55:
        tags.append("📈 Пик пересмотров")
    if ling_score >= 0.56:
        tags.append("💬 Сильный хук")
    if speech_score >= 0.72:
        tags.append("🎤 Живая подача")
    if not tags:
        tags.append("✨ Топ момент")

    return {
        "viral_score": viral_score,
        "raw_total": raw_total,
        "heatmap_score": round(hm_score, 3),
        "ling_score": round(ling_score, 3),
        "speech_score": round(speech_score, 3),
        "tags": tags[:3],
    }


def download_clip_segment(
    url: str,
    start: float,
    end: float,
    output_mp4: Path,
) -> Path:
    """
    Surgically download ONLY the [start, end] clip window from YouTube / Twitch VOD
    without downloading the full stream!
    """
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    if output_mp4.exists():
        output_mp4.unlink()

    out_tpl = str(output_mp4.with_suffix("")) + ".%(ext)s"
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]/best",
        "merge_output_format": "mp4",
        "outtmpl": out_tpl,
        "download_ranges": download_range_func(None, [(max(0.0, start), max(start + 1.0, end))]),
        "force_keyframes_at_cuts": True,
        "concurrent_fragment_downloads": 4,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    if output_mp4.exists():
        return output_mp4

    # yt-dlp might have written another extension before merge; locate it
    candidates = list(output_mp4.parent.glob(output_mp4.stem + ".*"))
    if candidates:
        return candidates[0]
    raise RuntimeError("Не удалось загрузить выбранный фрагмент по ссылке")
