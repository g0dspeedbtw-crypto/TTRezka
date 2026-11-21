"""100% local, zero-API highlight detector for Russian videos."""
import math
import re
import subprocess
import wave
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

# Russian viral hooks, emotional triggers, storytelling openers & punchlines
RUSSIAN_HOOK_WORDS = {
    "главное", "секрет", "почему", "ошибка", "ошибки", "никогда", "кстати",
    "прикинь", "прикиньте", "короче", "представь", "представьте", "шок",
    "жесть", "важно", "лайфхак", "проблема", "идея", "деньги", "миллион",
    "реально", "правда", "история", "фишка", "самое", "оказывается",
    "подожди", "подождите", "слушай", "слушайте", "смотри", "смотрите",
    "офигеть", "безумие", "круто", "капец", "треш", "ужас", "топ",
    "совет", "правило", "факт", "запомни", "запомните", "знаешь", "знаете",
    "самый", "самая", "лучший", "худший", "впервые", "внезапно", "срочно",
    "внимание", "вообще", "серьёзно", "серьезно", "невероятно", "страшно",
    "смешно", "прикол", "обман", "развод", "миф", "способ", "метод",
    "результат", "успех", "провал", "жизнь", "работает", "запрещено",
    "обязательно", "бесплатно", "быстро", "просто", "сложно", "глупо",
}

RUSSIAN_OPENER_WORDS = (
    "смотрите", "слушайте", "представь", "знаете", "кстати", "почему",
    "главное", "секрет", "короче", "однажды", "прикинь", "самое",
    "вот", "а вы знали", "как", "что если", "никогда", "первое",
)


def compute_audio_energy_curve(wav_path: Path, bin_sec: float = 0.5) -> Tuple[np.ndarray, float]:
    """
    Read 16kHz mono PCM WAV and return normalized RMS energy array per `bin_sec`.
    """
    with wave.open(str(wav_path), "rb") as wf:
        sr = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if len(samples) == 0:
        return np.zeros(1, dtype=np.float32), bin_sec

    step = max(1, int(sr * bin_sec))
    n_bins = max(1, len(samples) // step)
    trimmed = samples[: n_bins * step].reshape(n_bins, step)
    rms = np.sqrt(np.mean(trimmed ** 2, axis=1) + 1e-10)
    return rms, bin_sec


def detect_scene_changes(video_path: Path, threshold: float = 0.32) -> List[float]:
    """
    Fast downscaled scene change detection via FFmpeg.
    Returns list of timestamps (seconds) where visual scene cuts occur.
    """
    cmd = [
        "ffmpeg",
        "-i",
        str(video_path),
        "-vf",
        f"scale=160:-2,select='gt(scene,{threshold})',showinfo",
        "-f",
        "null",
        "-",
    ]
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )
        timestamps = [
            float(m.group(1))
            for m in re.finditer(r"pts_time:([0-9]+(?:\.[0-9]+)?)", res.stderr)
        ]
        return timestamps
    except Exception:
        return []


