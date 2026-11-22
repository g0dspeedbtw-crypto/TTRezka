"""Robust Google Gemini REST client with certifi SSL (Windows PyInstaller safe) & dynamic model discovery."""
import json
import re
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CTX = ssl.create_default_context()

PREFERRED_FLASH_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-flash-latest",
    "gemini-1.5-flash",
]


def clean_api_key(raw: str) -> str:
    """Strip whitespace, quotes, newlines and invisible chars from pasted API key."""
    s = (raw or "").strip().strip('"').strip("'")
    s = re.sub(r"[\s\u200b-\u200f\ufeff]+", "", s)
    return s


def _extract_google_error(err: urllib.error.HTTPError) -> Tuple[int, str]:
    body = ""
    try:
        body = err.read().decode("utf-8", errors="ignore")
    except Exception:
        pass
    msg = body
    try:
        j = json.loads(body)
        msg = (j.get("error") or {}).get("message") or body
    except Exception:
        pass
    return err.code, (msg or "").strip()


def discover_best_gemini_model(api_key: str) -> Tuple[str, List[str]]:
    """
    Call Google's /v1beta/models endpoint to validate the key and return
    (best_model_name, all_supported_flash_models).
    """
    key = clean_api_key(api_key)
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    req = urllib.request.Request(
        url,
        headers={"x-goog-api-key": key, "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))

    available: List[str] = []
    for m in data.get("models", []):
        methods = m.get("supportedGenerationMethods") or []
        if "generateContent" not in methods:
            continue
        name = (m.get("name") or "").replace("models/", "").strip()
        if name:
            available.append(name)

    # Pick highest-priority Flash model actually available on this key
    for pref in PREFERRED_FLASH_MODELS:
        if pref in available:
            return pref, available

    for name in available:
        if "gemini" in name and "flash" in name:
            return name, available

    for name in available:
        if "gemini" in name:
            return name, available

    return "gemini-2.5-flash", available


def is_vertex_express_key(api_key: str) -> bool:
    """Detect Google Cloud Vertex AI Express Mode API keys (start with 'AQ.')."""
    return clean_api_key(api_key).startswith("AQ.")


def gemini_generate_text(
    api_key: str,
    prompt: str,
    model_name: Optional[str] = None,
    json_mode: bool = False,
    max_tokens: Optional[int] = None,
    timeout: int = 60,
) -> Tuple[str, str]:
    """
    Generate text with Gemini REST API — automatically supports BOTH:
      - Google AI Studio keys (`AIza...`) -> generativelanguage.googleapis.com
      - Vertex AI Express Mode keys (`AQ....`) -> aiplatform.googleapis.com
    Uses certifi SSL context (Windows PyInstaller safe).
    """
    key = clean_api_key(api_key)
    vertex_mode = is_vertex_express_key(key)
    models_to_try: List[str] = []

    if model_name:
        models_to_try.append(model_name)
    elif vertex_mode:
        models_to_try.extend(["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-flash-lite"])
    else:
        try:
            best, avail = discover_best_gemini_model(key)
            models_to_try.append(best)
            for pref in PREFERRED_FLASH_MODELS:
                if pref in avail and pref not in models_to_try:
                    models_to_try.append(pref)
        except urllib.error.HTTPError:
            raise
        except Exception:
            models_to_try.extend(PREFERRED_FLASH_MODELS[:4])

    if not models_to_try:
        models_to_try = PREFERRED_FLASH_MODELS[:4]

    gen_cfg: Dict[str, Any] = {"temperature": 0.45}
    if json_mode:
        gen_cfg["responseMimeType"] = "application/json"
    if max_tokens is not None:
        gen_cfg["maxOutputTokens"] = max_tokens

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": gen_cfg,
    }
    raw_body = json.dumps(payload).encode("utf-8")

    last_err: Optional[Exception] = None
    for mdl in models_to_try[:4]:
        if vertex_mode:
            url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/{mdl}:generateContent?key={key}"
            headers = {"Content-Type": "application/json"}
        else:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={key}"
            headers = {"Content-Type": "application/json", "x-goog-api-key": key}

        try:
            req = urllib.request.Request(url, data=raw_body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            cands = data.get("candidates") or []
            if cands:
                text = (((cands[0].get("content") or {}).get("parts") or [{}])[0].get("text") or "").strip()
                if text:
                    label = f"{mdl} (Vertex AI)" if vertex_mode else mdl
                    return text, label
        except urllib.error.HTTPError as e:
            code, msg = _extract_google_error(e)
            last_err = RuntimeError(f"HTTP {code}: {msg}")
            low = msg.lower()
            if code in (401, 403) or "api key not valid" in low or "api_key_invalid" in low or "location is not supported" in low:
                raise last_err
            continue
        except Exception as exc:
            last_err = exc
            continue

    if last_err:
        raise last_err
    raise RuntimeError("Пустой ответ от Gemini API")


def test_gemini_key(api_key: str) -> Dict[str, Any]:
    """Validate a Gemini API key and return a clear Russian diagnostic result."""
    key = clean_api_key(api_key)
    if len(key) < 15:
        return {"ok": False, "message": "❌ Ключ слишком короткий — проверьте, что скопировали его целиком"}

    try:
        _txt, mdl = gemini_generate_text(
            api_key=key,
            prompt="Ответь одним словом: ОК",
            json_mode=False,
            max_tokens=8,
            timeout=15,
        )
        return {
            "ok": True,
            "model": mdl,
            "message": f"✅ Ключ работает и сохранён! Активна модель {mdl}",
        }
    except urllib.error.HTTPError as e:
        code, msg = _extract_google_error(e)
        return {"ok": False, "message": _friendly_error(code, msg)}
    except Exception as exc:
        msg = str(exc)
        low = msg.lower()
        if "http " in low:
            m = re.search(r"HTTP\s+(\d+):\s*(.*)", msg, re.DOTALL)
            if m:
                return {"ok": False, "message": _friendly_error(int(m.group(1)), m.group(2))}
        return {"ok": False, "message": f"⚠️ Ошибка подключения к Google API: {msg[:160]}"}


def _friendly_error(code: int, msg: str) -> str:
    low = (msg or "").lower()
    if "api key not valid" in low or "api_key_invalid" in low or code == 401:
        return "❌ Неверный API-ключ — проверьте на aistudio.google.com/apikey"
    if "user location is not supported" in low:
        return "⚠️ Gemini API заблокирован в вашем регионе — включите VPN и проверьте снова"
    if code == 403:
        return f"⚠️ Доступ запрещён (403): {msg[:140]}"
    if code == 429 or "quota" in low or "resource_exhausted" in low:
        return "⏳ Превышен лимит запросов (квота ключа) — подождите минуту или создайте новый ключ"
    return f"❌ Ошибка Gemini API (HTTP {code}): {msg[:150]}"
