"""Persistent multi-account TikTok Studio profiles & per-account presets."""
import json
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.config import DATA_DIR

ACCOUNTS_FILE = DATA_DIR / "accounts.json"


def _load_all() -> List[Dict[str, Any]]:
    if not ACCOUNTS_FILE.exists():
        return []
    try:
        data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_all(accounts: List[Dict[str, Any]]) -> None:
    tmp = ACCOUNTS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(accounts, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(ACCOUNTS_FILE)


def list_accounts() -> List[Dict[str, Any]]:
    return _load_all()


def get_account(account_id: str) -> Optional[Dict[str, Any]]:
    for acc in _load_all():
        if acc.get("id") == account_id:
            return acc
    return None


def create_account(
    name: str,
    handle: str = "",
    color: str = "#7c5cff",
    default_hashtags: str = "#нарезки #тикток #стрим #рекомендации #shorts",
    caption_template: str = "{title} 🔥\n\n{hashtags}",
    preset: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    accounts = _load_all()
    clean_handle = (handle or "").strip()
    if clean_handle and not clean_handle.startswith("@"):
        clean_handle = "@" + clean_handle

    acc = {
        "id": f"acc_{uuid.uuid4().hex[:8]}",
        "name": (name or clean_handle or "TikTok Аккаунт").strip()[:40],
        "handle": clean_handle[:36],
        "color": color or "#7c5cff",
        "default_hashtags": (default_hashtags or "").strip(),
        "caption_template": (caption_template or "{title} 🔥\n\n{hashtags}").strip(),
        "preset": preset or {},
        "published_count": 0,
        "created_at": int(time.time()),
    }
    accounts.append(acc)
    _save_all(accounts)
    return acc


def update_account(account_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    accounts = _load_all()
    updated = None
    for acc in accounts:
        if acc.get("id") == account_id:
            for k in ("name", "handle", "color", "default_hashtags", "caption_template", "preset"):
                if k in updates and updates[k] is not None:
                    val = updates[k]
                    if k == "handle" and isinstance(val, str) and val.strip() and not val.strip().startswith("@"):
                        val = "@" + val.strip()
                    acc[k] = val
            updated = dict(acc)
            break
    if updated is not None:
        _save_all(accounts)
    return updated


def delete_account(account_id: str) -> bool:
    accounts = _load_all()
    filtered = [a for a in accounts if a.get("id") != account_id]
    if len(filtered) == len(accounts):
        return False
    _save_all(filtered)
    return True


def increment_published(account_id: str) -> Optional[Dict[str, Any]]:
    accounts = _load_all()
    updated = None
    for acc in accounts:
        if acc.get("id") == account_id:
            acc["published_count"] = int(acc.get("published_count", 0)) + 1
            updated = dict(acc)
            break
    if updated is not None:
        _save_all(accounts)
    return updated
