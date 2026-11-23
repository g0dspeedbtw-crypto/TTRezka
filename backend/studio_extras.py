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


def auto_cleanup_old_audio(max_age_hours: int = 24) -> Dict[str, Any]:
    """Feature #15: Automatically remove old intermediate WAV & raw segment files older than max_age_hours."""
    cutoff = time.time() - max(1, int(max_age_hours)) * 3600
    freed = 0
    removed = 0
    if JOBS_DIR.exists():
        for f in JOBS_DIR.rglob("*"):
            if not f.is_file():
                continue
            name = f.name.lower()
            if name in ("audio.wav", "light_audio.wav") or name.startswith("raw_seg_") or name.endswith(".tmp"):
                try:
                    st = f.stat()
                    if st.st_mtime < cutoff:
                        freed += st.st_size
                        f.unlink(missing_ok=True)
                        removed += 1
                except OSError:
                    pass
    return {"removed_files": removed, "freed_mb": round(freed / (1024 * 1024), 1)}


# =====================================================================
# Feature #5 & #8 (v3.0): Full Studio Backup/Restore (.zip) & Self-Heal
# =====================================================================

def self_heal_startup() -> int:
    """Delete orphaned tikcut_sub_* temp directories left behind by crashes/power-loss."""
    import tempfile
    cleaned = 0
    tdir = Path(tempfile.gettempdir())
    for p in tdir.glob("tikcut_sub_*"):
        if p.is_dir():
            try:
                shutil.rmtree(p, ignore_errors=True)
                cleaned += 1
            except Exception:
                pass
    return cleaned


def create_studio_backup_zip() -> bytes:
    """Pack accounts, settings, content plan, and all uploaded studio assets into one .zip."""
    import io
    import zipfile
    from .config import DATA_DIR

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname in ("accounts.json", "settings.json", "content_plan.json"):
            fp = DATA_DIR / fname
            if fp.exists():
                zf.write(fp, arcname=fname)
        for dname in ("music", "avatars", "ads", "satisfying", "outros"):
            dpath = DATA_DIR / dname
            if dpath.exists():
                for f in dpath.rglob("*"):
                    if f.is_file():
                        zf.write(f, arcname=f"{dname}/{f.name}")
    return buf.getvalue()


def restore_studio_backup_zip(zip_bytes: bytes) -> Dict[str, Any]:
    """Safely restore accounts, settings, content plan, and studio assets from a backup .zip."""
    import io
    import zipfile
    from .config import DATA_DIR

    allowed_files = {"accounts.json", "settings.json", "content_plan.json"}
    allowed_dirs = {"music", "avatars", "ads", "satisfying", "outros"}
    restored = 0
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            rel = Path(info.filename)
            if rel.is_absolute() or ".." in rel.parts:
                continue
            if len(rel.parts) == 1 and rel.name in allowed_files:
                dest = DATA_DIR / rel.name
                dest.write_bytes(zf.read(info))
                restored += 1
            elif len(rel.parts) == 2 and rel.parts[0] in allowed_dirs:
                dest_dir = DATA_DIR / rel.parts[0]
                dest_dir.mkdir(parents=True, exist_ok=True)
                (dest_dir / rel.name).write_bytes(zf.read(info))
                restored += 1
    return {"ok": True, "restored_files": restored}


# =====================================================================
# Feature #9 (Asset Delete) & #18 (SRT Subtitle Export)
# =====================================================================

def delete_asset_file(kind: str, filename: str) -> bool:
    """Safely delete a user-uploaded asset file by category."""
    from .config import CUSTOM_FONTS_DIR, LOGOS_DIR

    dir_map = {
        "music": MUSIC_DIR,
        "avatars": AVATARS_DIR,
        "ads": ADS_DIR,
        "satisfying": SATISFYING_DIR,
        "outros": OUTROS_DIR,
        "logos": LOGOS_DIR,
        "fonts": CUSTOM_FONTS_DIR,
    }
    target_dir = dir_map.get(kind)
    if not target_dir:
        return False
    safe_name = Path(filename).name
    if not safe_name or safe_name in (".", ".."):
        return False
    p = target_dir / safe_name
    if p.exists() and p.is_file():
        p.unlink(missing_ok=True)
        return True
    return False


def _fmt_srt_ts(sec: float) -> str:
    s = max(0.0, float(sec))
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    rem = s % 60
    whole = int(rem)
    ms = int(round((rem - whole) * 1000))
    if ms >= 1000:
        whole += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{whole:02d},{ms:03d}"


def build_clip_srt(words: List[Dict[str, Any]], clip_start: float, clip_end: float, fallback_text: str = "") -> str:
    """Feature #18 (v3.1): Generate clean time-aligned .SRT subtitles for CapCut / Premiere Pro."""
    rel_words = []
    for w in words or []:
        ws = float(w.get("start", 0.0))
        we = float(w.get("end", ws + 0.25))
        if we >= clip_start and ws <= clip_end:
            rel_words.append({
                "word": str(w.get("word", "")).strip(),
                "start": max(0.0, ws - clip_start),
                "end": max(0.05, min(clip_end - clip_start, we - clip_start)),
            })
    rel_words = [w for w in rel_words if w["word"]]

    if not rel_words:
        txt = (fallback_text or "").strip() or "Без субтитров"
        dur = max(2.0, float(clip_end) - float(clip_start))
        return f"1\n00:00:00,000 --> {_fmt_srt_ts(dur)}\n{txt}\n"

    # Group into crisp 3-5 word chunks
    lines: List[str] = []
    idx = 1
    chunk: List[Dict[str, Any]] = []
    for w in rel_words:
        if chunk and (len(chunk) >= 4 or (w["start"] - chunk[-1]["end"]) > 0.65):
            lines.append(f"{idx}\n{_fmt_srt_ts(chunk[0]['start'])} --> {_fmt_srt_ts(chunk[-1]['end'])}\n{' '.join(x['word'] for x in chunk)}\n")
            idx += 1
            chunk = []
        chunk.append(w)
    if chunk:
        lines.append(f"{idx}\n{_fmt_srt_ts(chunk[0]['start'])} --> {_fmt_srt_ts(chunk[-1]['end'])}\n{' '.join(x['word'] for x in chunk)}\n")
    return "\n".join(lines)
