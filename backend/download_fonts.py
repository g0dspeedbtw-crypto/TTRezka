"""Download Cyrillic-capable TikTok display TTF fonts from Google Fonts."""
import re
import urllib.request
from pathlib import Path
from backend.config import FONTS_DIR

FONT_SPECS = [
    ("Montserrat-Black.ttf", "https://fonts.googleapis.com/css2?family=Montserrat:wght@900&subset=cyrillic"),
    ("Rubik-Black.ttf", "https://fonts.googleapis.com/css2?family=Rubik:wght@900&subset=cyrillic"),
    ("Oswald-Bold.ttf", "https://fonts.googleapis.com/css2?family=Oswald:wght@700&subset=cyrillic"),
    ("Unbounded-Black.ttf", "https://fonts.googleapis.com/css2?family=Unbounded:wght@900&subset=cyrillic"),
]


def download_all() -> None:
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    for filename, css_url in FONT_SPECS:
        dest = FONTS_DIR / filename
        if dest.exists() and dest.stat().st_size > 10_000:
            print(f"[ok] {filename} already exists ({dest.stat().st_size // 1024} KB)")
            continue
        try:
            # Default Python urllib User-Agent causes Google Fonts to return direct .ttf URLs!
            req = urllib.request.Request(css_url, headers={"User-Agent": "Python-urllib/3.9"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                css = resp.read().decode("utf-8", errors="ignore")
            urls = re.findall(r"url\((https://[^)]+\.ttf)\)", css)
            if not urls:
                print(f"[warn] No .ttf URL found in CSS for {filename}")
                continue
            ttf_url = urls[0]
            urllib.request.urlretrieve(ttf_url, str(dest))
            print(f"[downloaded] {filename} ({dest.stat().st_size // 1024} KB)")
        except Exception as exc:
            print(f"[error] Failed {filename}: {exc}")


if __name__ == "__main__":
    download_all()
