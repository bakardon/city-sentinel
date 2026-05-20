import os
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from ultralytics import YOLO

_plate_reader = None
_plate_reader_lock = threading.Lock()

_plate_detector = None
_plate_detector_lock = threading.Lock()
_plate_device = "cpu"


def _clean_plate_text(text: Any) -> str:
    raw = str(text).upper().strip()
    return re.sub(r"[^A-Z0-9]", "", raw)


def _normalize_plate_digits(value: str) -> str:
    return value.replace("G", "0").replace("O", "0").replace("I", "1")


def _format_plate_tokens(tokens: List[str]) -> Optional[str]:
    if not tokens:
        return None
    joined = "".join(tokens)
    candidates = [joined]
    for token in tokens:
        if token not in candidates:
            candidates.append(token)
    for candidate in candidates:
        cleaned = _clean_plate_text(candidate)
        for match in re.finditer(r"([A-Z]{3})([A-Z0-9]{2})([A-Z0-9]{4})", cleaned):
            region = match.group(1)
            year = _normalize_plate_digits(match.group(2))
            number = _normalize_plate_digits(match.group(3))
            if year.isdigit() and number.isdigit():
                return f"{region}-{year}-{number}"
    return None


def _pick_ocr_text(results: List[Any]) -> Tuple[Optional[str], Optional[float]]:
    tokens: List[str] = []
    best_conf: Optional[float] = None
    for result in results:
        if not result or len(result) < 3:
            continue
        _, text, conf = result
        cleaned = _clean_plate_text(text)
        if len(cleaned) < 2:
            continue
        tokens.append(cleaned)
        score = float(conf)
        if best_conf is None or score > best_conf:
            best_conf = score
    formatted = _format_plate_tokens(tokens)
    if not formatted:
        return None, None
    return formatted, best_conf


def _box_iou(a: Dict[str, float], b: Dict[str, float]) -> float:
    ax1, ay1, ax2, ay2 = a["x1"], a["y1"], a["x2"], a["y2"]
    bx1, by1, bx2, by2 = b["x1"], b["y1"], b["x2"], b["y2"]
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    if denom <= 0.0:
        return 0.0
    return inter / denom


def get_plate_reader():
    global _plate_reader
    if _plate_reader is not None:
        return _plate_reader
    with _plate_reader_lock:
        if _plate_reader is not None:
            return _plate_reader
        try:
            import torch
            try:
                use_gpu = bool(getattr(torch, "cuda", None) and torch.cuda.is_available())
            except Exception:
                use_gpu = False
            import easyocr
            _plate_reader = easyocr.Reader(["en"], gpu=use_gpu)
        except Exception:
            _plate_reader = None
    return _plate_reader


def get_plate_detector():
    global _plate_detector, _plate_device
    if _plate_detector is not None:
        return _plate_detector
    with _plate_detector_lock:
        if _plate_detector is not None:
            return _plate_detector
        plate_model_path = os.getenv(
            "PLATE_MODEL_PATH",
            r"D:\hanan_fyp\runs\pk_plate2\weights\best.pt",
        )
        if not plate_model_path or not os.path.exists(plate_model_path):
            _plate_detector = None
            return _plate_detector
        force_gpu = os.getenv("FORCE_GPU", "").lower() in {"1", "true", "yes"}
        _plate_device = "cpu"
        try:
            import torch
            if getattr(torch, "cuda", None) is not None and torch.cuda.is_available():
                _plate_device = "cuda"
            elif force_gpu:
                raise RuntimeError("CUDA is required but not available for plate model")
        except Exception:
            if force_gpu:
                raise
            _plate_device = "cpu"
        _plate_detector = YOLO(plate_model_path)
    return _plate_detector


def detect_plates(image: np.ndarray) -> List[Dict[str, Any]]:
    reader = get_plate_reader()
    detector = get_plate_detector()
    if reader is None or detector is None:
        return []
    results = detector(image, verbose=False, device=_plate_device)[0]
    if results.boxes is None or len(results.boxes) == 0:
        return []
    boxes = results.boxes.xyxy.cpu().numpy()
    confs = results.boxes.conf.cpu().numpy()
    h, w = image.shape[:2]
    plates: List[Dict[str, Any]] = []
    for (x1, y1, x2, y2), det_conf in zip(boxes, confs):
        ix1 = max(0, min(w - 1, int(x1)))
        iy1 = max(0, min(h - 1, int(y1)))
        ix2 = max(1, min(w, int(x2)))
        iy2 = max(1, min(h, int(y2)))
        if ix2 <= ix1 or iy2 <= iy1:
            continue
        crop = image[iy1:iy2, ix1:ix2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
        text, ocr_conf = _pick_ocr_text(reader.readtext(gray))
        if not text or ocr_conf is None:
            continue
        candidate = {
            "text": text,
            "confidence": float(ocr_conf),
            "det_confidence": float(det_conf),
            "box": {"x1": float(ix1), "y1": float(iy1), "x2": float(ix2), "y2": float(iy2)},
        }
        merged = False
        for idx, existing_plate in enumerate(plates):
            if existing_plate.get("text") != text:
                continue
            if _box_iou(existing_plate["box"], candidate["box"]) < 0.4:
                continue
            if float(candidate["confidence"]) > float(existing_plate.get("confidence", 0.0)):
                plates[idx] = candidate
            merged = True
            break
        if not merged:
            plates.append(candidate)
    return plates

