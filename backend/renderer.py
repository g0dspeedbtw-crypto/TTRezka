"""9:16 vertical video formatter and Pillow-powered TikTok word-by-word subtitle renderer."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from backend.config import SUBTITLE_STYLES, resolve_font_path

VIDEO_W = 1080
VIDEO_H = 1920
SUB_CANVAS_W = 1080
SUB_CANVAS_H = 440


def probe_video(video_path: Path) -> Dict[str, Any]:
    """Return video metadata (duration, width, height, fps, has_audio) via ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {res.stderr[-300:]}")

    data = json.loads(res.stdout)
    fmt = data.get("format", {})
    streams = data.get("streams", [])

    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = float(fmt.get("duration") or (v_stream.get("duration") if v_stream else 0) or 0)
    width = int(v_stream.get("width", 1920)) if v_stream else 1920
    height = int(v_stream.get("height", 1080)) if v_stream else 1080

    fps = 30.0
    if v_stream and v_stream.get("avg_frame_rate"):
        try:
            num, den = v_stream["avg_frame_rate"].split("/")
            if float(den) > 0:
                fps = round(float(num) / float(den), 2)
        except Exception:
            pass

    return {
        "duration": round(duration, 2),
        "width": width,
        "height": height,
        "fps": fps,
        "has_audio": a_stream is not None,
    }


def _hex_to_rgba(hex_color: Optional[str], default_alpha: int = 255) -> Optional[Tuple[int, int, int, int]]:
    if not hex_color:
        return None
    h = hex_color.lstrip("#")
    if len(h) == 6:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), default_alpha)
    if len(h) == 8:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16))
    return (255, 255, 255, default_alpha)


def _group_words_into_chunks(
    clip_words: List[Dict[str, Any]],
    max_words: int = 4,
    max_chars: int = 24,
) -> List[List[Dict[str, Any]]]:
    """Group clip-relative words into punchy TikTok caption chunks (2-4 words)."""
    chunks: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    cur_chars = 0

    for w in clip_words:
        txt = w["word"].strip()
        if not txt:
            continue
        if cur:
            gap = w["start"] - cur[-1]["end"]
            prev_ends_sentence = cur[-1]["word"].rstrip().endswith((".", "!", "?", "…"))
            if (
                len(cur) >= max_words
                or (cur_chars + len(txt) + 1) > max_chars
                or gap > 0.55
                or prev_ends_sentence
            ):
                chunks.append(cur)
                cur = []
                cur_chars = 0
        cur.append(w)
        cur_chars += len(txt) + (1 if cur_chars else 0)

    if cur:
        chunks.append(cur)
    return chunks


def _build_subtitle_timeline(
    words: List[Dict[str, Any]],
    clip_start: float,
    clip_end: float,
) -> List[Dict[str, Any]]:
    """
    Build a contiguous timeline covering [0, clip_duration] of subtitle states.
    Each item: {"start": float, "end": float, "words": list|None, "active_idx": int}
    """
    clip_dur = max(0.1, clip_end - clip_start)
    rel_words: List[Dict[str, Any]] = []
    for w in words:
        if w["end"] <= clip_start or w["start"] >= clip_end:
            continue
        ws = max(0.0, w["start"] - clip_start)
        we = min(clip_dur, max(ws + 0.08, w["end"] - clip_start))
        rel_words.append({"word": w["word"].strip(), "start": ws, "end": we})

    chunks = _group_words_into_chunks(rel_words)
    events: List[Dict[str, Any]] = []

    for chunk in chunks:
        for idx, w in enumerate(chunk):
            ev_start = w["start"]
            # Extend smoothly to the start of the next word in the same chunk (up to 0.35s)
            if idx + 1 < len(chunk):
                ev_end = min(chunk[idx + 1]["start"], w["end"] + 0.35)
                ev_end = max(ev_end, w["end"])
                if ev_end > chunk[idx + 1]["start"]:
                    ev_end = chunk[idx + 1]["start"]
            else:
                ev_end = min(clip_dur, w["end"] + 0.18)

            if ev_end - ev_start < 0.04:
                ev_end = min(clip_dur, ev_start + 0.06)

            events.append(
                {
                    "start": ev_start,
                    "end": ev_end,
                    "words": [x["word"] for x in chunk],
                    "active_idx": idx,
                }
            )

    # Fill gaps with blank frames so concat demuxer stays 100% synced
    timeline: List[Dict[str, Any]] = []
    cursor = 0.0
    for ev in events:
        s = max(cursor, ev["start"])
        e = max(s + 0.03, min(clip_dur, ev["end"]))
        if s > cursor + 0.03:
            timeline.append({"start": cursor, "end": s, "words": None, "active_idx": -1})
        timeline.append(
            {
                "start": s,
                "end": e,
                "words": ev["words"],
                "active_idx": ev["active_idx"],
            }
        )
        cursor = e

    if cursor < clip_dur - 0.02:
        timeline.append({"start": cursor, "end": clip_dur, "words": None, "active_idx": -1})

    if not timeline:
        timeline.append({"start": 0.0, "end": clip_dur, "words": None, "active_idx": -1})

    return timeline