def _score_window(
    start: float,
    end: float,
    text: str,
    window_words: List[Dict[str, Any]],
    rms: np.ndarray,
    bin_sec: float,
    global_rms_mean: float,
    global_rms_std: float,
    scene_times: List[float],
    starts_after_pause: bool,
) -> Dict[str, Any]:
    duration = max(1.0, end - start)

    # 1. Audio energy & excitement spikes (0..1)
    b0 = max(0, int(start / bin_sec))
    b1 = min(len(rms), max(b0 + 1, int(math.ceil(end / bin_sec))))
    seg_rms = rms[b0:b1]
    if len(seg_rms) > 0:
        z_scores = (seg_rms - global_rms_mean) / (global_rms_std + 1e-6)
        peak_ratio = float(np.mean(z_scores > 0.85))
        max_z = float(np.percentile(z_scores, 92))
        dyn_range = float(np.std(seg_rms) / (global_rms_mean + 1e-6))
        audio_score = min(1.0, max(0.0, 0.35 + 0.25 * max_z + 0.8 * peak_ratio + 0.15 * dyn_range))
    else:
        audio_score = 0.3

    # 2. Speech pacing & continuity (0..1)
    word_count = len(window_words)
    wps = word_count / duration
    # Sweet spot for engaging Russian speech: 2.0 - 4.0 words/sec
    if wps < 0.4:
        speech_score = 0.1
    elif wps <= 3.6:
        speech_score = min(1.0, 0.25 + (wps / 3.2) * 0.75)
    else:
        speech_score = max(0.65, 1.0 - (wps - 3.6) * 0.08)

    # Penalize long dead silences inside the clip
    max_gap = 0.0
    for i in range(1, len(window_words)):
        gap = window_words[i]["start"] - window_words[i - 1]["end"]
        if gap > max_gap:
            max_gap = gap
    if max_gap > 2.5:
        speech_score *= 0.78

    # 3. Russian linguistic & hook score (0..1)
    lower_text = text.lower()
    tokens = re.findall(r"[а-яёa-z0-9]+", lower_text)
    hook_hits = sum(1 for t in tokens if t in RUSSIAN_HOOK_WORDS)
    excl_count = text.count("!")
    quest_count = text.count("?")
    num_hits = len(re.findall(r"\b\d+\b", text))

    # Bonus if opening 6 words contain a strong Russian hook opener
    opening_str = " ".join(tokens[:8])
    opener_bonus = 0.22 if any(opening_str.startswith(op) or f" {op}" in opening_str for op in RUSSIAN_OPENER_WORDS) else 0.0
    pause_bonus = 0.10 if starts_after_pause else 0.0

    hook_density = hook_hits / max(1.0, len(tokens) / 25.0)
    ling_score = min(
        1.0,
        0.15
        + min(0.45, hook_density * 0.16)
        + min(0.22, (excl_count + quest_count) * 0.08)
        + min(0.12, num_hits * 0.05)
        + opener_bonus
        + pause_bonus,
    )

    # 4. Visual scene activity (0..1)
    cuts_in_window = sum(1 for t in scene_times if start <= t <= end)
    cuts_per_10s = cuts_in_window / (duration / 10.0)
    visual_score = min(1.0, 0.2 + cuts_per_10s * 0.28) if scene_times else 0.45

    # Weighted composite score
    raw_total = (
        0.35 * audio_score
        + 0.20 * speech_score
        + 0.30 * ling_score
        + 0.15 * visual_score
    )
    # Map to user-friendly 55..99 viral score scale
    viral_score = int(round(min(99, max(45, 42 + raw_total * 57))))

    tags: List[str] = []
    if audio_score >= 0.68:
        tags.append("🔥 Пик эмоций")
    if ling_score >= 0.58:
        tags.append("💬 Сильный хук")
    if speech_score >= 0.72:
        tags.append("🎤 Живая подача")
    if visual_score >= 0.62 and scene_times:
        tags.append("🎬 Динамика кадров")
    if not tags:
        tags.append("✨ Интересный фрагмент")

    return {
        "viral_score": viral_score,
        "raw_total": raw_total,
        "audio_score": round(audio_score, 3),
        "speech_score": round(speech_score, 3),
        "ling_score": round(ling_score, 3),
        "visual_score": round(visual_score, 3),
        "tags": tags[:3],
    }


