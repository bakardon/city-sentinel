import os
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np
from collections import deque

from .realtime_inference import load_module_from_path_cached


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _accident_src_dir() -> Path:
    return _project_root() / "accident_detection" / "src"


def _load_accident_modules():
    src_dir = _accident_src_dir()
    acc_config = load_module_from_path_cached("accident_testing_config_module", src_dir / "config.py")
    prev_config = sys.modules.get("config")
    try:
        sys.modules["config"] = acc_config
        acc_utils = load_module_from_path_cached("accident_testing_utils_module", src_dir / "utils.py")
        acc_db = load_module_from_path_cached("accident_testing_database_module", src_dir / "database.py")
    finally:
        if prev_config is not None:
            sys.modules["config"] = prev_config
        else:
            sys.modules.pop("config", None)

    return acc_config, acc_utils, acc_db


def get_accident_config():
    acc_config, _, _ = _load_accident_modules()
    return acc_config


@dataclass
class AccidentTestResult:
    ok: bool
    kind: str
    label: str
    confidence: float
    accident: bool
    snapshot_url: Optional[str]
    clip_url: Optional[str]
    error: Optional[str]


_model_lock = threading.Lock()
_model = None
_model_device = None
_model_weights = None

_veh_lock = threading.Lock()
_veh_model = None
_veh_device = None
_veh_weights = None


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


def _get_vehicle_model(weights_path: str, device: str):
    global _veh_model, _veh_device, _veh_weights
    with _veh_lock:
        if _veh_model is not None and _veh_device == device and _veh_weights == weights_path:
            return _veh_model
        from ultralytics import YOLO

        _veh_model = YOLO(weights_path)
        _veh_device = device
        _veh_weights = weights_path
        return _veh_model


def _max_iou(boxes_xyxy: np.ndarray) -> float:
    if boxes_xyxy is None or len(boxes_xyxy) < 2:
        return 0.0
    m = 0.0
    for i in range(len(boxes_xyxy)):
        x1a, y1a, x2a, y2a = boxes_xyxy[i]
        area_a = max(0.0, float(x2a - x1a)) * max(0.0, float(y2a - y1a))
        if area_a <= 0:
            continue
        for j in range(i + 1, len(boxes_xyxy)):
            x1b, y1b, x2b, y2b = boxes_xyxy[j]
            area_b = max(0.0, float(x2b - x1b)) * max(0.0, float(y2b - y1b))
            if area_b <= 0:
                continue
            ix1 = max(float(x1a), float(x1b))
            iy1 = max(float(y1a), float(y1b))
            ix2 = min(float(x2a), float(x2b))
            iy2 = min(float(y2a), float(y2b))
            iw = max(0.0, ix2 - ix1)
            ih = max(0.0, iy2 - iy1)
            inter = iw * ih
            if inter <= 0:
                continue
            iou = float(inter / float(area_a + area_b - inter + 1e-6))
            if iou > m:
                m = iou
    return float(m)


def _artifact_root(acc_config) -> Path:
    root = Path(acc_config.LIVE_PREDICTIONS_DIR) / "ui_tests"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _save_jpg(path: Path, bgr: np.ndarray) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(path), bgr))


def predict_image_file(image_path: Path) -> Tuple[AccidentTestResult, Optional[Path]]:
    try:
        acc_config, acc_utils, acc_db = _load_accident_modules()
        device = str(os.getenv("ACCIDENT_DEVICE", "cpu")).strip() or "cpu"
        weights_path = str(os.getenv("ACCIDENT_WEIGHTS_PATH") or acc_config.DEFAULT_WEIGHTS)
        model = _get_model(weights_path, device)

        im_bgr = cv2.imread(str(image_path))
        if im_bgr is None:
            return AccidentTestResult(False, "image", "", 0.0, False, None, None, "Invalid image"), None

        results = model.predict(im_bgr, imgsz=acc_config.IMGSZ, verbose=False, device=device)
        r = results[0]
        pred_class, conf, acc_prob = acc_utils.get_top1_and_prob(
            r,
            acc_utils.find_accident_index(getattr(model, "names", {}) or {}),
        )
        label = str(pred_class)
        accident = label.strip().lower() == "accident" and float(acc_prob) >= float(acc_config.CONF_THRESHOLD)

        plotted = r.plot()

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        run_dir = _artifact_root(acc_config) / f"image_{ts}"
        out_path = run_dir / "snapshot.jpg"
        _save_jpg(out_path, plotted)

        snapshot_url = None
        if accident and bool(getattr(acc_db, "SUPABASE_ENABLED", False)):
            dest = f"ui_test/image/{ts}_snapshot.jpg"
            try:
                snapshot_url = acc_db.upload_file(str(out_path), dest, bucket_name="accident-snapshots")
            except Exception:
                snapshot_url = None

        return AccidentTestResult(True, "image", label, float(conf), accident, snapshot_url, None, None), out_path
    except Exception as e:
        return AccidentTestResult(False, "image", "", 0.0, False, None, None, str(e)), None


