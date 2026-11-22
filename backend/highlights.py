"""100% local viral & funny moment detector for Russian videos and streams (Setup -> Peak -> Reaction)."""
import math
import random
import re
import subprocess
import wave
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

# Russian comedy, streamer reactions, rage, shock, laughter & clutch words (highest weight!)
RUSSIAN_COMEDY_REACTION_WORDS = {
    "ахах", "ахаха", "ахахах", "хаха", "хахах", "хахаха", "ору", "ржу", "угар",
    "прикол", "смешно", "ржака", "анекдот", "лол", "кек", "кекв", "кринж",
    "жесть", "треш", "капец", "пипец", "офигеть", "обалдеть", "ахренеть", "охренеть",
    "блин", "черт", "чёрт", "какого", "хрена", "фига", "нифига", "нихрена",
    "ебать", "пиздец", "ахуеть", "охуеть", "бля", "блять", "сука", "нахуй", "еблан", "пизда",
    "шок", "безумие", "невозможно", "нереально", "чудо", "легенда", "имба",
    "клатч", "слил", "слили", "затащил", "убил", "сдох", "умер", "читер", "баг", "бан",
    "обосрался", "испугался", "скример", "мама", "боже", "господи", "помогите",
    "стой", "стойте", "подожди", "погоди", "ладно", "серьёзно", "серьезно",
    "реально", "враньё", "обман", "подстава", "пранк", "попался", "спалился",
    "чат", "пацаны", "ребята", "ребят", "мужики", "братан", "брат", "донат",
}

RUSSIAN_COMEDY_PHRASES = (
    "да ладно", "не может быть", "я не могу", "ты серьёзно", "ты серьезно",
    "что это было", "чё это было", "вы видели", "ты видел", "смотрите чё",
    "смотри что", "какого хрена", "какого фига", "да ну нафиг", "ну нафиг",
    "щас будет", "сейчас будет", "я ору", "я ржу", "это жесть", "это кринж",
    "это пипец", "не смешно", "я в шоке", "в смысле", "погоди стой",
    "как так", "зачем ты", "что ты делаешь", "чё ты делаешь", "не трогай",
    "беги", "спасайся", "ой бля", "о боже", "твою мать", "елки палки",
)

# Storytelling & curiosity hooks
RUSSIAN_HOOK_WORDS = {
    "главное", "секрет", "почему", "ошибка", "никогда", "кстати", "прикинь",
    "прикиньте", "короче", "представь", "представьте", "важно", "история",
    "фишка", "оказывается", "слушай", "слушайте", "смотри", "смотрите",
    "самый", "лучший", "худший", "впервые", "внезапно", "правда", "спорим",
    "клянусь", "знаешь", "знаете", "признаюсь", "случилось", "произошло",
}

RUSSIAN_OPENER_WORDS = (
    "смотрите", "слушайте", "представь", "знаете", "кстати", "почему",
    "короче", "однажды", "прикинь", "щас", "сейчас", "подожди", "стой",
    "ребят", "пацаны", "чат", "а вы знали", "спорим", "никогда",
)

# Ad reads, sponsor segments, channel intros & outros to PENALIZE heavily
BORING_AD_INTRO_PHRASES = (
    "промокод", "переходи по ссылке", "ссылка в описании", "спонсор",
    "реклама", "подписывайтесь на канал", "ставьте лайк", "жмите колокольчик",
    "всем привет с вами", "добро пожаловать на канал", "до новых встреч",
    "спасибо за просмотр", "увидимся в следующем", "скидка по коду",
    "скачивай по ссылке", "регистрируйся по ссылке", "телеграм канал в описании",
)


