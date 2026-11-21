"""Local Russian speech-to-text transcription using faster-whisper with vocal cleanup & anti-hallucination."""
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from faster_whisper import WhisperModel

from backend.hardware import get_hardware_info

_MODEL_CACHE: Dict[str, Tuple[WhisperModel, str]] = {}

ALLOWED_MODELS = {"tiny", "base", "small", "medium", "large-v3-turbo"}

# Natural Russian prompt guides Whisper toward clean Russian spelling, slang & punctuation
RUSSIAN_INITIAL_PROMPT = (
    "Живая разговорная русская речь: стрим, видео на YouTube, диалог, шутки и реакции. "
    "Пиши грамотно по-русски с правильной пунктуацией, без выдуманных титров."
)

# Known Whisper hallucination phrases on Russian audio/music/silence
HALLUCINATION_PATTERNS = (
    "субтитры сделал",
    "субтитры создавал",
    "редактор субтитров",
    "корректор",
    "dimatorzok",
    "amara.org",
    "продолжение следует",
    "спасибо за просмотр",
    "подписывайтесь на канал",
    "ставьте лайки",
    "музыкальная заставка",
)


def get_whisper_model(model_size: str = "small") -> Tuple[WhisperModel, str]:
    """
    Load and cache a faster-whisper model.
    Uses NVIDIA CUDA FP16 automatically on RTX GPUs (e.g. RTX 4060 Ti) with safe CPU int8 fallback.
    """
    if model_size not in ALLOWED_MODELS:
        model_size = "small"

    if model_size in _MODEL_CACHE:
        return _MODEL_CACHE[model_size]

    hw = get_hardware_info()
    if hw.get("cuda_whisper"):
        try:
            model = WhisperModel(
                model_size,
                device="cuda",
                compute_type="float16",
            )
            _MODEL_CACHE[model_size] = (model, "cuda")
            return model, "cuda"
        except Exception as exc:
            print(f"[whisper] CUDA load failed ({exc}), falling back to CPU int8")

    model = WhisperModel(
        model_size,
        device="cpu",
        compute_type="int8",
        cpu_threads=0,
    )
    _MODEL_CACHE[model_size] = (model, "cpu")
    return model, "cpu"


def extract_audio_wav(video_path: Path, wav_path: Path) -> Path:
    """
    Extract speech-enhanced 16kHz mono PCM WAV from video using FFmpeg.
    Filters out low-frequency game rumble/explosions and normalizes vocal volume
    for much cleaner Russian speech recognition.
    """
    # Try vocal-cleanup chain first, fallback to plain extraction if filter unsupported
    af_chain = "highpass=f=85,lowpass=f=7600,dynaudnorm=f=150:g=15"
    for af_args in (["-af", af_chain], []):
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            *af_args,
            "-ac",
            "1",
            "-ar",
            "16000",
            "-acodec",
            "pcm_s16le",
            str(wav_path),
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0 and wav_path.exists() and wav_path.stat().st_size > 100:
            return wav_path
    raise RuntimeError(f"FFmpeg audio extraction failed: {res.stderr[-400:]}")


def _is_hallucination(text: str, no_speech_prob: float, avg_logprob: float) -> bool:
    low = text.lower().strip()
    if not low:
        return True
    if no_speech_prob > 0.68 and avg_logprob < -0.9:
        return True
    if avg_logprob < -1.25:
        return True
    for pat in HALLUCINATION_PATTERNS:
        if pat in low and len(low) < 60:
            return True
    # Detect stuck repetition loops like "да да да да да да"
    toks = re.findall(r"[а-яёa-z0-9]+", low)
    if len(toks) >= 6 and len(set(toks)) <= 2:
        return True
    return False


def _clean_word_token(raw: str) -> str:
    txt = re.sub(r"\s+", " ", raw or "").strip()
    # Strip stray leading punctuation artifacts while keeping Russian letters/digits/normal endings
    txt = re.sub(r"^[,.;:]+", "", txt).strip()
    return txt


def transcribe_russian(
    audio_wav_path: Path,
    total_duration: float,
    model_size: str = "small",
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Transcribe Russian audio with clean word-level timestamps & hallucination suppression.
    Automatically leverages NVIDIA RTX CUDA FP16 when available.
    """
    if progress_cb:
        progress_cb(0.05, f"Загрузка модели Whisper ({model_size})...")

    model, dev = get_whisper_model(model_size)
    dev_label = "RTX CUDA FP16" if dev == "cuda" else "CPU int8"

    if progress_cb:
        progress_cb(0.12, f"Распознавание русской речи ({model_size} • {dev_label})...")

    segments_gen, _info = model.transcribe(
        str(audio_wav_path),
        language="ru",
        initial_prompt=RUSSIAN_INITIAL_PROMPT,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={
            "threshold": 0.45,
            "min_speech_duration_ms": 220,
            "min_silence_duration_ms": 420,
            "speech_pad_ms": 200,
        },
        condition_on_previous_text=False,
        repetition_penalty=1.1,
        no_repeat_ngram_size=3,
        temperature=0.0,
        beam_size=5 if dev == "cuda" else 3,
    )

    segments: List[Dict[str, Any]] = []
    words: List[Dict[str, Any]] = []

    for seg in segments_gen:
        seg_text = re.sub(r"\s+", " ", (seg.text or "")).strip()
        no_sp = float(getattr(seg, "no_speech_prob", 0.0) or 0.0)
        avg_lp = float(getattr(seg, "avg_logprob", 0.0) or 0.0)

        if _is_hallucination(seg_text, no_sp, avg_lp):
            continue

        seg_words: List[Dict[str, Any]] = []
        if seg.words:
            for w in seg.words:
                txt = _clean_word_token(w.word or "")
                if not txt:
                    continue
                ws = round(float(w.start), 3)
                we = round(max(ws + 0.06, float(w.end)), 3)
                # Merge orphan punctuation onto previous word instead of making a separate subtitle token
                if re.fullmatch(r"[.!?,…:—–-]+", txt) and seg_words:
                    seg_words[-1]["word"] += txt
                    seg_words[-1]["end"] = max(seg_words[-1]["end"], we)
                    words[-1]["word"] = seg_words[-1]["word"]
                    words[-1]["end"] = seg_words[-1]["end"]
                    continue

                w_item = {
                    "word": txt,
                    "start": ws,
                    "end": we,
                    "prob": round(float(getattr(w, "probability", 1.0) or 1.0), 3),
                }
                seg_words.append(w_item)
                words.append(w_item)

        if seg_text and seg_words:
            segments.append(
                {
                    "start": round(float(seg.start), 3),
                    "end": round(float(seg.end), 3),
                    "text": seg_text,
                    "words": seg_words,
                }
            )

        if progress_cb and total_duration > 0:
            frac = min(0.98, max(0.12, float(seg.end) / total_duration))
            progress_cb(
                frac,
                f"Распознавание ({dev_label}): {int(seg.end)} / {int(total_duration)} сек...",
            )

    if progress_cb:
        progress_cb(1.0, f"Распознано {len(words)} слов ({dev_label})")

    return segments, words
