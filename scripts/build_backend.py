"""Cross-platform PyInstaller bundler for TikCut Studio backend (macOS & Windows)."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "desktop" / "backend-dist"
BUILD_WORK = ROOT / "build" / "pyinstaller"


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    sep = ";" if os.name == "nt" else ":"
    static_src = ROOT / "static"
    fonts_src = ROOT / "backend" / "fonts"
    changelog_src = ROOT / "CHANGELOG.md"

    # On Windows, bundle NVIDIA cuBLAS 12 / cuDNN 9 DLLs if installed so RTX CUDA works out-of-the-box!
    extra_bins = []
    if os.name == "nt":
        import site
        sp_dirs = [Path(p) for p in site.getsitepackages()] + [Path(sys.prefix) / "Lib" / "site-packages"]
        seen_dlls = set()
        for sp in sp_dirs:
            for sub in ("nvidia/cublas/bin", "nvidia/cudnn/bin"):
                d = sp / sub
                if d.exists():
                    for dll in d.glob("*.dll"):
                        if dll.name.lower() not in seen_dlls:
                            seen_dlls.add(dll.name.lower())
                            extra_bins.append(f"--add-binary={dll}{sep}cuda_dlls")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        "tikcut-backend",
        "--distpath",
        str(OUT_DIR),
        "--workpath",
        str(BUILD_WORK),
        "--specpath",
        str(BUILD_WORK),
        f"--add-data={static_src}{sep}static",
        f"--add-data={fonts_src}{sep}backend/fonts",
        f"--add-data={changelog_src}{sep}.",
        *extra_bins,
        "--collect-all",
        "faster_whisper",
        "--collect-all",
        "ctranslate2",
        "--collect-all",
        "onnxruntime",
        "--collect-all",
        "yt_dlp",
        "--collect-all",
        "cv2",
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        "--hidden-import",
        "uvicorn.lifespan.on",
        str(ROOT / "backend" / "server_entry.py"),
    ]

    env = dict(os.environ)
    cache_dir = ROOT / "build" / "pyinstaller_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    env["PYINSTALLER_CONFIG_DIR"] = str(cache_dir)

    print("Running PyInstaller:", " ".join(cmd))
    subprocess.run(cmd, cwd=str(ROOT), env=env, check=True)
    print(f"Backend bundle ready at: {OUT_DIR / 'tikcut-backend'}")


if __name__ == "__main__":
    main()
