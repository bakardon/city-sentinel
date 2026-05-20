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





def _weapon_src_dir() -> Path:

    return _project_root() / "weapon_detection" / "src"





def _load_module_from_path(mod_name: str, file_path: Path):

    spec = importlib.util.spec_from_file_location(mod_name, str(file_path))

    if spec is None or spec.loader is None:

        raise RuntimeError(f"Failed to load module: {file_path}")

    module = importlib.util.module_from_spec(spec)

    sys.modules[mod_name] = module

    spec.loader.exec_module(module)

    return module





def _load_weapon_modules():

    src_dir = _weapon_src_dir()

    weapon_config = _load_module_from_path("weapon_testing_config", src_dir / "config.py")

    weapon_utils = _load_module_from_path("weapon_testing_utils", src_dir / "utils.py")

    return weapon_config, weapon_utils





def get_weapon_config():

    weapon_config, _ = _load_weapon_modules()

    return weapon_config





@dataclass

class WeaponTestResult:

    ok: bool

    kind: str

    label: str

    confidence: float

    weapon: bool

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





def _artifact_root(weapon_config) -> Path:

    root = Path(weapon_config.LIVE_PREDICTIONS_DIR) / "ui_tests"

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





def predict_image_file(image_path: Path) -> Tuple[WeaponTestResult, Optional[Path]]:

    try:

        weapon_config, weapon_utils = _load_weapon_modules()

        device = str(os.getenv("WEAPON_DEVICE", "cpu")).strip() or "cpu"

        weights_path = str(weapon_config.resolve_weights_path())

        model = _get_model(weights_path, device)

        names = getattr(model, "names", {}) or {}



        im_bgr = cv2.imread(str(image_path))

        if im_bgr is None:

            return WeaponTestResult(False, "image", "", 0.0, False, None, "Invalid image"), None



        res = model.predict(im_bgr, imgsz=weapon_config.IMGSZ, verbose=False, device=device)[0]

        dets = weapon_utils.parse_yolo_detections(res, names)

        best_pos = _best_positive_score(dets, weapon_config.POSITIVE_CLASSES)

        # For single-image testing, any positive-class detection from YOLO
        # counts as a weapon. The high CONF_THRESHOLD is for the live worker's
        # temporal smoothing and is too strict for one-shot testing.
        weapon = best_pos > 0.0

        # Use the actual detected class name (e.g. 'rifle', 'pistol') instead of generic 'weapon'
        best_label = "normal"
        if weapon:
            pos = {str(x).strip().lower() for x in weapon_config.POSITIVE_CLASSES}
            for d in dets:
                if d.label.strip().lower() in pos and float(d.confidence) >= best_pos - 1e-6:
                    best_label = d.label.strip()
                    break



        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        run_dir = _artifact_root(weapon_config) / f"image_{ts}"

        out_path = run_dir / "snapshot.jpg"

        _save_jpg(out_path, res.plot() if hasattr(res, "plot") else im_bgr)



        ui_root = _artifact_root(weapon_config)

        rel = str(out_path.relative_to(ui_root)).replace("\\", "/")
        label = best_label if weapon else "normal"

        conf = float(best_pos if weapon else max(0.0, 1.0 - best_pos))

        return WeaponTestResult(True, "image", label, float(conf), bool(weapon), f"/weapon-test/artifacts/{rel}", None), out_path

    except Exception as e:

        return WeaponTestResult(False, "image", "", 0.0, False, None, str(e)), None





def predict_video_file(video_path: Path, max_frames: int = 3000) -> Tuple[WeaponTestResult, Optional[Path], Optional[Path]]:

    try:

        weapon_config, weapon_utils = _load_weapon_modules()

        device = str(os.getenv("WEAPON_DEVICE", "cpu")).strip() or "cpu"

        weights_path = str(weapon_config.resolve_weights_path())

        model = _get_model(weights_path, device)

        names = getattr(model, "names", {}) or {}



        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():

            return WeaponTestResult(False, "video", "", 0.0, False, None, "Could not open video"), None, None



        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)

        if fps <= 0:

            fps = 30.0

        step = max(1, int(round(fps)))



        sampled = 0

        weapon_votes = 0

        normal_votes = 0

        frames = []

        thr = float(weapon_config.CONF_THRESHOLD)



        idx = 0

        while True:

            ok, frame = cap.read()

            if not ok or frame is None:

                break

            if int(max_frames) > 0 and idx >= int(max_frames):

                break

            if idx % step == 0:

                res = model.predict(frame, imgsz=weapon_config.IMGSZ, verbose=False, device=device)[0]

                dets = weapon_utils.parse_yolo_detections(res, names)

                frames.append((dets, frame.copy()))

                best_pos = _best_positive_score(dets, weapon_config.POSITIVE_CLASSES)

                is_weapon = best_pos > 0.0

                sampled += 1

                if is_weapon:

                    weapon_votes += 1

                else:

                    normal_votes += 1

            idx += 1



        cap.release()

        if sampled <= 0:

            return WeaponTestResult(False, "video", "", 0.0, False, None, "No frames sampled"), None, None



        weapon = bool(weapon_votes > normal_votes)

        conf = float((weapon_votes if weapon else normal_votes) / float(sampled))



        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        ui_root = _artifact_root(weapon_config)

        run_dir = ui_root / f"video_{ts}"

        run_dir.mkdir(parents=True, exist_ok=True)

        snap_path = run_dir / "snapshot.jpg"



        chosen = weapon_utils.best_positive_frame(frames, weapon_config.POSITIVE_CLASSES, float(weapon_config.CONF_THRESHOLD)) if weapon else weapon_utils.best_negative_frame(frames)

        if chosen is None:

            return WeaponTestResult(False, "video", "", 0.0, False, None, "No representative frame"), None, None

        _save_jpg(snap_path, chosen)



        clip_path = None

        if weapon:

            out_vid = run_dir / "input.mp4"

            try:

                out_vid.write_bytes(video_path.read_bytes())

                clip_path = out_vid

            except Exception:

                clip_path = None



        rel = str(snap_path.relative_to(ui_root)).replace("\\", "/")
        label = "weapon" if weapon else "normal"

        return WeaponTestResult(True, "video", label, float(conf), bool(weapon), f"/weapon-test/artifacts/{rel}", None), snap_path, clip_path

    except Exception as e:

        return WeaponTestResult(False, "video", "", 0.0, False, None, str(e)), None, None





def safe_artifact_path(rel: str) -> Optional[Path]:

    weapon_config = get_weapon_config()

    root = _artifact_root(weapon_config).resolve()

    p = (root / rel).resolve()

    if root not in p.parents and p != root:

        return None

    if not p.exists() or not p.is_file():

        return None

    return p

