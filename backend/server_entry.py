"""Standalone entrypoint for launching TikCut Studio backend (dev & desktop app)."""
import argparse
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path when executed directly
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
