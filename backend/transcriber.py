"""Local Russian speech-to-text transcription using faster-whisper."""
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from faster_whisper import WhisperModel

_MODEL_CACHE: Dict[str, WhisperModel] = {}


def get_whisper_model(model_size: str = "small") -> WhisperModel:
    """Load and cache a faster-whisper model (CPU int8, fast on Apple Silicon)."""
    allowed = {"tiny", "base", "small", "medium"}
    if model_size not in allowed:
        model_size = "small"
    if model_size not in _MODEL_CACHE:
        _MODEL_CACHE[model_size] = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            cpu_threads=0,
        )
    return _MODEL_CACHE[model_size]


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
    Returns (segments, words).
    """
    if progress_cb:
        progress_cb(0.05, f"Загрузка локальной модели Whisper ({model_size})...")

    model = get_whisper_model(model_size)

    if progress_cb:
        progress_cb(0.12, "Распознавание русской речи и таймкодов слов...")

    segments_gen, _info = model.transcribe(
        str(audio_wav_path),
        language="ru",
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 450},
        beam_size=3,
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
                f"Распознавание речи: {int(seg.end)} / {int(total_duration)} сек...",
            )

    if progress_cb:
        progress_cb(1.0, f"Распознано {len(words)} слов")

    return segments, words
