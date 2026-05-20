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





def _violence_src_dir() -> Path:

    return _project_root() / "violence_detection" / "src"





def _load_module_from_path(mod_name: str, file_path: Path):

    spec = importlib.util.spec_from_file_location(mod_name, str(file_path))

    if spec is None or spec.loader is None:

        raise RuntimeError(f"Failed to load module: {file_path}")

    module = importlib.util.module_from_spec(spec)

    sys.modules[mod_name] = module

    spec.loader.exec_module(module)

    return module





def _load_violence_modules():

    src_dir = _violence_src_dir()

    violence_config = _load_module_from_path("violence_testing_config", src_dir / "config.py")

    violence_utils = _load_module_from_path("violence_testing_utils", src_dir / "utils.py")

    return violence_config, violence_utils





def get_violence_config():

    violence_config, _ = _load_violence_modules()

    return violence_config





@dataclass

class ViolenceTestResult:

    ok: bool

    kind: str

    label: str

    confidence: float

    violence: bool

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





def _artifact_root(violence_config) -> Path:

    root = Path(violence_config.LIVE_PREDICTIONS_DIR) / "ui_tests"

    root.mkdir(parents=True, exist_ok=True)

    return root





def _save_jpg(path: Path, bgr: np.ndarray) -> bool:

    path.parent.mkdir(parents=True, exist_ok=True)

    return bool(cv2.imwrite(str(path), bgr))





def _best_positive_score(dets, positive_classes) -> float:

    best_pos = 0.0

    pos = {str(x).strip().lower() for x in positive_classes}

    for d in dets:

        if d.label.strip().lower() in pos and float(d.confidence) > best_pos:

            best_pos = float(d.confidence)

    return best_pos





def predict_image_file(image_path: Path) -> Tuple[ViolenceTestResult, Optional[Path]]:

    try:

        violence_config, violence_utils = _load_violence_modules()

        device = str(os.getenv("VIOLENCE_DEVICE", "cpu")).strip() or "cpu"

        weights_path = str(violence_config.resolve_weights_path())

        model = _get_model(weights_path, device)

        names = getattr(model, "names", {}) or {}



        im_bgr = cv2.imread(str(image_path))

        if im_bgr is None:

            return ViolenceTestResult(False, "image", "", 0.0, False, None, "Invalid image"), None



        res = model.predict(im_bgr, imgsz=violence_config.IMGSZ, verbose=False, device=device)[0]

        dets = violence_utils.parse_yolo_detections(res, names)

        best_pos = _best_positive_score(dets, violence_config.POSITIVE_CLASSES)

        # For single-image testing, any positive-class detection from YOLO
        # counts as violence. The high CONF_THRESHOLD (0.45) is designed for
        # the live worker's temporal smoothing and is too strict for one-shot.
        violence = best_pos > 0.0



        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        run_dir = _artifact_root(violence_config) / f"image_{ts}"

        out_path = run_dir / "snapshot.jpg"

        _save_jpg(out_path, res.plot() if hasattr(res, "plot") else im_bgr)



        ui_root = _artifact_root(violence_config)

        rel = str(out_path.relative_to(ui_root)).replace("\\", "/")
        label = "violence" if violence else "normal"

        conf = float(best_pos if violence else max(0.0, 1.0 - best_pos))

        # If no positive detection but there are any detections at all,
        # use the top detection's confidence for the "normal" label
        if not violence and dets:
            top_neg = max(d.confidence for d in dets)
            conf = float(top_neg)

        return ViolenceTestResult(True, "image", label, float(conf), bool(violence), f"/violence-test/artifacts/{rel}", None), out_path

    except Exception as e:

        return ViolenceTestResult(False, "image", "", 0.0, False, None, str(e)), None





def predict_video_file(video_path: Path, max_frames: int = 3000) -> Tuple[ViolenceTestResult, Optional[Path], Optional[Path]]:

    try:

        violence_config, violence_utils = _load_violence_modules()

        device = str(os.getenv("VIOLENCE_DEVICE", "cpu")).strip() or "cpu"

        weights_path = str(violence_config.resolve_weights_path())

        model = _get_model(weights_path, device)

        names = getattr(model, "names", {}) or {}



        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():

            return ViolenceTestResult(False, "video", "", 0.0, False, None, "Could not open video"), None, None



        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)

        if fps <= 0:

            fps = 30.0

        step = max(1, int(round(fps)))



        sampled = 0

        violence_votes = 0

        normal_votes = 0

        frames = []

        thr = float(violence_config.CONF_THRESHOLD)



        idx = 0

        while True:

            ok, frame = cap.read()

            if not ok or frame is None:

                break

            if int(max_frames) > 0 and idx >= int(max_frames):

                break

            if idx % step == 0:

                res = model.predict(frame, imgsz=violence_config.IMGSZ, verbose=False, device=device)[0]

                dets = violence_utils.parse_yolo_detections(res, names)

                frames.append((dets, frame.copy()))

                best_pos = _best_positive_score(dets, violence_config.POSITIVE_CLASSES)

                is_violence = best_pos > 0.0

                sampled += 1

                if is_violence:

                    violence_votes += 1

                else:

                    normal_votes += 1

            idx += 1



        cap.release()

        if sampled <= 0:

            return ViolenceTestResult(False, "video", "", 0.0, False, None, "No frames sampled"), None, None



        violence = bool(violence_votes > normal_votes)

        conf = float((violence_votes if violence else normal_votes) / float(sampled))



        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        ui_root = _artifact_root(violence_config)

        run_dir = ui_root / f"video_{ts}"

        run_dir.mkdir(parents=True, exist_ok=True)

        snap_path = run_dir / "snapshot.jpg"



        chosen = violence_utils.best_positive_frame(frames, violence_config.POSITIVE_CLASSES, float(violence_config.CONF_THRESHOLD)) if violence else violence_utils.best_negative_frame(frames)

        if chosen is None:

            return ViolenceTestResult(False, "video", "", 0.0, False, None, "No representative frame"), None, None

        _save_jpg(snap_path, chosen)



        clip_path = None

        if violence:

            out_vid = run_dir / "input.mp4"

            try:

                out_vid.write_bytes(video_path.read_bytes())

                clip_path = out_vid

            except Exception:

                clip_path = None



        rel = str(snap_path.relative_to(ui_root)).replace("\\", "/")
        label = "violence" if violence else "normal"

        return ViolenceTestResult(True, "video", label, float(conf), bool(violence), f"/violence-test/artifacts/{rel}", None), snap_path, clip_path

    except Exception as e:

        return ViolenceTestResult(False, "video", "", 0.0, False, None, str(e)), None, None





def safe_artifact_path(rel: str) -> Optional[Path]:

    violence_config = get_violence_config()

    root = _artifact_root(violence_config).resolve()

    p = (root / rel).resolve()

    if root not in p.parents and p != root:

        return None

    if not p.exists() or not p.is_file():

        return None

    return p

