import base64
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


@dataclass
class ViolenceDetection:
    label: str
    confidence: float
    box: Dict[str, float]


def encode_jpeg_b64(bgr: np.ndarray, quality: int = 75) -> str:
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        return ""
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def parse_yolo_detections(result: Any, names: Dict[int, str]) -> List[ViolenceDetection]:
    dets: List[ViolenceDetection] = []
    if result is None or getattr(result, "boxes", None) is None or len(result.boxes) == 0:
        return dets
    xyxy = result.boxes.xyxy.cpu().numpy()
    cls = result.boxes.cls.cpu().numpy()
    conf = result.boxes.conf.cpu().numpy()
    for (x1, y1, x2, y2), c, p in zip(xyxy, cls, conf):
        label = str(names.get(int(c), str(int(c))))
        dets.append(
            ViolenceDetection(
                label=label,
                confidence=float(p),
                box={"x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2)},
            )
        )
    return dets


def is_violence_present(detections: List[ViolenceDetection], positive_labels: Optional[set] = None, min_conf: float = 0.25) -> bool:
    pos = {str(x).strip().lower() for x in (positive_labels or {"violence"})}
    for d in detections:
        if d.label.strip().lower() in pos and float(d.confidence) >= float(min_conf):
            return True
    return False


def best_positive_frame(
    detections_per_frame: List[Tuple[List[ViolenceDetection], np.ndarray]], positive_labels: Optional[set], min_conf: float
) -> Optional[np.ndarray]:
    best = None
    best_score = -1.0
    pos = {str(x).strip().lower() for x in (positive_labels or {"violence"})}
    for dets, frame in detections_per_frame:
        for d in dets:
            if d.label.strip().lower() in pos and float(d.confidence) >= float(min_conf):
                if float(d.confidence) > best_score:
                    best_score = float(d.confidence)
                    best = frame
    return best


def best_negative_frame(detections_per_frame: List[Tuple[List[ViolenceDetection], np.ndarray]]) -> Optional[np.ndarray]:
    if not detections_per_frame:
        return None
    return detections_per_frame[0][1]