def predict_video_file(video_path: Path, max_frames: int = 900) -> Tuple[AccidentTestResult, Optional[Path], Optional[Path]]:
    try:
        acc_config, acc_utils, acc_db = _load_accident_modules()
        device = str(os.getenv("ACCIDENT_DEVICE", "cpu")).strip() or "cpu"
        weights_path = str(os.getenv("ACCIDENT_WEIGHTS_PATH") or acc_config.DEFAULT_WEIGHTS)
        model = _get_model(weights_path, device)
        veh_device = "cpu"
        veh_weights = str(os.getenv("ACCIDENT_TEST_VEHICLE_WEIGHTS") or "yolov8m.pt")
        veh_model = _get_vehicle_model(veh_weights, veh_device)

        accident_idx = acc_utils.find_accident_index(getattr(model, "names", {}) or {})
        veh_iou_thresh = float(os.getenv("ACCIDENT_TEST_VIDEO_MIN_VEH_IOU", "0.25"))
        veh_min_conf = float(os.getenv("ACCIDENT_TEST_VEHICLE_MIN_CONF", "0.25"))
        veh_classes = {1, 2, 3, 5, 6, 7}

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return AccidentTestResult(False, "video", "", 0.0, False, None, None, "Could not open video"), None, None

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        run_dir = _artifact_root(acc_config) / f"video_{ts}"
        run_dir.mkdir(parents=True, exist_ok=True)
        snap_path = run_dir / "snapshot.jpg"
        clip_path = run_dir / "input.mp4"

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if fps <= 0:
            fps = 30.0
        step = max(1, int(round(fps)))

        accident_votes = 0
        normal_votes = 0
        sampled = 0

        best_acc_prob = -1.0
        best_acc_frame = None
        best_norm_prob = 2.0
        best_norm_frame = None

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            if int(max_frames) > 0 and frame_idx >= int(max_frames):
                break

            if frame_idx % step == 0:
                results = model.predict(frame, imgsz=acc_config.IMGSZ, verbose=False, device=device)
                pred_class, _, acc_prob = acc_utils.get_top1_and_prob(results[0], accident_idx)
                label = str(pred_class).strip().lower()
                is_acc = label == "accident" and float(acc_prob) >= float(acc_config.CONF_THRESHOLD)
                sampled += 1
                if is_acc:
                    det = veh_model.predict(frame, verbose=False, device=veh_device)[0]
                    v_boxes = []
                    if det.boxes is not None and len(det.boxes) > 0:
                        xyxy = det.boxes.xyxy.cpu().numpy()
                        cls = det.boxes.cls.cpu().numpy()
                        conf = det.boxes.conf.cpu().numpy()
                        for b, c, p in zip(xyxy, cls, conf):
                            if int(c) in veh_classes and float(p) >= veh_min_conf:
                                v_boxes.append(b)
                    iou = _max_iou(np.array(v_boxes)) if len(v_boxes) >= 2 else 0.0
                    if float(iou) >= float(veh_iou_thresh):
                        accident_votes += 1
                        if float(acc_prob) > best_acc_prob:
                            best_acc_prob = float(acc_prob)
                            best_acc_frame = frame.copy()
                    else:
                        normal_votes += 1
                        if float(acc_prob) < best_norm_prob:
                            best_norm_prob = float(acc_prob)
                            best_norm_frame = frame.copy()
                else:
                    normal_votes += 1
                    if float(acc_prob) < best_norm_prob:
                        best_norm_prob = float(acc_prob)
                        best_norm_frame = frame.copy()

            frame_idx += 1

        cap.release()

        if sampled <= 0:
            return AccidentTestResult(False, "video", "", 0.0, False, None, None, "No frames sampled"), None, None

        accident = bool(accident_votes > normal_votes)
        conf = float((accident_votes if accident else normal_votes) / float(sampled))

        chosen = best_acc_frame if accident else best_norm_frame
        if chosen is None:
            return AccidentTestResult(False, "video", "", 0.0, False, None, None, "No representative frame"), None, None

        _save_jpg(snap_path, chosen)

        snapshot_url = None
        clip_url = None
        local_clip = None

        if accident:
            try:
                clip_path.write_bytes(video_path.read_bytes())
                local_clip = clip_path
            except Exception:
                local_clip = None

            if bool(getattr(acc_db, "SUPABASE_ENABLED", False)):
                try:
                    snapshot_url = acc_db.upload_file(
                        str(snap_path),
                        f"ui_test/video/{ts}_snapshot.jpg",
                        bucket_name="accident-snapshots",
                    )
                except Exception:
                    snapshot_url = None
                if local_clip is not None:
                    try:
                        clip_url = acc_db.upload_file(
                            str(local_clip),
                            f"ui_test/video/{ts}_video.mp4",
                            bucket_name="accident-clips",
                        )
                    except Exception:
                        clip_url = None

        label = "accident" if accident else "normal"
        return (
            AccidentTestResult(True, "video", label, float(conf), accident, snapshot_url, clip_url, None),
            snap_path,
            local_clip,
        )
    except Exception as e:
        return AccidentTestResult(False, "video", "", 0.0, False, None, None, str(e)), None, None


def safe_artifact_path(rel: str) -> Optional[Path]:
    acc_config = get_accident_config()
    root = _artifact_root(acc_config).resolve()
    p = (root / rel).resolve()
    if root not in p.parents and p != root:
        return None
    if not p.exists() or not p.is_file():
        return None
    return p
