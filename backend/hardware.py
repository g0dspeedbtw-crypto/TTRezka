"""Hardware acceleration detector for NVIDIA RTX (CUDA + NVENC), Apple Silicon & local Ollama."""
import json
import platform
import subprocess
import urllib.request
from typing import Any, Dict, List, Optional

_HW_CACHE: Optional[Dict[str, Any]] = None


def _detect_nvidia_gpu() -> Optional[Dict[str, Any]]:
    try:
        res = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
        )
        if res.returncode == 0 and res.stdout.strip():
            first_line = res.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in first_line.split(",")]
            name = parts[0] if len(parts) > 0 else "NVIDIA GPU"
            vram_mb = int(float(parts[1])) if len(parts) > 1 else 0
            driver = parts[2] if len(parts) > 2 else ""
            return {
                "name": name,
                "vram_gb": round(vram_mb / 1024.0, 1) if vram_mb else 0,
                "driver": driver,
            }
    except Exception:
        pass
    return None


def _detect_ctranslate2_cuda() -> bool:
    try:
        import ctranslate2
        return int(ctranslate2.get_cuda_device_count()) > 0
    except Exception:
        return False


def _detect_ffmpeg_encoders() -> List[str]:
    try:
        res = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=4,
        )
        out = res.stdout
        found = []
        for enc in ("h264_nvenc", "hevc_nvenc", "av1_nvenc", "h264_videotoolbox", "libx264"):
            if enc in out:
                found.append(enc)
        return found
    except Exception:
        return ["libx264"]


def detect_ollama_models() -> List[str]:
    """Check if local Ollama is running on 127.0.0.1:11434 and list installed models."""
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=1.2) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def get_hardware_info(force_refresh: bool = False) -> Dict[str, Any]:
    global _HW_CACHE
    if _HW_CACHE is not None and not force_refresh:
        info = dict(_HW_CACHE)
        info["ollama_models"] = detect_ollama_models()
        return info

    os_name = platform.system()
    arch = platform.machine()
    nvidia = _detect_nvidia_gpu()
    cuda_whisper = _detect_ctranslate2_cuda() if nvidia else False
    encoders = _detect_ffmpeg_encoders()

    has_nvenc = bool(nvidia) and ("h264_nvenc" in encoders)
    has_videotoolbox = (os_name == "Darwin") and ("h264_videotoolbox" in encoders)

    if has_nvenc:
        encoder = "h264_nvenc"
    elif has_videotoolbox:
        encoder = "h264_videotoolbox"
    else:
        encoder = "libx264"

    if nvidia:
        label = f"🟢 {nvidia['name']}"
        if nvidia.get("vram_gb"):
            label += f" ({nvidia['vram_gb']} ГБ)"
        if cuda_whisper and has_nvenc:
            label += " • CUDA + NVENC"
        elif has_nvenc:
            label += " • NVENC"
    elif os_name == "Darwin" and arch == "arm64":
        label = "🍎 Apple Silicon • VideoToolbox"
    else:
        label = f"💻 CPU ({arch})"

    _HW_CACHE = {
        "os": os_name,
        "arch": arch,
        "nvidia": nvidia,
        "cuda_whisper": cuda_whisper,
        "has_nvenc": has_nvenc,
        "has_videotoolbox": has_videotoolbox,
        "preferred_encoder": encoder,
        "encoders": encoders,
        "recommended_whisper": "large-v3-turbo" if cuda_whisper else "small",
        "max_parallel_renders": 2 if has_nvenc else 1,
        "label": label,
    }
    info = dict(_HW_CACHE)
    info["ollama_models"] = detect_ollama_models()
    return info