def _render_subtitle_frame(
    words_list: List[str],
    active_idx: int,
    style: Dict[str, Any],
    font_path: str,
    base_font_size: int,
    uppercase: bool,
) -> Image.Image:
    """Render a crisp 1080x440 transparent RGBA TikTok subtitle frame with Pillow."""
    img = Image.new("RGBA", (SUB_CANVAS_W, SUB_CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    display_words = [w.upper() if uppercase else w for w in words_list]
    active_scale = float(style.get("active_scale", 1.1))
    stroke_w = int(style.get("stroke_width", 7))
    text_rgba = _hex_to_rgba(style.get("text_color", "#FFFFFF"))
    active_rgba = _hex_to_rgba(style.get("active_color", "#FFE600"))
    stroke_rgba = _hex_to_rgba(style.get("stroke_color", "#000000"))
    shadow_rgba = _hex_to_rgba(style.get("shadow_color", "#000000CC"))
    shadow_dx, shadow_dy = style.get("shadow_offset", (0, 7))
    bg_pill_rgba = _hex_to_rgba(style.get("bg_pill_color"))
    active_pill_rgba = _hex_to_rgba(style.get("active_pill_color"))

    font_normal = ImageFont.truetype(font_path, base_font_size)
    font_active = ImageFont.truetype(font_path, int(round(base_font_size * active_scale)))

    # Wrap words into at most 2 centered lines within max_line_w
    max_line_w = SUB_CANVAS_W - 140
    space_w = int(base_font_size * 0.32)

    def _measure_word(idx: int) -> Tuple[int, int]:
        f = font_active if idx == active_idx else font_normal
        bbox = draw.textbbox((0, 0), display_words[idx], font=f, stroke_width=stroke_w)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])

    lines: List[List[int]] = []
    cur_line: List[int] = []
    cur_w = 0
    for i in range(len(display_words)):
        ww, _wh = _measure_word(i)
        add_w = ww + (space_w if cur_line else 0)
        if cur_line and cur_w + add_w > max_line_w:
            lines.append(cur_line)
            cur_line = [i]
            cur_w = ww
        else:
            cur_line.append(i)
            cur_w += add_w
    if cur_line:
        lines.append(cur_line)

    line_height = int(base_font_size * 1.38)
    total_h = len(lines) * line_height
    start_y = (SUB_CANVAS_H - total_h) // 2

    # Compute exact positions of each word
    placements: List[Dict[str, Any]] = []
    min_x, min_y = SUB_CANVAS_W, SUB_CANVAS_H
    max_x, max_y = 0, 0

    for row_idx, line in enumerate(lines):
        widths = [_measure_word(i)[0] for i in line]
        line_w = sum(widths) + space_w * max(0, len(line) - 1)
        x = (SUB_CANVAS_W - line_w) // 2
        y_center = start_y + row_idx * line_height + line_height // 2

        for i, ww in zip(line, widths):
            is_active = i == active_idx
            f = font_active if is_active else font_normal
            word_txt = display_words[i]
            bbox = draw.textbbox((0, 0), word_txt, font=f, stroke_width=stroke_w)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            # Anchor at (x, y_center) adjusted by bbox offsets for crisp vertical alignment
            tx = x - bbox[0]
            ty = y_center - th // 2 - bbox[1]

            placements.append(
                {
                    "text": word_txt,
                    "font": f,
                    "tx": tx,
                    "ty": ty,
                    "box": (x, y_center - th // 2, x + tw, y_center + th // 2),
                    "is_active": is_active,
                }
            )
            min_x = min(min_x, x)
            min_y = min(min_y, y_center - th // 2)
            max_x = max(max_x, x + tw)
            max_y = max(max_y, y_center + th // 2)
            x += ww + space_w

    # Optional phrase background pill
    if bg_pill_rgba and placements:
        pad_x, pad_y = 34, 22
        draw.rounded_rectangle(
            [min_x - pad_x, min_y - pad_y, max_x + pad_x, max_y + pad_y],
            radius=28,
            fill=bg_pill_rgba,
        )

    # Optional active-word pill (e.g. Viral Green Pill style)
    if active_pill_rgba:
        for p in placements:
            if p["is_active"]:
                bx0, by0, bx1, by1 = p["box"]
                draw.rounded_rectangle(
                    [bx0 - 18, by0 - 10, bx1 + 18, by1 + 12],
                    radius=18,
                    fill=active_pill_rgba,
                )

    # Draw shadow + stroked text
    for p in placements:
        is_active = p["is_active"]
        fill_col = active_rgba if is_active else text_rgba
        sw = 0 if (is_active and active_pill_rgba) else stroke_w

        if shadow_rgba and not (is_active and active_pill_rgba):
            draw.text(
                (p["tx"] + shadow_dx, p["ty"] + shadow_dy),
                p["text"],
                font=p["font"],
                fill=shadow_rgba,
                stroke_width=sw,
                stroke_fill=shadow_rgba,
            )

        draw.text(
            (p["tx"], p["ty"]),
            p["text"],
            font=p["font"],
            fill=fill_col,
            stroke_width=sw,
            stroke_fill=stroke_rgba if sw > 0 else None,
        )

    return img


def render_clip(
    source_video: Path,
    output_mp4: Path,
    thumb_jpg: Path,
    clip_start: float,
    clip_end: float,
    words: List[Dict[str, Any]],
    style_id: str = "hormozi",
    font_id: str = "montserrat",
    font_size: str = "medium",
    crop_mode: str = "fill",
    position: str = "lower_third",
    uppercase: Optional[bool] = None,
) -> Path:
    """
    Render a 1080x1920 9:16 TikTok MP4 clip with word-by-word animated subtitles.
    """
    style = SUBTITLE_STYLES.get(style_id, SUBTITLE_STYLES["hormozi"])
    font_path = resolve_font_path(font_id)
    size_map = {"small": 56, "medium": 68, "large": 80}
    base_px = size_map.get(font_size, 68)
    use_upper = style.get("uppercase", True) if uppercase is None else uppercase

    pos_y_map = {
        "center": 740,
        "lower_third": 1160,
        "bottom": 1340,
    }
    overlay_y = pos_y_map.get(position, 1160)

    clip_duration = max(0.5, clip_end - clip_start)
    timeline = _build_subtitle_timeline(words, clip_start, clip_end)

    tmp_dir = Path(tempfile.mkdtemp(prefix="tikcut_sub_"))
    try:
        blank_path = tmp_dir / "blank.png"
        Image.new("RGBA", (SUB_CANVAS_W, SUB_CANVAS_H), (0, 0, 0, 0)).save(blank_path)

        concat_lines: List[str] = ["ffconcat version 1.0"]
        last_file = blank_path
        for idx, item in enumerate(timeline):
            dur = max(0.033, item["end"] - item["start"])
            if item["words"]:
                png_path = tmp_dir / f"sub_{idx:04d}.png"
                frame_img = _render_subtitle_frame(
                    item["words"],
                    item["active_idx"],
                    style,
                    font_path,
                    base_px,
                    use_upper,
                )
                frame_img.save(png_path)
                last_file = png_path
            else:
                last_file = blank_path

            concat_lines.append(f"file '{last_file.as_posix()}'")
            concat_lines.append(f"duration {dur:.4f}")

        # Repeat last file per FFmpeg concat demuxer specification
        concat_lines.append(f"file '{last_file.as_posix()}'")
        concat_file = tmp_dir / "subs.ffconcat"
        concat_file.write_text("\n".join(concat_lines), encoding="utf-8")

        # Build FFmpeg filter_complex for 9:16 + subtitle overlay
        if crop_mode == "blur_bg":
            video_chain = (
                f"[0:v]split=2[vbg][vfg];"
                f"[vbg]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
                f"crop={VIDEO_W}:{VIDEO_H},boxblur=24:4,eq=brightness=-0.12[bg];"
                f"[vfg]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[base];"
            )
        else:
            video_chain = (
                f"[0:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
                f"crop={VIDEO_W}:{VIDEO_H},setsar=1[base];"
            )

        filter_complex = (
            f"{video_chain}"
            f"[1:v]fps=30,format=rgba[sub];"
            f"[base][sub]overlay=x=0:y={overlay_y}:shortest=1[outv]"
        )

        # Try Apple Silicon hardware encoder first, fallback to libx264
        encoders = [
            ["-c:v", "h264_videotoolbox", "-b:v", "6M", "-pix_fmt", "yuv420p"],
            ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"],
        ]

        last_err = ""
        for enc_args in encoders:
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                f"{clip_start:.3f}",
                "-t",
                f"{clip_duration:.3f}",
                "-i",
                str(source_video),
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-filter_complex",
                filter_complex,
                "-map",
                "[outv]",
                "-map",
                "0:a?",
                *enc_args,
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(output_mp4),
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0 and output_mp4.exists() and output_mp4.stat().st_size > 1024:
                break
            last_err = res.stderr[-500:]
        else:
            raise RuntimeError(f"FFmpeg clip render failed: {last_err}")

        # Generate crisp preview thumbnail at ~25% into the clip
        thumb_t = min(max(0.5, clip_duration * 0.25), max(0.1, clip_duration - 0.2))
        thumb_cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{thumb_t:.2f}",
            "-i",
            str(output_mp4),
            "-vframes",
            "1",
            "-q:v",
            "3",
            str(thumb_jpg),
        ]
        subprocess.run(thumb_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        return output_mp4
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
