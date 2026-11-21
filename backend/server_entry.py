"""Standalone entrypoint for launching TikCut Studio backend (dev & desktop app)."""
import argparse
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path when executed directly
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _register_windows_cuda_dlls() -> None:
    """Register bundled NVIDIA CUDA/cuBLAS/cuDNN DLL directories on Windows."""
    if os.name != "nt":
        return
    candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        candidates.extend([
            meipass,
            meipass / "nvidia" / "cublas" / "bin",
            meipass / "nvidia" / "cudnn" / "bin",
            meipass / "cuda_dlls",
        ])
    # Also check site-packages nvidia wheels in dev mode
    for sp in sys.path:
        p = Path(sp)
        candidates.extend([
            p / "nvidia" / "cublas" / "bin",
            p / "nvidia" / "cudnn" / "bin",
        ])

    added = []
    for d in candidates:
        if d.exists() and d.is_dir():
            s = str(d)
            if s not in added:
                added.append(s)
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(s)
                    except Exception:
                        pass
    if added:
        os.environ["PATH"] = os.pathsep.join(added) + os.pathsep + os.environ.get("PATH", "")


_register_windows_cuda_dlls()

import uvicorn
from backend.main import app


def main() -> None:
    parser = argparse.ArgumentParser(description="TikCut Studio Backend Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
