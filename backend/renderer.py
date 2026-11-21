"""9:16 vertical video formatter, AI Face Tracking, Stream Split-Screen, Jump-Cuts, Hook Banner, Watermark, Music Ducking & TikTok Subtitles."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from backend.config import SUBTITLE_STYLES, resolve_font_path
from backend.face_track import detect_face_center_x
from backend.hardware import get_hardware_info

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

    if bg_pill_rgba and placements:
        pad_x, pad_y = 34, 22
        draw.rounded_rectangle(
            [min_x - pad_x, min_y - pad_y, max_x + pad_x, max_y + pad_y],
            radius=28,
            fill=bg_pill_rgba,
        )

    if active_pill_rgba:
        for p in placements:
            if p["is_active"]:
                bx0, by0, bx1, by1 = p["box"]
                draw.rounded_rectangle(
                    [bx0 - 18, by0 - 10, bx1 + 18, by1 + 12],
                    radius=18,
                    fill=active_pill_rgba,
                )

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


def _render_hook_banner(text: str, font_path: str) -> Image.Image:
    """Render a bold viral Hook Title Banner (1080x260) for the first 4 seconds."""
    img = Image.new("RGBA", (VIDEO_W, 260), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    clean = text.strip().upper()[:66]
    font = ImageFont.truetype(font_path, 46)
    max_w = VIDEO_W - 180

    # Word wrap into max 2 lines
    words = clean.split()
    lines: List[str] = []
    cur = ""
    for w in words:
        cand = f"{cur} {w}".strip()
        bb = draw.textbbox((0, 0), cand, font=font)
        if cur and (bb[2] - bb[0]) > max_w:
            lines.append(cur)
            cur = w
            if len(lines) >= 2:
                break
        else:
            cur = cand
    if cur and len(lines) < 2:
        lines.append(cur)

    line_h = 58
    total_h = len(lines) * line_h
    max_line_w = 0
    for ln in lines:
        bb = draw.textbbox((0, 0), ln, font=font)
        max_line_w = max(max_line_w, bb[2] - bb[0])

    pad_x, pad_y = 40, 26
    box_w = min(VIDEO_W - 90, max_line_w + pad_x * 2)
    box_h = total_h + pad_y * 2
    x0 = (VIDEO_W - box_w) // 2
    y0 = (260 - box_h) // 2

    # Soft shadow + crisp white pill card with vibrant accent border
    draw.rounded_rectangle([x0, y0 + 10, x0 + box_w, y0 + box_h + 10], radius=28, fill=(0, 0, 0, 150))
    draw.rounded_rectangle(
        [x0, y0, x0 + box_w, y0 + box_h],
        radius=28,
        fill=(255, 255, 255, 245),
        outline=(255, 230, 0, 255),
        width=6,
    )

    ty = y0 + pad_y
    for ln in lines:
        bb = draw.textbbox((0, 0), ln, font=font)
        lw = bb[2] - bb[0]
        tx = (VIDEO_W - lw) // 2 - bb[0]
        draw.text((tx, ty - bb[1]), ln, font=font, fill=(12, 14, 24, 255))
        ty += line_h

    return img


def _render_watermark(text: str, font_path: str, opacity: float = 0.55) -> Image.Image:
    """Render a clean translucent @channel watermark overlay (1080x100)."""
    img = Image.new("RGBA", (VIDEO_W, 100), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    alpha = int(max(30, min(255, round(opacity * 255))))
    font = ImageFont.truetype(font_path, 34)
    label = text.strip()[:36]
    bb = draw.textbbox((0, 0), label, font=font, stroke_width=3)
    tw = bb[2] - bb[0]
    tx = VIDEO_W - tw - 46 - bb[0]
    ty = 26 - bb[1]
    draw.text(
        (tx, ty),
        label,
        font=font,
        fill=(255, 255, 255, alpha),
        stroke_width=3,
        stroke_fill=(0, 0, 0, int(alpha * 0.85)),
    )
    return img


def _apply_jump_cuts(
    source_video: Path,
    clip_start: float,
    clip_end: float,
    words: List[Dict[str, Any]],
    tmp_dir: Path,
    min_silence: float = 0.85,
    pad: float = 0.16,
) -> Tuple[Path, float, float, List[Dict[str, Any]]]:
    """
    Remove dead silences > `min_silence` seconds inside [clip_start, clip_end]
    using FFmpeg trim/atrim/concat and remap word timestamps cleanly.
    """
    clip_dur = clip_end - clip_start
    rel_words = [
        {
            "word": w["word"],
            "start": max(0.0, w["start"] - clip_start),
            "end": min(clip_dur, w["end"] - clip_start),
        }
        for w in words
        if w["end"] > clip_start and w["start"] < clip_end
    ]
    if len(rel_words) < 2:
        return source_video, clip_start, clip_end, words

    # Merge active speech intervals with breath padding
    intervals: List[List[float]] = []
    for w in rel_words:
        s = max(0.0, w["start"] - pad)
        e = min(clip_dur, w["end"] + pad)
        if intervals and s - intervals[-1][1] < (min_silence - 2 * pad):
            intervals[-1][1] = max(intervals[-1][1], e)
        else:
            intervals.append([s, e])

    # Only run jump-cut pass if it actually cuts meaningful silence (>= 1.2s saved) and <= 20 cuts
    kept_dur = sum(e - s for s, e in intervals)
    if len(intervals) <= 1 or (clip_dur - kept_dur) < 1.2 or len(intervals) > 20:
        return source_video, clip_start, clip_end, words

    fc_parts: List[str] = []
    concat_inputs: List[str] = []
    for idx, (s, e) in enumerate(intervals):
        fc_parts.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{idx}];")
        fc_parts.append(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{idx}];")
        concat_inputs.append(f"[v{idx}][a{idx}]")

    fc = "".join(fc_parts) + "".join(concat_inputs) + f"concat=n={len(intervals)}:v=1:a=1[outv][outa]"
    jc_mp4 = tmp_dir / "jumpcut.mp4"

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{clip_start:.3f}",
        "-t",
        f"{clip_dur:.3f}",
        "-i",
        str(source_video),
        "-filter_complex",
        fc,
        "-map",
        "[outv]",
        "-map",
        "[outa]",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(jc_mp4),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0 or not jc_mp4.exists():
        return source_video, clip_start, clip_end, words

    # Remap word timestamps into the new jump-cutted timeline
    remapped_words: List[Dict[str, Any]] = []
    offsets: List[Tuple[float, float, float]] = []
    acc = 0.0
    for s, e in intervals:
        offsets.append((s, e, acc))
        acc += (e - s)

    for w in rel_words:
        mid = (w["start"] + w["end"]) * 0.5
        for s, e, base in offsets:
            if s - 0.05 <= mid <= e + 0.05:
                ns = max(0.0, base + (w["start"] - s))
                ne = max(ns + 0.06, base + (w["end"] - s))
                remapped_words.append({"word": w["word"], "start": round(ns, 3), "end": round(ne, 3)})
                break

    new_meta = probe_video(jc_mp4)
    return jc_mp4, 0.0, float(new_meta.get("duration") or acc), remapped_words


def _build_video_framing_chain(
    crop_mode: str,
    source_video: Path,
    clip_start: float,
    clip_end: float,
    webcam_corner: str = "bottom_left",
    webcam_size: float = 0.28,
) -> str:
    """Build FFmpeg filter chain producing [base] at 1080x1920."""
    if crop_mode == "blur_bg":
        return (
            f"[0:v]split=2[vbg][vfg];"
            f"[vbg]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_W}:{VIDEO_H},boxblur=24:4,eq=brightness=-0.12[bg];"
            f"[vfg]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[base];"
        )

    if crop_mode == "split_stream":
        # Top 37.5% (1080x720) = cropped streamer webcam, Bottom 62.5% (1080x1200) = gameplay
        w_frac = max(0.18, min(0.45, float(webcam_size or 0.28)))
        h_frac = min(0.55, w_frac * 1.15)
        x_expr = "0" if "left" in webcam_corner else f"iw*(1-{w_frac:.3f})"
        y_expr = "0" if "top" in webcam_corner else f"ih*(1-{h_frac:.3f})"
        return (
            f"[0:v]split=2[vcam][vgame];"
            f"[vcam]crop=iw*{w_frac:.3f}:ih*{h_frac:.3f}:{x_expr}:{y_expr},"
            f"scale={VIDEO_W}:720:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_W}:720,setsar=1[cam];"
            f"[vgame]scale={VIDEO_W}:1200:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_W}:1200,setsar=1[game];"
            f"[cam][game]vstack=inputs=2,setsar=1[base];"
        )

    if crop_mode == "face_track":
        cx = detect_face_center_x(source_video, clip_start, clip_end)
        if cx is not None:
            # Scale height to 1920, then crop 1080px wide centered on detected face X (clamped safely)
            x_expr = f"max(0,min(iw-{VIDEO_W},iw*{cx:.4f}-{VIDEO_W // 2}))"
            return (
                f"[0:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
                f"crop={VIDEO_W}:{VIDEO_H}:{x_expr}:(ih-{VIDEO_H})/2,setsar=1[base];"
            )

    # Default 'fill' center crop
    return (
        f"[0:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_W}:{VIDEO_H},setsar=1[base];"
    )


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
    webcam_corner: str = "bottom_left",
    webcam_size: float = 0.28,
    hook_text: Optional[str] = None,
    watermark_text: Optional[str] = None,
    watermark_opacity: float = 0.55,
    jump_cuts: bool = False,
    bg_music_path: Optional[Path] = None,
    bg_music_volume: float = 0.18,
    target_fps: int = 30,
    video_enhance: bool = False,
) -> Path:
    """
    Render a 1080x1920 9:16 TikTok MP4 clip with word-by-word subtitles,
    optional AI Face Tracking / Split-Screen, Hook Banner, Watermark, Jump-Cuts & Music Ducking.
    """
    style = SUBTITLE_STYLES.get(style_id, SUBTITLE_STYLES["hormozi"])
    font_path = resolve_font_path(font_id)
    size_map = {"small": 56, "medium": 68, "large": 80}
    base_px = size_map.get(font_size, 68)
    use_upper = style.get("uppercase", True) if uppercase is None else uppercase

    pos_y_map = {"center": 740, "lower_third": 1160, "bottom": 1340}
    overlay_y = pos_y_map.get(position, 1160)

    tmp_dir = Path(tempfile.mkdtemp(prefix="tikcut_sub_"))
    try:
        # Optional Step 0: Auto Jump-Cuts (remove dead pauses > 0.85s)
        work_video = source_video
        work_start = clip_start
        work_end = clip_end
        work_words = words
        if jump_cuts and words:
            work_video, work_start, work_end, work_words = _apply_jump_cuts(
                source_video, clip_start, clip_end, words, tmp_dir
            )

        clip_duration = max(0.5, work_end - work_start)
        timeline = _build_subtitle_timeline(work_words, work_start, work_end)

        blank_path = tmp_dir / "blank.png"
        Image.new("RGBA", (SUB_CANVAS_W, SUB_CANVAS_H), (0, 0, 0, 0)).save(blank_path)

        concat_lines: List[str] = ["ffconcat version 1.0"]
        last_file = blank_path
        for idx, item in enumerate(timeline):
            dur = max(0.033, item["end"] - item["start"])
            if item["words"]:
                png_path = tmp_dir / f"sub_{idx:04d}.png"
                frame_img = _render_subtitle_frame(
                    item["words"], item["active_idx"], style, font_path, base_px, use_upper
                )
                frame_img.save(png_path)
                last_file = png_path
            else:
                last_file = blank_path

            concat_lines.append(f"file '{last_file.as_posix()}'")
            concat_lines.append(f"duration {dur:.4f}")

        concat_lines.append(f"file '{last_file.as_posix()}'")
        concat_file = tmp_dir / "subs.ffconcat"
        concat_file.write_text("\n".join(concat_lines), encoding="utf-8")

        # Build FFmpeg inputs dynamically
        inputs: List[str] = [
            "-ss", f"{work_start:.3f}",
            "-t", f"{clip_duration:.3f}",
            "-i", str(work_video),
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
        ]
        next_idx = 2

        hook_idx: Optional[int] = None
        if hook_text and hook_text.strip():
            hook_png = tmp_dir / "hook.png"
            _render_hook_banner(hook_text.strip(), font_path).save(hook_png)
            inputs.extend(["-i", str(hook_png)])
            hook_idx = next_idx
            next_idx += 1

        wm_idx: Optional[int] = None
        if watermark_text and watermark_text.strip():
            wm_png = tmp_dir / "watermark.png"
            _render_watermark(watermark_text.strip(), font_path, watermark_opacity).save(wm_png)
            inputs.extend(["-i", str(wm_png)])
            wm_idx = next_idx
            next_idx += 1

        music_idx: Optional[int] = None
        if bg_music_path and Path(bg_music_path).exists():
            inputs.extend(["-stream_loop", "-1", "-i", str(bg_music_path)])
            music_idx = next_idx
            next_idx += 1

        # Build filter_complex
        out_fps = 60 if int(target_fps or 30) >= 60 else 30
        video_chain = _build_video_framing_chain(
            crop_mode=crop_mode,
            source_video=work_video,
            clip_start=work_start,
            clip_end=work_end,
            webcam_corner=webcam_corner,
            webcam_size=webcam_size,
        )
        enhance_step = (
            "[base]eq=contrast=1.06:saturation=1.14,unsharp=5:5:0.65:5:5:0.0[base_e];"
            if video_enhance
            else ""
        )
        base_label = "base_e" if video_enhance else "base"

        fc = (
            f"{video_chain}"
            f"{enhance_step}"
            f"[1:v]fps={out_fps},format=rgba[sub];"
            f"[{base_label}][sub]overlay=x=0:y={overlay_y}:shortest=1,fps={out_fps}[v_sub];"
        )
        cur_v = "v_sub"

        if hook_idx is not None:
            fc += f"[{cur_v}][{hook_idx}:v]overlay=x=0:y=150:enable='between(t,0,4.0)'[v_hook];"
            cur_v = "v_hook"

        if wm_idx is not None:
            fc += f"[{cur_v}][{wm_idx}:v]overlay=x=0:y=48[v_wm];"
            cur_v = "v_wm"

        # Audio chain (with optional auto-ducking background music)
        audio_map = "0:a?"
        if music_idx is not None:
            vol = max(0.05, min(0.5, float(bg_music_volume or 0.18)))
            fc += (
                f"[0:a]asplit=2[voice_main][voice_sc];"
                f"[{music_idx}:a]volume={vol:.2f},atrim=0:{clip_duration:.3f}[mus];"
                f"[mus][voice_sc]sidechaincompress=threshold=0.03:ratio=6:attack=35:release=350[mus_duck];"
                f"[voice_main][mus_duck]amix=inputs=2:duration=first:dropout_transition=2[outa];"
            )
            audio_map = "[outa]"

        fc = fc.rstrip(";")

        # Hardware-aware encoder priority: NVIDIA RTX NVENC -> Apple VideoToolbox -> libx264
        hw = get_hardware_info()
        bitrate = "10M" if out_fps >= 60 else "7M"
        maxrate = "14M" if out_fps >= 60 else "10M"
        encoders: List[List[str]] = []
        if hw.get("has_nvenc"):
            encoders.append([
                "-c:v", "h264_nvenc",
                "-preset", "p5",
                "-tune", "hq",
                "-rc", "vbr",
                "-cq", "19",
                "-b:v", bitrate,
                "-maxrate", maxrate,
                "-pix_fmt", "yuv420p",
            ])
        if hw.get("has_videotoolbox"):
            encoders.append(["-c:v", "h264_videotoolbox", "-b:v", bitrate, "-pix_fmt", "yuv420p"])
        encoders.append(["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"])

        last_err = ""
        for enc_args in encoders:
            cmd = [
                "ffmpeg",
                "-y",
                *inputs,
                "-filter_complex",
                fc,
                "-map",
                f"[{cur_v}]",
                "-map",
                audio_map,
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
