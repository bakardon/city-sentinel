import os
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _fire_src_dir() -> Path:
    return _project_root() / "fire_detection" / "src"


def _ensure_fire_src_on_path() -> None:
    src_dir = _fire_src_dir()
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))


def _load_fire_modules():
    _ensure_fire_src_on_path()
    import config as fire_config
    import utils as fire_utils

    return fire_config, fire_utils


def get_fire_config():
    fire_config, _ = _load_fire_modules()
    return fire_config


@dataclass
class FireTestResult:
    ok: bool
    kind: str
    label: str
    confidence: float
    fire: bool
    artifact_url: Optional[str]
    error: Optional[str]


_model_lock = threading.Lock()
_model = None
_model_device = None
_model_weights = None


def _get_model(weights_path: str, device: str):
    global _model, _model_device, _model_weights
    with _model_lock:
        if _model is not None and _model_device == device and _model_weights == weights_path:
            return _model
        from ultralytics import YOLO

        fire_config, _ = _load_fire_modules()
        _model = YOLO(weights_path)
        _model_device = device
        _model_weights = weights_path
        return _model


def _artifact_root(fire_config) -> Path:
    root = Path(fire_config.LIVE_PREDICTIONS_DIR) / "ui_tests"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _save_jpg(path: Path, bgr: np.ndarray) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(path), bgr))


def predict_image_file(image_path: Path) -> Tuple[FireTestResult, Optional[Path]]:
    try:
        fire_config, fire_utils = _load_fire_modules()
        device = str(os.getenv("FIRE_DEVICE", "cpu")).strip() or "cpu"
        weights_path = str(fire_config.resolve_weights_path())
        model = _get_model(weights_path, device)
        names = getattr(model, "names", {}) or {}

        im_bgr = cv2.imread(str(image_path))
        if im_bgr is None:
            return FireTestResult(False, "image", "", 0.0, False, None, "Invalid image"), None

        res = model.predict(im_bgr, imgsz=fire_config.IMGSZ, verbose=False, device=device)[0]
        dets = fire_utils.parse_yolo_detections(res, names)
        thr = float(fire_config.CONF_THRESHOLD)
        pos = {str(x).strip().lower() for x in (fire_config.POSITIVE_CLASSES or set())}
        best_pos = 0.0
        for d in dets:
            if d.label.strip().lower() in pos and float(d.confidence) > best_pos:
                best_pos = float(d.confidence)
        fire = best_pos >= thr

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        run_dir = _artifact_root(fire_config) / f"image_{ts}"
        out_path = run_dir / "snapshot.jpg"
        _save_jpg(out_path, res.plot() if hasattr(res, "plot") else im_bgr)

        ui_root = _artifact_root(fire_config)
        rel = str(out_path.relative_to(ui_root)).replace("\\", "/")
        label = "fire" if fire else "normal"
        conf = float(best_pos if fire else max(0.0, 1.0 - best_pos))
        return FireTestResult(True, "image", label, float(conf), bool(fire), f"/fire-test/artifacts/{rel}", None), out_path
    except Exception as e:
        return FireTestResult(False, "image", "", 0.0, False, None, str(e)), None


def predict_video_file(video_path: Path, max_frames: int = 3000) -> Tuple[FireTestResult, Optional[Path], Optional[Path]]:
    try:
        fire_config, fire_utils = _load_fire_modules()
        device = str(os.getenv("FIRE_DEVICE", "cpu")).strip() or "cpu"
        weights_path = str(fire_config.resolve_weights_path())
        model = _get_model(weights_path, device)
        names = getattr(model, "names", {}) or {}

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return FireTestResult(False, "video", "", 0.0, False, None, "Could not open video"), None, None

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if fps <= 0:
            fps = 30.0
        step = max(1, int(round(fps)))

        sampled = 0
        fire_votes = 0
        normal_votes = 0
        frames = []
        thr = float(fire_config.CONF_THRESHOLD)

        idx = 0
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            if int(max_frames) > 0 and idx >= int(max_frames):
                break
            if idx % step == 0:
                res = model.predict(frame, imgsz=fire_config.IMGSZ, verbose=False, device=device)[0]
                dets = fire_utils.parse_yolo_detections(res, names)
                frames.append((dets, frame.copy()))
                pos = {str(x).strip().lower() for x in (fire_config.POSITIVE_CLASSES or set())}
                best_pos = 0.0
                for d in dets:
                    if d.label.strip().lower() in pos and float(d.confidence) > best_pos:
                        best_pos = float(d.confidence)
                is_fire = best_pos >= thr
                sampled += 1
                if is_fire:
                    fire_votes += 1
                else:
                    normal_votes += 1
            idx += 1

        cap.release()
        if sampled <= 0:
            return FireTestResult(False, "video", "", 0.0, False, None, "No frames sampled"), None, None

        fire = bool(fire_votes > normal_votes)
        conf = float((fire_votes if fire else normal_votes) / float(sampled))

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        ui_root = _artifact_root(fire_config)
        run_dir = ui_root / f"video_{ts}"
        run_dir.mkdir(parents=True, exist_ok=True)
        snap_path = run_dir / "snapshot.jpg"

        chosen = fire_utils.best_positive_frame(frames, fire_config.POSITIVE_CLASSES, float(fire_config.CONF_THRESHOLD)) if fire else fire_utils.best_negative_frame(frames)
        if chosen is None:
            return FireTestResult(False, "video", "", 0.0, False, None, "No representative frame"), None, None
        _save_jpg(snap_path, chosen)

        clip_path = None
        if fire:
            out_vid = run_dir / "input.mp4"
            try:
                out_vid.write_bytes(video_path.read_bytes())
                clip_path = out_vid
            except Exception:
                clip_path = None

        rel = str(snap_path.relative_to(ui_root)).replace("\\", "/")
        label = "fire" if fire else "normal"
        return FireTestResult(True, "video", label, float(conf), bool(fire), f"/fire-test/artifacts/{rel}", None), snap_path, clip_path
    except Exception as e:
        return FireTestResult(False, "video", "", 0.0, False, None, str(e)), None, None


def safe_artifact_path(rel: str) -> Optional[Path]:
    fire_config = get_fire_config()
    root = _artifact_root(fire_config).resolve()
    p = (root / rel).resolve()
    if root not in p.parents and p != root:
        return None
    if not p.exists() or not p.is_file():
        return None
    return p
