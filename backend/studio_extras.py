import datetime
import json
import re
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import (
    ADS_DIR,
    AVATARS_DIR,
    CONTENT_PLAN_FILE,
    EXPORTS_DIR,
    JOBS_DIR,
    MUSIC_DIR,
    OUTROS_DIR,
    SATISFYING_DIR,
    UPLOADS_DIR,
)

_PLAN_LOCK = threading.Lock()


# =====================================================================
# Feature #12: Manual Timecodes Parser
# =====================================================================

def _parse_ts_to_sec(token: str) -> Optional[float]:
    parts = [p.strip() for p in token.strip().split(":")]
    if not parts or len(parts) > 3:
        return None
    try:
        nums = [float(p.replace(",", ".")) for p in parts]
    except ValueError:
        return None
    if len(nums) == 1:
        return nums[0]
    if len(nums) == 2:
        return nums[0] * 60.0 + nums[1]
    return nums[0] * 3600.0 + nums[1] * 60.0 + nums[2]


def parse_manual_timecodes(raw_text: str, total_duration: float = 0.0) -> List[Dict[str, Any]]:
    """
    Parse user-supplied timecodes like:
      12:40-13:25
      1:02:15 - 1:03:00 Смешной момент
      45:10..45:55 | Жесткий клатч
    Returns a list of highlight dicts ready for local or remote pipeline.
    """
    if not raw_text or not raw_text.strip():
        return []

    pattern = re.compile(
        r"(\d{1,2}:\d{2}(?::\d{2})?)\s*(?:-|–|—|\.\.|to|до)\s*(\d{1,2}:\d{2}(?::\d{2})?)(.*)",
        re.IGNORECASE,
    )
    results: List[Dict[str, Any]] = []
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = pattern.search(line)
        if not m:
            continue
        start_s = _parse_ts_to_sec(m.group(1))
        end_s = _parse_ts_to_sec(m.group(2))
        if start_s is None or end_s is None or end_s <= start_s + 1.5:
            continue
        if total_duration > 0:
            start_s = max(0.0, min(start_s, total_duration - 2.0))
            end_s = max(start_s + 2.0, min(end_s, total_duration))
        label = m.group(3).strip(" |-–—:\t")
        idx = len(results) + 1
        title = label[:72] if label else f"Момент #{idx} ({m.group(1)}–{m.group(2)})"
        results.append(
            {
                "id": f"clip_{idx:02d}",
                "index": idx,
                "start": round(start_s, 2),
                "end": round(end_s, 2),
                "duration": round(end_s - start_s, 2),
                "title": title,
                "hook_text": title,
                "viral_score": 95,
                "tags": ["✂️ Ручной таймкод"],
                "transcript": "",
            }
        )
    return results


# =====================================================================
# Feature #19: Content Plan / Publishing Calendar
# =====================================================================

def _load_plan_unlocked() -> List[Dict[str, Any]]:
    if not CONTENT_PLAN_FILE.exists():
        return []
    try:
        data = json.loads(CONTENT_PLAN_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_plan_unlocked(items: List[Dict[str, Any]]) -> None:
    tmp = CONTENT_PLAN_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CONTENT_PLAN_FILE)


def list_plan_items() -> List[Dict[str, Any]]:
    with _PLAN_LOCK:
        items = _load_plan_unlocked()
    items.sort(key=lambda x: (x.get("scheduled_date", ""), x.get("scheduled_time", "")))
    return items


def add_plan_item(
    title: str,
    account_id: str = "",
    account_name: str = "Основной",
    platform: str = "tiktok",
    scheduled_date: str = "",
    scheduled_time: str = "18:00",
    job_id: str = "",
    clip_id: str = "",
    notes: str = "",
) -> Dict[str, Any]:
    if not scheduled_date:
        scheduled_date = datetime.date.today().isoformat()
    item = {
        "id": f"plan_{uuid.uuid4().hex[:8]}",
        "title": (title or "Без названия").strip()[:90],
        "account_id": account_id,
        "account_name": account_name or "Основной",
        "platform": platform if platform in ("tiktok", "youtube", "instagram") else "tiktok",
        "scheduled_date": scheduled_date,
        "scheduled_time": scheduled_time or "18:00",
        "status": "planned",
        "job_id": job_id,
        "clip_id": clip_id,
        "notes": notes.strip()[:240],
        "created_at": time.time(),
    }
    with _PLAN_LOCK:
        items = _load_plan_unlocked()
        items.append(item)
        _save_plan_unlocked(items)
    return item


