"""Zero-full-download analyzer & surgical clip downloader for YouTube / Twitch VODs."""
import json
import math
import random
import re
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import yt_dlp
from yt_dlp.utils import download_range_func

from backend.config import load_settings
from backend.highlights import (
    _find_audio_peak_times,
    _make_clip_title,
    compute_audio_features,
    score_russian_text_fun_and_hooks,
)
from backend.twitch_chat import analyze_twitch_chat_peaks, extract_twitch_vod_id


def _apply_network_opts(ydl_opts: Dict[str, Any]) -> Dict[str, Any]:
    """Feature #59: Apply user-configured Proxy and Browser Cookies to yt-dlp."""
    cfg = load_settings()
    proxy = (cfg.get("yt_proxy") or "").strip()
    if proxy:
        ydl_opts["proxy"] = proxy
    browser = (cfg.get("yt_cookies_browser") or "").strip().lower()
    if browser in ("chrome", "edge", "firefox", "safari", "brave", "opera", "chromium"):
        ydl_opts["cookiesfrombrowser"] = (browser,)
    return ydl_opts


def download_lightweight_audio(url: str, wav_path: Path) -> Optional[Path]:
    """
    Download ONLY ultra-low-bitrate audio (NO video!) and convert to 8kHz mono WAV
    for fast 100% local acoustic laughter & loud-reaction peak detection on YouTube/Twitch links.
    """
    if wav_path.exists() and wav_path.stat().st_size > 1000:
        return wav_path

    raw_base = wav_path.with_suffix(".raw_audio")
    out_tpl = str(raw_base) + ".%(ext)s"
    ydl_opts = _apply_network_opts({
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "worstaudio[abr>=24]/bestaudio[abr<=64]/worstaudio/bestaudio",
        "outtmpl": out_tpl,
        "concurrent_fragment_downloads": 6,
    })
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        files = list(wav_path.parent.glob(raw_base.name + ".*"))
        if not files:
            return None
        src_audio = files[0]
        cmd = [
            "ffmpeg", "-y", "-i", str(src_audio),
            "-vn", "-ac", "1", "-ar", "8000", "-acodec", "pcm_s16le",
            str(wav_path),
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            src_audio.unlink()
        except Exception:
            pass
        if res.returncode == 0 and wav_path.exists() and wav_path.stat().st_size > 1000:
            return wav_path
    except Exception as exc:
        print(f"[remote] lightweight audio download skipped: {exc}")
    return None


def probe_remote_url(url: str) -> Dict[str, Any]:
    """
    Fetch metadata, heatmap, chapters, and caption URLs from YouTube / Twitch VODs
    WITHOUT downloading the video file.
    """
    ydl_opts = _apply_network_opts({
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
    })
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
    has_twitch_chat = False

    # For Twitch VODs without YouTube heatmap, analyze Twitch Chat Replay bursts!
    webpage_url = info.get("webpage_url") or url
    if not heatmap and extract_twitch_vod_id(webpage_url):
        try:
            chat_peaks = analyze_twitch_chat_peaks(webpage_url, duration)
            if chat_peaks:
                heatmap = chat_peaks
                has_twitch_chat = True
        except Exception:
            pass

    # Check available Russian captions (manual first, then auto-captions)
    caption_info = _pick_caption_track(info)

    return {
        "url": webpage_url,
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
        "has_twitch_chat": has_twitch_chat,
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
    dur = max(1.0, end - start)
    is_twitch = any(h.get("source") == "twitch_chat" for h in heatmap[:5])
    # For Twitch chat, chat lags 4-8s behind the actual joke, so also look 6s past clip end!
    look_end = end + 6.0 if is_twitch else end
    matched = [
        h for h in heatmap
        if float(h.get("end_time", 0.0)) >= start and float(h.get("start_time", 0.0)) <= look_end
    ]
    if not matched:
        return 0.0

    best_h = max(matched, key=lambda h: float(h.get("value", 0.0)))
    max_val = float(best_h.get("value", 0.0))
    avg_val = sum(float(h.get("value", 0.0)) for h in matched) / len(matched)
    base = 0.65 * max_val + 0.35 * avg_val

    if is_twitch:
        # Reward clips where the chat explosion hits in the 2nd half (40%..105%) so we capture the setup + joke!
        # Penalize clips that start RIGHT AT or AFTER the chat explosion (missing the actual funny moment).
        peak_t = float(best_h.get("start_time", start))
        rel_pos = (peak_t - start) / dur
        if 0.38 <= rel_pos <= 1.15:
            pos_mult = 1.08
        elif rel_pos < 0.22:
            pos_mult = 0.62
        else:
            pos_mult = 0.88
        return min(1.0, base * pos_mult)

    return min(1.0, base)


def find_remote_highlights(
    remote_meta: Dict[str, Any],
    segments: List[Dict[str, Any]],
    words: List[Dict[str, Any]],
    clip_count: int = 5,
    min_duration: float = 20.0,
    max_duration: float = 55.0,
    search_chat_activity: bool = True,
    search_laughter: bool = True,
    search_screams: bool = True,
    shuffle_seed: int = 0,
    exclude_ranges: Optional[List[Tuple[float, float]]] = None,
    audio_wav_path: Optional[Path] = None,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> List[Dict[str, Any]]:
    """
    Analyze a remote video or multi-hour stream WITHOUT downloading the full video!
    Combines separate acoustic Laughter & Scream detectors (lightweight audio) + Twitch Chat / YouTube Heatmap
    (with chat-reaction lag offset!) + Russian comedy transcript hooks.
    """
    total_duration = float(remote_meta.get("duration") or 0)
    heatmap = (remote_meta.get("heatmap") or []) if search_chat_activity else []
    has_heatmap = len(heatmap) > 0

    # Real local acoustic laughter (burst) & scream (rms) detection from lightweight audio!
    rms = None
    burst = None
    bin_sec = 0.25
    audio_peaks: List[float] = []
    if (search_laughter or search_screams) and audio_wav_path and Path(audio_wav_path).exists():
        if progress_cb:
            progress_cb(0.2, "😂 Локальный анализ смеха и криков стримера...")
        try:
            rms, burst, bin_sec = compute_audio_features(Path(audio_wav_path), bin_sec=0.25)
            p_mode = "both" if (search_laughter and search_screams) else ("laugh" if search_laughter else "scream")
            audio_peaks = _find_audio_peak_times(rms, burst, bin_sec, top_k=max(24, clip_count * 4), mode=p_mode)
        except Exception:
            rms, burst, audio_peaks = None, None, []

    if progress_cb:
        progress_cb(0.45, "Анализ пиков чата, смеха и криков...")

    def _audio_split_scores(s_t: float, e_t: float) -> Tuple[float, float]:
        if rms is None or burst is None or len(rms) < 8:
            return 0.0, 0.0
        b0 = max(0, int(s_t / bin_sec))
        b1 = min(len(rms), max(b0 + 1, int(math.ceil(e_t / bin_sec))))
        seg_r = rms[b0:b1]
        seg_b = burst[b0:b1]
        if len(seg_r) < 4:
            return 0.0, 0.0
        p92_r = float(np.percentile(seg_r, 92)) / (float(np.median(rms)) + 1e-6)
        p92_b = float(np.percentile(seg_b, 92)) / (float(np.median(burst)) + 1e-6)
        scream_sc = min(1.0, max(0.0, 0.18 + 0.34 * (p92_r - 1.0)))
        laugh_sc = min(1.0, max(0.0, 0.18 + 0.36 * (p92_b - 1.0)))
        return laugh_sc, scream_sc

    candidates: List[Dict[str, Any]] = []
    seen_ranges = set()

    def _add_remote_cand(s_t: float, e_t: float, txt: str, w_list: List[Dict[str, Any]], after_pause: bool) -> None:
        key = (round(s_t, 1), round(e_t, 1))
        if key in seen_ranges:
            return
        seen_ranges.add(key)
        a_laugh, a_scream = _audio_split_scores(s_t, e_t)
        sc = _score_remote_window(
            s_t, e_t, total_duration, txt, w_list, heatmap, after_pause,
            search_chat_activity=search_chat_activity,
            search_laughter=search_laughter,
            search_screams=search_screams,
            audio_laughter_score=a_laugh,
            audio_scream_score=a_scream,
            has_transcript=bool(segments),
        )
        candidates.append(
            {
                "start": round(s_t, 2),
                "end": round(e_t, 2),
                "duration": round(e_t - s_t, 2),
                "text": txt,
                "score_data": sc,
            }
        )

    if segments:
        n_seg = len(segments)

        def _snap_and_add(desired_start: float, desired_end: float) -> None:
            i_start = min(range(n_seg), key=lambda k: abs(segments[k]["start"] - desired_start))
            i_end = min(range(n_seg), key=lambda k: abs(segments[k]["end"] - desired_end))
            if i_end < i_start:
                i_end = i_start
            while i_end + 1 < n_seg and (segments[i_end]["end"] - segments[i_start]["start"]) < min_duration:
                i_end += 1
            while i_start > 0 and (segments[i_end]["end"] - segments[i_start]["start"]) < min_duration:
                i_start -= 1
            s_t = max(0.0, segments[i_start]["start"] - 0.15)
            e_t = min(total_duration or (segments[i_end]["end"] + 1.0), segments[i_end]["end"] + 0.25)
            if min_duration * 0.75 <= (e_t - s_t) <= max_duration + 6.0:
                seg_slice = segments[i_start : i_end + 1]
                txt = " ".join(s["text"] for s in seg_slice).strip()
                w_slice = [w for s in seg_slice for w in s.get("words", [])]
                _add_remote_cand(s_t, e_t, txt, w_slice, True)

        # 1. Anchor around REAL Acoustic Laughter / Scream peaks! (Setup ~15s before laugh + ~12s after)
        for pt in audio_peaks:
            _snap_and_add(max(0.0, pt - min(18.0, min_duration * 0.65)), min(total_duration or (pt + 15.0), pt + min(14.0, max_duration * 0.35)))

        # 2. Anchor around Chat / Heatmap peaks with CHAT REACTION LAG OFFSET!
        # (Chat explodes 4-6s AFTER the joke, so start 18-22s BEFORE the chat peak!)
        if has_heatmap:
            sorted_peaks = sorted(heatmap, key=lambda h: float(h.get("value", 0.0)), reverse=True)
            chosen_peak_centers: List[float] = []
            for h in sorted_peaks:
                center = (float(h["start_time"]) + float(h["end_time"])) * 0.5
                if all(abs(center - c) >= 18.0 for c in chosen_peak_centers):
                    chosen_peak_centers.append(center)
                    if len(chosen_peak_centers) >= max(20, clip_count * 4):
                        break
            for center in chosen_peak_centers:
                _snap_and_add(max(0.0, center - min(22.0, min_duration * 0.75)), min(total_duration or (center + 14.0), center + min(12.0, max_duration * 0.30)))

        # 3. Sliding transcript windows across the stream
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

                _add_remote_cand(start_t, end_t, " ".join(acc_text).strip(), list(acc_words), starts_after_pause)
                if n_seg > 450 and dur >= (min_duration + max_duration) * 0.45:
                    break

    # No captions (e.g. Twitch VOD): build directly from REAL acoustic laughter peaks + Twitch Chat peaks!
    if not candidates:
        target_dur = min(max_duration, max(min_duration, 32.0))
        for pt in audio_peaks:
            s = max(0.0, pt - target_dur * 0.58)
            e = min(total_duration, s + target_dur)
            if e - s >= min_duration * 0.7:
                _add_remote_cand(s, e, "", [], True)
        if has_heatmap:
            sorted_hm = sorted(heatmap, key=lambda h: float(h.get("value", 0)), reverse=True)
            for h in sorted_hm[: max(24, clip_count * 5)]:
                center = (float(h["start_time"]) + float(h["end_time"])) / 2.0
                # Shift BEFORE chat peak because chat lags behind the joke by ~4-6s!
                s = max(0.0, center - target_dur * 0.68)
                e = min(total_duration, s + target_dur)
                if e - s >= min_duration * 0.7:
                    _add_remote_cand(s, e, "", [], True)
        if not candidates:
            usable = max(target_dur, total_duration - 20.0)
            step = max(target_dur, usable / max(1, clip_count + 1))
            t = min(10.0, total_duration * 0.05)
            idx_c = 0
            while t + min_duration <= total_duration and idx_c < clip_count * 3:
                e = min(total_duration, t + target_dur)
                _add_remote_cand(t, e, "", [], True)
                t += step
                idx_c += 1

    if progress_cb:
        progress_cb(0.85, "Отбор лучших непересекающихся моментов...")

    if shuffle_seed:
        rng = random.Random(int(shuffle_seed))
        excl = exclude_ranges or []
        for cand in candidates:
            ov_prev = any(
                (min(cand["end"], ex_e) - max(cand["start"], ex_s)) > 5.0
                for ex_s, ex_e in excl
            )
            jitter = rng.uniform(-0.18, 0.22)
            cand["_rank"] = cand["score_data"]["raw_total"] + jitter - (0.35 if ov_prev else 0.0)
        candidates.sort(key=lambda c: c["_rank"], reverse=True)
    else:
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
    total_duration: float,
    text: str,
    window_words: List[Dict[str, Any]],
    heatmap: List[Dict[str, Any]],
    starts_after_pause: bool,
    search_chat_activity: bool = True,
    search_laughter: bool = True,
    search_screams: bool = True,
    audio_laughter_score: float = 0.0,
    audio_scream_score: float = 0.0,
    has_transcript: bool = True,
) -> Dict[str, Any]:
    duration = max(1.0, end - start)
    hm_score = _heatmap_score_in_window(heatmap, start, end) if search_chat_activity else 0.0

    # Speech pacing + hard penalty for wordless/music-only segments ONLY when transcript exists!
    word_count = len(window_words) if window_words else len(text.split())
    wps = word_count / duration
    wordless_penalty = 0.0
    if not has_transcript:
        speech_score = 0.55
    elif word_count == 0 and not text.strip():
        speech_score = 0.10
        wordless_penalty = 0.45
    elif word_count < 6 or wps < 0.35:
        speech_score = 0.05
        wordless_penalty = 0.50
    elif word_count < 12 or wps < 0.65:
        speech_score = 0.20
        wordless_penalty = 0.22
    elif wps <= 4.0:
        speech_score = min(1.0, 0.25 + (wps / 3.3) * 0.75)
    else:
        speech_score = 0.78

    # Comedy / Reaction & Hook Language Score + Ad/Intro Penalty
    comedy_score, hook_score, ad_penalty = score_russian_text_fun_and_hooks(text, starts_after_pause)

    edge_penalty = 0.0
    if total_duration > 120:
        if start < 12.0 or end > (total_duration - 12.0):
            edge_penalty = 0.14

    if search_laughter and search_screams:
        active_audio = 0.52 * audio_laughter_score + 0.48 * audio_scream_score
    elif search_laughter:
        active_audio = audio_laughter_score
    elif search_screams:
        active_audio = audio_scream_score
    else:
        active_audio = 0.0

    has_audio_sig = active_audio > 0.01
    synergy_bonus = 0.16 if (has_audio_sig and active_audio >= 0.45 and hm_score >= 0.50) else 0.0

    if has_audio_sig and heatmap and search_chat_activity and (search_laughter or search_screams):
        c_w = 0.18 if search_laughter else 0.08
        h_w = 0.07 if search_laughter else 0.17
        raw_total = 0.36 * active_audio + 0.34 * hm_score + c_w * comedy_score + h_w * hook_score + 0.05 * speech_score + synergy_bonus - ad_penalty - edge_penalty
    elif has_audio_sig and (search_laughter or search_screams):
        c_w = 0.26 if search_laughter else 0.10
        h_w = 0.12 if search_laughter else 0.28
        raw_total = 0.52 * active_audio + c_w * comedy_score + h_w * hook_score + 0.10 * speech_score - ad_penalty - edge_penalty
    elif heatmap and search_chat_activity:
        if search_laughter:
            raw_total = 0.46 * hm_score + 0.34 * comedy_score + 0.12 * hook_score + 0.08 * speech_score - ad_penalty - edge_penalty
        else:
            raw_total = 0.60 * hm_score + 0.12 * comedy_score + 0.18 * hook_score + 0.10 * speech_score - ad_penalty - edge_penalty
    else:
        if search_laughter:
            raw_total = 0.60 * comedy_score + 0.22 * hook_score + 0.18 * speech_score - ad_penalty - edge_penalty
        else:
            raw_total = 0.22 * comedy_score + 0.48 * hook_score + 0.30 * speech_score - ad_penalty - edge_penalty

    raw_total = max(0.02, min(1.0, raw_total - wordless_penalty))
    viral_score = int(round(min(99, max(48, 44 + raw_total * 56))))

    tags: List[str] = []
    if search_laughter and audio_laughter_score >= 0.54:
        tags.append("😂 Смех стримера")
    if search_screams and audio_scream_score >= 0.58:
        tags.append("📢 Крик / Эмоция")
    if heatmap and hm_score >= 0.50:
        is_tw = any(h.get("source") == "twitch_chat" for h in heatmap[:3])
        tags.append("💬 Взрыв чата Twitch" if is_tw else "📈 Пик пересмотров")
    if search_laughter and comedy_score >= 0.40 and len(tags) < 3:
        tags.append("🤣 Смешная реакция")
    if hook_score >= 0.52 and len(tags) < 3:
        tags.append("💬 Сильный хук")
    if not tags:
        tags.append("✨ Топ момент")

    return {
        "viral_score": viral_score,
        "raw_total": raw_total,
        "audio_laughter_score": round(audio_laughter_score, 3),
        "audio_scream_score": round(audio_scream_score, 3),
        "heatmap_score": round(hm_score, 3),
        "comedy_score": round(comedy_score, 3),
        "hook_score": round(hook_score, 3),
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
    ydl_opts = _apply_network_opts({
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]/best",
        "merge_output_format": "mp4",
        "outtmpl": out_tpl,
        "download_ranges": download_range_func(None, [(max(0.0, start), max(start + 1.0, end))]),
        "force_keyframes_at_cuts": True,
        "concurrent_fragment_downloads": 4,
    })
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    if output_mp4.exists():
        return output_mp4

    # yt-dlp might have written another extension before merge; locate it
    candidates = list(output_mp4.parent.glob(output_mp4.stem + ".*"))
    if candidates:
        return candidates[0]
    raise RuntimeError("Не удалось загрузить выбранный фрагмент по ссылке")