def _make_clip_title(text: str, index: int) -> str:
    """Create a punchy Russian title from the opening sentence of the clip."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return f"Момент #{index}"
    # Take first sentence or first ~55 chars
    first_sent = re.split(r"[.!?]+", cleaned)[0].strip()
    candidate = first_sent if len(first_sent) >= 12 else cleaned
    if len(candidate) > 58:
        candidate = candidate[:55].rsplit(" ", 1)[0].rstrip(",;:-") + "…"
    return candidate[0].upper() + candidate[1:] if candidate else f"Момент #{index}"


def find_highlights(
    video_path: Path,
    wav_path: Path,
    total_duration: float,
    segments: List[Dict[str, Any]],
    words: List[Dict[str, Any]],
    clip_count: int = 5,
    min_duration: float = 20.0,
    max_duration: float = 55.0,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> List[Dict[str, Any]]:
    """
    Identify top `clip_count` non-overlapping viral moments from the video.
    """
    if progress_cb:
        progress_cb(0.1, "Анализ громкости, интонаций и пиков энергии аудио...")

    rms, bin_sec = compute_audio_energy_curve(wav_path, bin_sec=0.5)
    global_mean = float(np.mean(rms))
    global_std = float(np.std(rms)) + 1e-6

    if progress_cb:
        progress_cb(0.45, "Поиск динамичных смен сцен в видео...")

    scene_times = detect_scene_changes(video_path)

    if progress_cb:
        progress_cb(0.75, "Оценка виральности и подбор лучших моментов...")

    # Handle very short videos directly
    if total_duration <= min_duration + 3.0:
        full_text = " ".join(s["text"] for s in segments).strip()
        sc = _score_window(
            0.0,
            total_duration,
            full_text,
            words,
            rms,
            bin_sec,
            global_mean,
            global_std,
            scene_times,
            True,
        )
        return [
            {
                "id": "clip_1",
                "index": 1,
                "start": 0.0,
                "end": round(total_duration, 2),
                "duration": round(total_duration, 2),
                "title": _make_clip_title(full_text, 1),
                "transcript": full_text,
                "viral_score": sc["viral_score"],
                "tags": sc["tags"],
                "metrics": sc,
            }
        ]

    candidates: List[Dict[str, Any]] = []

    if segments:
        # Build sentence-aligned candidate windows from Whisper segments
        n_seg = len(segments)
        for i in range(n_seg):
            start_t = max(0.0, segments[i]["start"] - 0.15)
            prev_end = segments[i - 1]["end"] if i > 0 else 0.0
            starts_after_pause = (i == 0) or ((segments[i]["start"] - prev_end) >= 0.45)

            acc_text_parts: List[str] = []
            acc_words: List[Dict[str, Any]] = []

            for j in range(i, n_seg):
                acc_text_parts.append(segments[j]["text"])
                acc_words.extend(segments[j].get("words", []))
                end_t = min(total_duration, segments[j]["end"] + 0.25)
                dur = end_t - start_t

                if dur < min_duration:
                    continue
                if dur > max_duration + 4.0:
                    break

                full_txt = " ".join(acc_text_parts).strip()
                sc = _score_window(
                    start_t,
                    end_t,
                    full_txt,
                    acc_words,
                    rms,
                    bin_sec,
                    global_mean,
                    global_std,
                    scene_times,
                    starts_after_pause,
                )
                candidates.append(
                    {
                        "start": round(start_t, 2),
                        "end": round(end_t, 2),
                        "duration": round(dur, 2),
                        "text": full_txt,
                        "score_data": sc,
                    }
                )

    # Fallback if no speech segments or too few candidates (e.g. music/gameplay video)
    if not candidates:
        target_dur = min(max_duration, max(min_duration, 30.0))
        step = max(5.0, target_dur / 3.0)
        t = 0.0
        while t + min_duration <= total_duration + 0.5:
            end_t = min(total_duration, t + target_dur)
            w_slice = [w for w in words if w["start"] >= t and w["end"] <= end_t]
            txt = " ".join(w["word"] for w in w_slice)
            sc = _score_window(
                t,
                end_t,
                txt,
                w_slice,
                rms,
                bin_sec,
                global_mean,
                global_std,
                scene_times,
                True,
            )
            candidates.append(
                {
                    "start": round(t, 2),
                    "end": round(end_t, 2),
                    "duration": round(end_t - t, 2),
                    "text": txt,
                    "score_data": sc,
                }
            )
            t += step

    # Sort by composite score descending and pick non-overlapping clips (NMS)
    candidates.sort(key=lambda c: c["score_data"]["raw_total"], reverse=True)
    selected: List[Dict[str, Any]] = []

    def _overlap_ratio(a: Dict[str, Any], b: Dict[str, Any]) -> float:
        inter = max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
        min_len = max(1.0, min(a["duration"], b["duration"]))
        return inter / min_len

    for max_ov in (0.05, 0.20):
        for cand in candidates:
            if len(selected) >= clip_count:
                break
            if all(_overlap_ratio(cand, s) <= max_ov for s in selected):
                selected.append(cand)
        if len(selected) >= clip_count:
            break

    # Sort final selected clips by viral score descending
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
        progress_cb(1.0, f"Найдено {len(results)} лучших моментов")

    return results