def update_plan_item(item_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed = {"title", "account_id", "account_name", "platform", "scheduled_date", "scheduled_time", "status", "notes"}
    with _PLAN_LOCK:
        items = _load_plan_unlocked()
        found = None
        for it in items:
            if it.get("id") == item_id:
                for k, v in updates.items():
                    if k in allowed and v is not None:
                        it[k] = v
                found = dict(it)
                break
        if found is not None:
            _save_plan_unlocked(items)
    return found


def delete_plan_item(item_id: str) -> bool:
    with _PLAN_LOCK:
        items = _load_plan_unlocked()
        new_items = [it for it in items if it.get("id") != item_id]
        if len(new_items) == len(items):
            return False
        _save_plan_unlocked(new_items)
    return True


# =====================================================================
# Feature #18: Disk & Cache Manager
# =====================================================================

def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def get_disk_usage_stats() -> Dict[str, Any]:
    uploads_b = _dir_size_bytes(UPLOADS_DIR)
    exports_b = _dir_size_bytes(EXPORTS_DIR)
    assets_b = sum(
        _dir_size_bytes(d)
        for d in (MUSIC_DIR, AVATARS_DIR, ADS_DIR, SATISFYING_DIR, OUTROS_DIR)
    )

    jobs_sources_b = 0
    jobs_clips_b = 0
    jobs_temp_b = 0
    if JOBS_DIR.exists():
        for jdir in JOBS_DIR.iterdir():
            if not jdir.is_dir():
                continue
            for f in jdir.rglob("*"):
                if not f.is_file():
                    continue
                try:
                    sz = f.stat().st_size
                except OSError:
                    continue
                name = f.name.lower()
                if name.startswith("clip_") and name.endswith((".mp4", ".jpg")):
                    jobs_clips_b += sz
                elif name.startswith("source.") or name in ("audio.wav", "light_audio.wav") or name.startswith("raw_"):
                    jobs_sources_b += sz
                elif name.endswith(".tmp") or "tmp" in f.parts:
                    jobs_temp_b += sz
                else:
                    jobs_clips_b += sz

    total_sources_b = uploads_b + jobs_sources_b
    total_b = total_sources_b + jobs_clips_b + assets_b + exports_b + jobs_temp_b

    def mb(b: int) -> float:
        return round(b / (1024 * 1024), 1)

    return {
        "total_mb": mb(total_b),
        "sources_mb": mb(total_sources_b),
        "clips_mb": mb(jobs_clips_b),
        "assets_mb": mb(assets_b),
        "exports_mb": mb(exports_b),
        "temp_mb": mb(jobs_temp_b),
    }


def cleanup_old_sources(older_than_days: int = 7) -> Dict[str, Any]:
    """Delete heavy source videos & intermediate audio older than N days while keeping rendered clips."""
    cutoff = time.time() - max(0, older_than_days) * 86400
    freed = 0
    removed_files = 0

    for root in (UPLOADS_DIR, JOBS_DIR):
        if not root.exists():
            continue
        for f in root.rglob("*"):
            if not f.is_file():
                continue
            name = f.name.lower()
            is_heavy_source = (
                root == UPLOADS_DIR
                or name.startswith("source.")
                or name in ("audio.wav", "light_audio.wav")
                or name.startswith("raw_seg_")
            )
            if not is_heavy_source:
                continue
            try:
                st = f.stat()
                if older_than_days == 0 or st.st_mtime < cutoff:
                    sz = st.st_size
                    f.unlink(missing_ok=True)
                    freed += sz
                    removed_files += 1
            except OSError:
                pass

    return {
        "removed_files": removed_files,
        "freed_mb": round(freed / (1024 * 1024), 1),
        "stats": get_disk_usage_stats(),
    }


def cleanup_temp_cache() -> Dict[str, Any]:
    """Delete temporary scratch files and intermediate raw downloads across jobs."""
    freed = 0
    removed_files = 0
    if JOBS_DIR.exists():
        for f in JOBS_DIR.rglob("*"):
            if not f.is_file():
                continue
            name = f.name.lower()
            if name.endswith(".tmp") or name in ("audio.wav", "light_audio.wav") or name.startswith("raw_"):
                try:
                    sz = f.stat().st_size
                    f.unlink(missing_ok=True)
                    freed += sz
                    removed_files += 1
                except OSError:
                    pass
    return {
        "removed_files": removed_files,
        "freed_mb": round(freed / (1024 * 1024), 1),
        "stats": get_disk_usage_stats(),
    }
