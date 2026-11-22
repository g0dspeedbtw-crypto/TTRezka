import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("TIKCUT_DATA_DIR", str(BASE_DIR / "data")))
UPLOADS_DIR = DATA_DIR / "uploads"
JOBS_DIR = DATA_DIR / "jobs"
MUSIC_DIR = DATA_DIR / "music"
AVATARS_DIR = DATA_DIR / "avatars"
ADS_DIR = DATA_DIR / "ads"
SETTINGS_FILE = DATA_DIR / "settings.json"
FONTS_DIR = BASE_DIR / "backend" / "fonts"
STATIC_DIR = BASE_DIR / "static"

for _d in (DATA_DIR, UPLOADS_DIR, JOBS_DIR, MUSIC_DIR, AVATARS_DIR, ADS_DIR, FONTS_DIR, STATIC_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def load_settings() -> Dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    cur = load_settings()
    for k, v in updates.items():
        if v is None:
            cur.pop(k, None)
        else:
            cur[k] = v
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SETTINGS_FILE)
    return cur


# Font definitions: bundled fonts in backend/fonts/ with macOS system fallbacks
FONT_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "montserrat",
        "name": "Montserrat Black",
        "description": "Жирный геометрический — главный тренд TikTok и Reels",
        "css_family": "'Montserrat', 'Arial Black', sans-serif",
        "candidates": [
            str(FONTS_DIR / "Montserrat-Black.ttf"),
            "/Library/Fonts/Rubik.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ],
    },
    {
        "id": "rubik",
        "name": "Rubik Black",
        "description": "Мягкий округлый жирный шрифт с отличной кириллицей",
        "css_family": "'Rubik', 'Arial Rounded MT Bold', sans-serif",
        "candidates": [
            str(FONTS_DIR / "Rubik-Black.ttf"),
            "/Library/Fonts/Rubik.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ],
    },
    {
        "id": "oswald",
        "name": "Oswald Bold",
        "description": "Узкий и высокий — идеально для длинных фраз",
        "css_family": "'Oswald', 'Impact', sans-serif",
        "candidates": [
            str(FONTS_DIR / "Oswald-Bold.ttf"),
            "/System/Library/Fonts/Supplemental/Impact.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ],
    },
    {
        "id": "unbounded",
        "name": "Unbounded Black",
        "description": "Футуристичный широкий шрифт для дерзких клипов",
        "css_family": "'Unbounded', 'Arial Black', sans-serif",
        "candidates": [
            str(FONTS_DIR / "Unbounded-Black.ttf"),
            "/Library/Fonts/Rubik.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ],
    },
    {
        "id": "impact",
        "name": "Impact Classic",
        "description": "Классический мощный шрифт для мемов и виральных роликов",
        "css_family": "'Impact', 'Arial Black', sans-serif",
        "candidates": [
            "/System/Library/Fonts/Supplemental/Impact.ttf",
            str(FONTS_DIR / "Oswald-Bold.ttf"),
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ],
    },
]


def resolve_font_path(font_id: str) -> str:
    """Return the first existing font file path for the given font_id."""
    for item in FONT_CATALOG:
        if item["id"] == font_id:
            for candidate in item["candidates"]:
                if Path(candidate).exists():
                    return candidate
    # Ultimate fallback (macOS & Windows)
    for fallback in (
        str(FONTS_DIR / "Montserrat-Black.ttf"),
        "/Library/Fonts/Rubik.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ):
        if Path(fallback).exists():
            return fallback
    return ""


def get_available_fonts() -> List[Dict[str, Any]]:
    result = []
    for item in FONT_CATALOG:
        resolved = resolve_font_path(item["id"])
        result.append(
            {
                "id": item["id"],
                "name": item["name"],
                "description": item["description"],
                "css_family": item["css_family"],
                "available": bool(resolved),
                "bundled": Path(item["candidates"][0]).exists(),
            }
        )
    return result


# TikTok Subtitle Style Presets
SUBTITLE_STYLES: Dict[str, Dict[str, Any]] = {
    "hormozi": {
        "id": "hormozi",
        "name": "Hormozi Gold",
        "badge": "ХИТ",
        "description": "Белый текст + ярко-жёлтая подсветка активного слова и жирная обводка",
        "text_color": "#FFFFFF",
        "active_color": "#FFE600",
        "stroke_color": "#000000",
        "stroke_width": 8,
        "shadow_color": "#000000CC",
        "shadow_offset": (0, 8),
        "bg_pill_color": None,
        "active_pill_color": None,
        "active_scale": 1.12,
        "uppercase": True,
    },
    "neon": {
        "id": "neon",
        "name": "Neon Cyber",
        "badge": "ТРЕНД",
        "description": "Неоново-бирюзовая подсветка на тёмной полупрозрачной подложке",
        "text_color": "#FFFFFF",
        "active_color": "#00F5FF",
        "stroke_color": "#050A18",
        "stroke_width": 6,
        "shadow_color": "#00F5FF66",
        "shadow_offset": (0, 5),
        "bg_pill_color": "#090D1AD9",
        "active_pill_color": None,
        "active_scale": 1.08,
        "uppercase": True,
    },
    "pill": {
        "id": "pill",
        "name": "Viral Green Pill",
        "badge": "ЧИСТО",
        "description": "Активное слово выделяется яркой неоново-зелёной плашкой",
        "text_color": "#FFFFFF",
        "active_color": "#090D16",
        "stroke_color": "#000000",
        "stroke_width": 5,
        "shadow_color": "#000000B0",
        "shadow_offset": (0, 6),
        "bg_pill_color": None,
        "active_pill_color": "#00FF88",
        "active_scale": 1.04,
        "uppercase": True,
    },
    "fire": {
        "id": "fire",
        "name": "Fire Punch",
        "badge": "ЭМОЦИИ",
        "description": "Огненно-оранжевый акцент для громких и динамичных моментов",
        "text_color": "#FFFDF7",
        "active_color": "#FF4D00",
        "stroke_color": "#000000",
        "stroke_width": 9,
        "shadow_color": "#000000E0",
        "shadow_offset": (0, 9),
        "bg_pill_color": None,
        "active_pill_color": None,
        "active_scale": 1.14,
        "uppercase": True,
    },
    "minimal": {
        "id": "minimal",
        "name": "Minimal Clean",
        "badge": "ЭСТЕТИКА",
        "description": "Аккуратные субтитры без капса с мягким золотым акцентом",
        "text_color": "#F5F7FA",
        "active_color": "#FFD166",
        "stroke_color": "#111827",
        "stroke_width": 5,
        "shadow_color": "#000000AA",
        "shadow_offset": (0, 5),
        "bg_pill_color": "#0000008C",
        "active_pill_color": None,
        "active_scale": 1.04,
        "uppercase": False,
    },
}


def get_subtitle_styles() -> List[Dict[str, Any]]:
    return list(SUBTITLE_STYLES.values())
