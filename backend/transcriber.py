"""Local Russian speech-to-text transcription using faster-whisper (CUDA FP16 on NVIDIA RTX + CPU int8 fallback)."""
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from faster_whisper import WhisperModel

from backend.hardware import get_hardware_info

_MODEL_CACHE: Dict[str, Tuple[WhisperModel, str]] = {}

ALLOWED_MODELS = {"tiny", "base", "small", "medium", "large-v3-turbo"}


def get_whisper_model(model_size: str = "small") -> Tuple[WhisperModel, str]:
    """
    Load and cache a faster-whisper model.
    Uses NVIDIA CUDA FP16 automatically on RTX GPUs (e.g. RTX 4060 Ti) with safe CPU int8 fallback.
    Returns (model, device_used).
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
    """Extract 16kHz mono 16-bit PCM WAV from video using ffmpeg."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        str(wav_path),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {res.stderr[-400:]}")
    return wav_path


def transcribe_russian(
    audio_wav_path: Path,
    total_duration: float,
    model_size: str = "small",
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Transcribe Russian audio with word-level timestamps.
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
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 450},
        beam_size=5 if dev == "cuda" else 3,
    )

    segments: List[Dict[str, Any]] = []
    words: List[Dict[str, Any]] = []

    for seg in segments_gen:
        seg_words: List[Dict[str, Any]] = []
        if seg.words:
            for w in seg.words:
                txt = (w.word or "").strip()
                if not txt:
                    continue
                w_item = {
                    "word": txt,
                    "start": round(float(w.start), 3),
                    "end": round(float(w.end), 3),
                    "prob": round(float(getattr(w, "probability", 1.0) or 1.0), 3),
                }
                seg_words.append(w_item)
                words.append(w_item)

        seg_text = (seg.text or "").strip()
        if seg_text:
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