def compute_audio_features(wav_path: Path, bin_sec: float = 0.25) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Compute 4Hz (0.25s) RMS loudness curve AND laughter/excitement modulation curve
    from 16kHz mono PCM WAV.
    """
    with wave.open(str(wav_path), "rb") as wf:
        sr = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if len(samples) == 0:
        return np.zeros(1, dtype=np.float32), np.zeros(1, dtype=np.float32), bin_sec

    step = max(1, int(sr * bin_sec))
    n_bins = max(1, len(samples) // step)
    trimmed = samples[: n_bins * step].reshape(n_bins, step)

    # 1. RMS loudness per 0.25s bin
    rms = np.sqrt(np.mean(trimmed ** 2, axis=1) + 1e-10)

    # 2. Laughter / excited vocal burstiness:
    # Split each 0.25s bin into 5 sub-frames (50ms) and measure amplitude modulation + high-freq activity
    sub = max(1, step // 5)
    sub_trim = trimmed[:, : sub * 5].reshape(n_bins, 5, sub)
    sub_rms = np.sqrt(np.mean(sub_trim ** 2, axis=2) + 1e-10)
    mod_var = np.std(sub_rms, axis=1) / (np.mean(sub_rms, axis=1) + 1e-6)
    # Zero-crossing rate (higher for laughter / shouting / excited speech than flat hum)
    zcr = np.mean(np.abs(np.diff(np.signbit(trimmed), axis=1)), axis=1)
    burst = rms * (0.6 + mod_var) * np.clip(zcr * 4.0, 0.2, 2.0)

    return rms, burst, bin_sec


def detect_scene_changes(video_path: Path, threshold: float = 0.32) -> List[float]:
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
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        return [float(m.group(1)) for m in re.finditer(r"pts_time:([0-9]+(?:\.[0-9]+)?)", res.stderr)]
    except Exception:
        return []


def score_russian_text_fun_and_hooks(text: str, starts_after_pause: bool = False) -> Tuple[float, float, float]:
    """
    Returns (comedy_reaction_score, hook_score, ad_penalty) each in 0..1.
    Shared by both local and remote highlight detectors!
    """
    lower = text.lower()
    tokens = re.findall(r"[а-яёa-z0-9]+", lower)
    n_tok = max(1, len(tokens))

    # 1. Comedy / Reaction / Hype density
    comedy_hits = sum(1 for t in tokens if t in RUSSIAN_COMEDY_REACTION_WORDS)
    phrase_hits = sum(1 for p in RUSSIAN_COMEDY_PHRASES if p in lower)
    # Detect stretched laughter/shouting like "ааааа", "хахахаха", "оооо"
    stretch_hits = len(re.findall(r"(а{3,}|о{3,}|х[ао]{1}х[ао]{1}|у{3,})", lower))
    excl = text.count("!")
    quest = text.count("?")

    comedy_density = (comedy_hits + phrase_hits * 2.2 + stretch_hits * 1.5) / max(1.0, n_tok / 22.0)
    comedy_score = min(
        1.0,
        min(0.68, comedy_density * 0.24)
        + min(0.24, excl * 0.09)
        + min(0.14, quest * 0.06),
    )

    # 2. Storytelling / Hook score
    hook_hits = sum(1 for t in tokens if t in RUSSIAN_HOOK_WORDS)
    opening_str = " ".join(tokens[:9])
    opener_bonus = 0.24 if any(opening_str.startswith(op) or f" {op}" in opening_str for op in RUSSIAN_OPENER_WORDS) else 0.0
    pause_bonus = 0.08 if starts_after_pause else 0.0
    hook_score = min(1.0, 0.12 + min(0.48, (hook_hits / max(1.0, n_tok / 25.0)) * 0.18) + opener_bonus + pause_bonus)

    # 3. Heavy penalty for ad reads, sponsor promos, channel intros/outros
    ad_hits = sum(1 for pat in BORING_AD_INTRO_PHRASES if pat in lower)
    ad_penalty = min(0.65, ad_hits * 0.35)

    return comedy_score, hook_score, ad_penalty


def _score_window(
    start: float,
    end: float,
    total_duration: float,
    text: str,
    window_words: List[Dict[str, Any]],
    rms: np.ndarray,
    burst: np.ndarray,
    bin_sec: float,
    global_rms_mean: float,
    global_rms_std: float,
    global_burst_p85: float,
    scene_times: List[float],
    starts_after_pause: bool,
    search_laughter: bool = True,
) -> Dict[str, Any]:
    duration = max(1.0, end - start)

    # 1. Localized Peak Burst & Setup->Punchline Contrast (0..1)
    b0 = max(0, int(start / bin_sec))
    b1 = min(len(rms), max(b0 + 1, int(math.ceil(end / bin_sec))))
    seg_rms = rms[b0:b1]
    seg_burst = burst[b0:b1]

    if len(seg_rms) >= 8:
        # Smooth with 1.5s moving average to find genuine 2-5s laughter/rage bursts (not 1-frame pops)
        k = min(6, len(seg_rms))
        kernel = np.ones(k, dtype=np.float32) / k
        smooth_rms = np.convolve(seg_rms, kernel, mode="valid")
        peak_idx = int(np.argmax(smooth_rms))
        peak_val = float(smooth_rms[peak_idx])
        peak_z = (peak_val - global_rms_mean) / (global_rms_std + 1e-6)

        # Contrast: calm setup BEFORE the peak -> sudden explosion AT the peak!
        setup_slice = seg_rms[: max(1, peak_idx)]
        setup_mean = float(np.mean(setup_slice)) if len(setup_slice) > 2 else global_rms_mean
        contrast = peak_val / (setup_mean + 1e-5)

        # Laughter / excitement burst ratio
        burst_ratio = float(np.mean(seg_burst > global_burst_p85))

        # Sweet spot: peak occurs in middle-to-end of clip (30%..88%) so viewer sees setup + reaction!
        peak_rel_pos = peak_idx / max(1, len(smooth_rms))
        arc_bonus = 0.14 if (0.28 <= peak_rel_pos <= 0.88) else 0.0

        audio_peak_score = min(
            1.0,
            max(
                0.0,
                0.20
                + min(0.38, max(0.0, peak_z) * 0.19)
                + min(0.24, max(0.0, contrast - 1.15) * 0.20)
                + min(0.22, burst_ratio * 0.75)
                + arc_bonus,
            ),
        )
    else:
        audio_peak_score = 0.3

    # 2. Comedy / Reaction & Hook Language Score (0..1)
    comedy_score, hook_score, ad_penalty = score_russian_text_fun_and_hooks(text, starts_after_pause)

    # 3. Speech Pacing & Excitement Speedup (0..1)
    word_count = len(window_words)
    wps = word_count / duration
    if wps < 0.5:
        speech_score = 0.12
    elif wps <= 4.2:
        speech_score = min(1.0, 0.25 + (wps / 3.4) * 0.75)
    else:
        speech_score = 0.82

    # Penalize boring dead silences (> 2.2s)
    max_gap = 0.0
    for i in range(1, len(window_words)):
        gap = window_words[i]["start"] - window_words[i - 1]["end"]
        if gap > max_gap:
            max_gap = gap
    if max_gap > 2.4:
        speech_score *= 0.72

    # 4. Visual scene activity (0..1)
    cuts_in_window = sum(1 for t in scene_times if start <= t <= end)
    cuts_per_10s = cuts_in_window / (duration / 10.0)
    visual_score = min(1.0, 0.2 + cuts_per_10s * 0.25) if scene_times else 0.4

    # Slight penalty for very first 12s / very last 12s of long videos (usually intro/outro)
    edge_penalty = 0.0
    if total_duration > 120:
        if start < 10.0 or end > (total_duration - 10.0):
            edge_penalty = 0.14

    if search_laughter:
        raw_total = (
            0.40 * audio_peak_score
            + 0.36 * comedy_score
            + 0.12 * hook_score
            + 0.08 * speech_score
            + 0.04 * visual_score
            - ad_penalty
            - edge_penalty
        )
    else:
        raw_total = (
            0.28 * audio_peak_score
            + 0.14 * comedy_score
            + 0.30 * hook_score
            + 0.18 * speech_score
            + 0.10 * visual_score
            - ad_penalty
            - edge_penalty
        )
    raw_total = max(0.05, min(1.0, raw_total))
    viral_score = int(round(min(99, max(48, 44 + raw_total * 56))))

    tags: List[str] = []
    if comedy_score >= 0.42:
        tags.append("😂 Смешной / Реакция")
    if audio_peak_score >= 0.66:
        tags.append("🔥 Пик эмоций")
    if hook_score >= 0.52:
        tags.append("💬 Сильный хук")
    if speech_score >= 0.74 and len(tags) < 3:
        tags.append("⚡ Живая подача")
    if not tags:
        tags.append("✨ Топ момент")

    return {
        "viral_score": viral_score,
        "raw_total": raw_total,
        "audio_score": round(audio_peak_score, 3),
        "comedy_score": round(comedy_score, 3),
        "hook_score": round(hook_score, 3),
        "speech_score": round(speech_score, 3),
        "tags": tags[:3],
    }


def _make_clip_title(text: str, index: int) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return f"Топ момент #{index}"
    # Prefer the most emotional/exclamation sentence inside the clip if short enough!
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if len(s.strip()) >= 8]
    best_sent = sentences[0] if sentences else cleaned
    for s in sentences[:6]:
        if ("!" in s or "?" in s or any(w in s.lower() for w in ("ахах", "жесть", "шок", "кринж", "ладно", "реально"))) and len(s) <= 64:
            best_sent = s
            break
    candidate = best_sent.rstrip(".!?…")
    if len(candidate) > 58:
        candidate = candidate[:55].rsplit(" ", 1)[0].rstrip(",;:-") + "…"
    return candidate[0].upper() + candidate[1:] if candidate else f"Топ момент #{index}"


def _find_audio_peak_times(rms: np.ndarray, burst: np.ndarray, bin_sec: float, top_k: int = 24) -> List[float]:
    """Locate distinct local maxima in combined loudness + laughter burstiness."""
    if len(rms) < 12:
        return []
    k = 8  # 2-second smoothing window
    kernel = np.ones(k, dtype=np.float32) / k
    combined = (rms / (np.mean(rms) + 1e-6)) + 0.8 * (burst / (np.mean(burst) + 1e-6))
    smooth = np.convolve(combined, kernel, mode="same")

    order = np.argsort(smooth)[::-1]
    peaks: List[float] = []
    min_sep_sec = 14.0
    for idx in order:
        t = float(idx) * bin_sec
        if all(abs(t - p) >= min_sep_sec for p in peaks):
            peaks.append(t)
            if len(peaks) >= top_k:
                break
    return peaks


def find_highlights(
    video_path: Path,
    wav_path: Path,
    total_duration: float,
    segments: List[Dict[str, Any]],
    words: List[Dict[str, Any]],
    clip_count: int = 5,
    min_duration: float = 20.0,
    max_duration: float = 55.0,
    search_laughter: bool = True,
    shuffle_seed: int = 0,
    exclude_ranges: Optional[List[Tuple[float, float]]] = None,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> List[Dict[str, Any]]:
    """
    Identify top `clip_count` genuinely funny & viral non-overlapping moments
    using Peak-Anchored Setup -> Punchline -> Reaction windowing.
    """
    if progress_cb:
        progress_cb(0.1, "Поиск пиков смеха, эмоций и громких реакций в аудио...")

    rms, burst, bin_sec = compute_audio_features(wav_path, bin_sec=0.25)
    global_mean = float(np.mean(rms))
    global_std = float(np.std(rms)) + 1e-6
    global_burst_p85 = float(np.percentile(burst, 85)) if len(burst) else 0.0

    if progress_cb:
        progress_cb(0.45, "Анализ динамики кадров и смешных реакций...")

    scene_times = detect_scene_changes(video_path)

    if progress_cb:
        progress_cb(0.75, "Отбор самых смешных и виральных моментов...")

    if total_duration <= min_duration + 3.0:
        full_text = " ".join(s["text"] for s in segments).strip()
        sc = _score_window(
            0.0, total_duration, total_duration, full_text, words,
            rms, burst, bin_sec, global_mean, global_std, global_burst_p85, scene_times, True,
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
    seen_ranges = set()

    def _add_candidate(start_t: float, end_t: float, txt: str, w_list: List[Dict[str, Any]], after_pause: bool) -> None:
        key = (round(start_t, 1), round(end_t, 1))
        if key in seen_ranges:
            return
        seen_ranges.add(key)
        sc = _score_window(
            start_t, end_t, total_duration, txt, w_list,
            rms, burst, bin_sec, global_mean, global_std, global_burst_p85, scene_times, after_pause,
            search_laughter=search_laughter,
        )
        candidates.append(
            {
                "start": round(start_t, 2),
                "end": round(end_t, 2),
                "duration": round(end_t - start_t, 2),
                "text": txt,
                "score_data": sc,
            }
        )

    if segments:
        n_seg = len(segments)
        # 1. Peak-Anchored Windows: build Setup (~15s before peak) -> Peak -> Reaction (~12s after peak)
        peak_times = _find_audio_peak_times(rms, burst, bin_sec, top_k=max(20, clip_count * 4))
        for pt in peak_times:
            desired_start = max(0.0, pt - min(18.0, min_duration * 0.65))
            desired_end = min(total_duration, pt + min(16.0, max_duration * 0.38))
            # Snap to nearest segment boundaries
            i_start = min(range(n_seg), key=lambda k: abs(segments[k]["start"] - desired_start))
            i_end = min(range(n_seg), key=lambda k: abs(segments[k]["end"] - desired_end))
            if i_end < i_start:
                i_end = i_start
            # Expand if shorter than min_duration
            while i_end + 1 < n_seg and (segments[i_end]["end"] - segments[i_start]["start"]) < min_duration:
                i_end += 1
            while i_start > 0 and (segments[i_end]["end"] - segments[i_start]["start"]) < min_duration:
                i_start -= 1

            s_t = max(0.0, segments[i_start]["start"] - 0.15)
            e_t = min(total_duration, segments[i_end]["end"] + 0.25)
            if min_duration * 0.8 <= (e_t - s_t) <= max_duration + 6.0:
                seg_slice = segments[i_start : i_end + 1]
                txt = " ".join(s["text"] for s in seg_slice).strip()
                w_slice = [w for s in seg_slice for w in s.get("words", [])]
                prev_end = segments[i_start - 1]["end"] if i_start > 0 else 0.0
                _add_candidate(s_t, e_t, txt, w_slice, (i_start == 0) or (segments[i_start]["start"] - prev_end >= 0.4))

        # 2. Sentence-aligned sliding windows (catches deadpan jokes & storytelling hooks)
        stride = 1 if n_seg <= 300 else max(1, n_seg // 250)
        for i in range(0, n_seg, stride):
            start_t = max(0.0, segments[i]["start"] - 0.15)
            prev_end = segments[i - 1]["end"] if i > 0 else 0.0
            after_pause = (i == 0) or ((segments[i]["start"] - prev_end) >= 0.45)

            acc_text: List[str] = []
            acc_words: List[Dict[str, Any]] = []
            for j in range(i, n_seg):
                acc_text.append(segments[j]["text"])
                acc_words.extend(segments[j].get("words", []))
                end_t = min(total_duration, segments[j]["end"] + 0.25)
                dur = end_t - start_t
                if dur < min_duration:
                    continue
                if dur > max_duration + 4.0:
                    break
                _add_candidate(start_t, end_t, " ".join(acc_text).strip(), list(acc_words), after_pause)
                if n_seg > 250 and dur >= (min_duration + max_duration) * 0.45:
                    break

    # Fallback for gameplay/music without speech
    if not candidates:
        target_dur = min(max_duration, max(min_duration, 30.0))
        for pt in _find_audio_peak_times(rms, burst, bin_sec, top_k=clip_count * 4):
            s_t = max(0.0, pt - target_dur * 0.55)
            e_t = min(total_duration, s_t + target_dur)
            w_slice = [w for w in words if w["start"] >= s_t and w["end"] <= e_t]
            _add_candidate(s_t, e_t, " ".join(w["word"] for w in w_slice), w_slice, True)

    if shuffle_seed:
        rng = random.Random(int(shuffle_seed))
        excl = exclude_ranges or []
        for cand in candidates:
            # Penalize previously shown moments so Shuffle picks genuinely fresh clips!
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

    def _overlap_ratio(a: Dict[str, Any], b: Dict[str, Any]) -> float:
        inter = max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
        return inter / max(1.0, min(a["duration"], b["duration"]))

    for max_ov in (0.05, 0.20):
        for cand in candidates:
            if len(selected) >= clip_count:
                break
            if all(_overlap_ratio(cand, s) <= max_ov for s in selected):
                selected.append(cand)
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
        progress_cb(1.0, f"Найдено {len(results)} топовых и смешных моментов")

    return results
