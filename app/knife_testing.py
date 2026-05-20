import importlib.util
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


def _knife_src_dir() -> Path:
    return _project_root() / "knife_detection" / "src"


def _load_module_from_path(mod_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(mod_name, str(file_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module: {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def _load_knife_modules():
    src_dir = _knife_src_dir()
    knife_config = _load_module_from_path("knife_testing_config", src_dir / "config.py")
    knife_utils = _load_module_from_path("knife_testing_utils", src_dir / "utils.py")
    return knife_config, knife_utils


def get_knife_config():
    knife_config, _ = _load_knife_modules()
    return knife_config


@dataclass
class KnifeTestResult:
    ok: bool
    kind: str
    label: str
    confidence: float
    knife: bool
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

        _model = YOLO(weights_path)
        _model_device = device
        _model_weights = weights_path
        return _model


def _artifact_root(knife_config) -> Path:
    root = Path(knife_config.LIVE_PREDICTIONS_DIR) / "ui_tests"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _save_jpg(path: Path, bgr: np.ndarray) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(path), bgr))


def predict_image_file(image_path: Path) -> Tuple[KnifeTestResult, Optional[Path]]:
    try:
        knife_config, knife_utils = _load_knife_modules()
        device = str(os.getenv("KNIFE_DEVICE", "cpu")).strip() or "cpu"
        weights_path = str(knife_config.resolve_weights_path())
        model = _get_model(weights_path, device)
        names = getattr(model, "names", {}) or {}

        im_bgr = cv2.imread(str(image_path))
        if im_bgr is None:
            return KnifeTestResult(False, "image", "", 0.0, False, None, "Invalid image"), None

        res = model.predict(im_bgr, imgsz=knife_config.IMGSZ, verbose=False, device=device)[0]
        dets = knife_utils.parse_yolo_detections(res, names)
        thr = float(knife_config.CONF_THRESHOLD)
        best_pos = 0.0
        for d in dets:
            if d.label.strip().lower() in knife_config.POSITIVE_CLASSES and float(d.confidence) > best_pos:
                best_pos = float(d.confidence)
        knife = best_pos >= thr

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        run_dir = _artifact_root(knife_config) / f"image_{ts}"
        out_path = run_dir / "snapshot.jpg"
        _save_jpg(out_path, res.plot() if hasattr(res, "plot") else im_bgr)

        ui_root = _artifact_root(knife_config)
        rel = str(out_path.relative_to(ui_root)).replace("\\", "/")
        label = "knife" if knife else "normal"
        conf = float(best_pos if knife else max(0.0, 1.0 - best_pos))
        return KnifeTestResult(True, "image", label, float(conf), bool(knife), f"/knife-test/artifacts/{rel}", None), out_path
    except Exception as e:
        return KnifeTestResult(False, "image", "", 0.0, False, None, str(e)), None


def predict_video_file(video_path: Path, max_frames: int = 3000) -> Tuple[KnifeTestResult, Optional[Path], Optional[Path]]:
    try:
        knife_config, knife_utils = _load_knife_modules()
        device = str(os.getenv("KNIFE_DEVICE", "cpu")).strip() or "cpu"
        weights_path = str(knife_config.resolve_weights_path())
        model = _get_model(weights_path, device)
        names = getattr(model, "names", {}) or {}

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return KnifeTestResult(False, "video", "", 0.0, False, None, "Could not open video"), None, None

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if fps <= 0:
            fps = 30.0
        step = max(1, int(round(fps)))

        sampled = 0
        knife_votes = 0
        normal_votes = 0
        frames = []
        thr = float(knife_config.CONF_THRESHOLD)

        idx = 0
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            if int(max_frames) > 0 and idx >= int(max_frames):
                break
            if idx % step == 0:
                res = model.predict(frame, imgsz=knife_config.IMGSZ, verbose=False, device=device)[0]
                dets = knife_utils.parse_yolo_detections(res, names)
                frames.append((dets, frame.copy()))
                best_pos = 0.0
                for d in dets:
                    if d.label.strip().lower() in knife_config.POSITIVE_CLASSES and float(d.confidence) > best_pos:
                        best_pos = float(d.confidence)
                is_knife = best_pos >= thr
                sampled += 1
                if is_knife:
                    knife_votes += 1
                else:
                    normal_votes += 1
            idx += 1

        cap.release()
        if sampled <= 0:
            return KnifeTestResult(False, "video", "", 0.0, False, None, "No frames sampled"), None, None

        knife = bool(knife_votes > normal_votes)
        conf = float((knife_votes if knife else normal_votes) / float(sampled))

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        ui_root = _artifact_root(knife_config)
        run_dir = ui_root / f"video_{ts}"
        run_dir.mkdir(parents=True, exist_ok=True)
        snap_path = run_dir / "snapshot.jpg"

        chosen = knife_utils.best_positive_frame(frames, knife_config.POSITIVE_CLASSES, float(knife_config.CONF_THRESHOLD)) if knife else knife_utils.best_negative_frame(frames)
        if chosen is None:
            return KnifeTestResult(False, "video", "", 0.0, False, None, "No representative frame"), None, None
        _save_jpg(snap_path, chosen)

        clip_path = None
        if knife:
            out_vid = run_dir / "input.mp4"
            try:
                out_vid.write_bytes(video_path.read_bytes())
                clip_path = out_vid
            except Exception:
                clip_path = None

        rel = str(snap_path.relative_to(ui_root)).replace("\\", "/")
        label = "knife" if knife else "normal"
        return KnifeTestResult(True, "video", label, float(conf), bool(knife), f"/knife-test/artifacts/{rel}", None), snap_path, clip_path
    except Exception as e:
        return KnifeTestResult(False, "video", "", 0.0, False, None, str(e)), None, None


def safe_artifact_path(rel: str) -> Optional[Path]:
    knife_config = get_knife_config()
    root = _artifact_root(knife_config).resolve()
    p = (root / rel).resolve()
    if root not in p.parents and p != root:
        return None
    if not p.exists() or not p.is_file():
        return None
    return p
