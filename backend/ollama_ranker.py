"""Optional local Ollama LLM viral-hook re-ranker & Russian title writer (runs on RTX GPU)."""
import json
import re
import urllib.request
from typing import Any, Dict, List


def enhance_highlights_with_ollama(
    highlights: List[Dict[str, Any]],
    model_name: str,
) -> List[Dict[str, Any]]:
    """
    Ask a local Ollama model (running on RTX GPU) to evaluate each highlight's
    Russian transcript, boost viral scores, and write punchy TikTok hook titles.
    """
    if not highlights or not model_name:
        return highlights

    items_desc = []
    for h in highlights:
        txt = (h.get("transcript") or "")[:360]
        items_desc.append(f'ID: {h["id"]} | Текст: "{txt}"')

    prompt = (
        "Ты опытный продюсер вирусных TikTok / Shorts нарезок на русском языке.\n"
        "Оцени следующие фрагменты видео/стрима по вирусности (от 60 до 99) и придумай для каждого "
        "короткий цепляющий заголовок-хук на русском (до 6 слов, без кавычек).\n"
        "Верни ТОЛЬКО валидный JSON массив вида:\n"
        '[{"id": "clip_1", "score": 94, "title": "ОН НЕ ОЖИДАЛ ТАКОГО ФИНАЛА"}]\n\n'
        + "\n".join(items_desc)
    )

    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.4, "num_predict": 512},
    }

    try:
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = json.loads(resp.read().decode("utf-8", errors="ignore"))
        text = (raw.get("response") or "").strip()
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if not m:
            return highlights
        parsed = json.loads(m.group(0))
        by_id = {str(item.get("id")): item for item in parsed if isinstance(item, dict)}

        for h in highlights:
            info = by_id.get(h["id"])
            if not info:
                continue
            if info.get("title"):
                h["title"] = str(info["title"]).strip()[:64]
            if isinstance(info.get("score"), (int, float)):
                ai_sc = int(max(55, min(99, round(float(info["score"])))))
                h["viral_score"] = int(round(0.45 * h.get("viral_score", 75) + 0.55 * ai_sc))
            tags = list(h.get("tags") or [])
            if "🧠 RTX AI Выбор" not in tags:
                tags.insert(0, "🧠 RTX AI Выбор")
            h["tags"] = tags[:3]

        highlights.sort(key=lambda x: x.get("viral_score", 0), reverse=True)
        return highlights
    except Exception:
        return highlights
