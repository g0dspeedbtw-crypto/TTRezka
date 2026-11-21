"""Lightweight local AI Face Tracking for 9:16 vertical framing using OpenCV."""
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import cv2
except Exception:
    cv2 = None


def detect_face_center_x(
    video_path: Path,
    clip_start: float,
    clip_end: float,
    samples: int = 16,
) -> Optional[float]:
    """
    Sample frames across [clip_start, clip_end] and return the smoothed normalized
    horizontal center X (0.0 .. 1.0) of the speaker's face.
    Returns None if OpenCV is unavailable or no face is reliably detected.
    """
    if cv2 is None or not video_path.exists():
        return None

    try:
        cascade_cls = getattr(cv2, "CascadeClassifier", None) or getattr(
            getattr(cv2, "objdetect", None), "CascadeClassifier", None
        )
        if cascade_cls is None:
            return None

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cascade_cls(cascade_path)
        if face_cascade.empty():
            return None
    except Exception:
        return None

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None

    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920.0
        dur = max(0.5, clip_end - clip_start)
        step = dur / max(1, samples)

        xs = []
        for i in range(samples):
            t = clip_start + (i + 0.5) * step
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
            ok, frame = cap.read()
            if not ok or frame is None:
                continue

            # Downscale for super-fast detection (~5ms per frame)
            h, w = frame.shape[:2]
            scale = 480.0 / max(1, w)
            small = cv2.resize(frame, (int(w * scale), int(h * scale)))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.15,
                minNeighbors=4,
                minSize=(36, 36),
            )
            if len(faces) > 0:
                # Pick largest face (most prominent speaker)
                fx, fy, fw, fh = max(faces, key=lambda b: b[2] * b[3])
                cx_norm = (fx + fw * 0.5) / max(1.0, small.shape[1])
                xs.append(float(cx_norm))

        if len(xs) < 2:
            return None

        # Robust median removes stray false detections
        median_x = float(np.median(xs))
        return max(0.08, min(0.92, median_x))
    finally:
        cap.release()
