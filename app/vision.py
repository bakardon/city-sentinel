from typing import List, Optional, Tuple

import cv2
import numpy as np
import os
try:
    import onnxruntime as ort
except Exception:
    ort = None
try:
    import torch
except Exception:
    torch = None
from insightface.app import FaceAnalysis
from ultralytics import YOLO


def _cuda_available() -> bool:
    try:
        return bool(torch is not None and hasattr(torch, "cuda") and torch.cuda.is_available())
    except Exception:
        return False


def _gpu_enabled_from_env(name: str, default: str = "auto") -> bool:
    value = str(os.getenv(name, default)).strip().lower()
    if value in {"0", "false", "no", "off", "cpu"}:
        return False
    if value in {"1", "true", "yes", "on", "cuda", "gpu"}:
        return True
    return _cuda_available()


class VisionService:
    def __init__(self, yolo_model_path: str = "yolov8m.pt", plate_model_path: str = "best.pt") -> None:
        force_gpu = os.getenv("FORCE_GPU", "").lower() in {"1", "true", "yes"}
        self.person_detector = YOLO(yolo_model_path)
        self.yolo_device = "cpu"
        use_cuda = _gpu_enabled_from_env("VISION_USE_CUDA", "auto") or force_gpu
        if use_cuda and _cuda_available():
            self.yolo_device = "0"
        elif force_gpu:
            raise RuntimeError("CUDA is required but not available for YOLO")
        providers = ["CPUExecutionProvider"]
        if ort is not None:
            available = ort.get_available_providers()
            if use_cuda and "CUDAExecutionProvider" in available:
                providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            elif force_gpu:
                raise RuntimeError("CUDAExecutionProvider is required but not available")
        elif force_gpu:
            raise RuntimeError("onnxruntime is missing or does not support CUDA")
        self.face_app = FaceAnalysis(name="buffalo_l", providers=providers)
        self.face_app.prepare(ctx_id=0 if providers and providers[0] == "CUDAExecutionProvider" else -1, det_size=(640, 640))
        self.plate_device = "cpu"
        plate_use_cuda = _gpu_enabled_from_env("PLATE_USE_CUDA", "auto") or force_gpu
        if plate_use_cuda and _cuda_available():
            self.plate_device = "0"
        elif force_gpu:
            raise RuntimeError("CUDA is required but not available for plate model")
        
        self.plate_detector = None
        if plate_model_path and os.path.exists(plate_model_path):
            self.plate_detector = YOLO(plate_model_path)
        else:
            print(f"Warning: Plate model not found at {plate_model_path}")

    def detect_person_boxes(self, image: np.ndarray) -> List[Tuple[float, float, float, float]]:
        results = self.person_detector(image, verbose=False, device=self.yolo_device)[0]
        if results.boxes is None or len(results.boxes) == 0:
            return []
        boxes = results.boxes.xyxy.cpu().numpy()
        classes = results.boxes.cls.cpu().numpy()
        return [
            (float(x1), float(y1), float(x2), float(y2))
            for (x1, y1, x2, y2), cls in zip(boxes, classes)
            if int(cls) == 0
        ]

    def detect_plate_boxes(self, image: np.ndarray) -> List[Tuple[float, float, float, float, float]]:
        if self.plate_detector is None:
            return []
        results = self.plate_detector(image, verbose=False, device=self.plate_device)[0]
        if results.boxes is None or len(results.boxes) == 0:
            return []
        boxes = results.boxes.xyxy.cpu().numpy()
        confs = results.boxes.conf.cpu().numpy()
        return [
            (float(x1), float(y1), float(x2), float(y2), float(conf))
            for (x1, y1, x2, y2), conf in zip(boxes, confs)
        ]

    def crop_head(
        self, image: np.ndarray, box: Tuple[float, float, float, float]
    ) -> Optional[Tuple[np.ndarray, Tuple[float, float, float, float]]]:
        h, w = image.shape[:2]
        x1, y1, x2, y2 = box
        box_w = max(1.0, x2 - x1)
        box_h = max(1.0, y2 - y1)
        head_h = box_h * 0.4
        head_w = box_w * 0.6
        head_size = max(head_h, head_w)
        cx = (x1 + x2) / 2.0
        hx1 = int(max(0, cx - head_size / 2.0))
        hx2 = int(min(w, cx + head_size / 2.0))
        hy1 = int(max(0, y1))
        hy2 = int(min(h, y1 + head_size))
        if hx2 <= hx1 or hy2 <= hy1:
            return None
        return image[hy1:hy2, hx1:hx2], (float(hx1), float(hy1), float(hx2), float(hy2))

    def face_embedding(self, face_crop: np.ndarray) -> Optional[np.ndarray]:
        faces = self.face_app.get(face_crop)
        if not faces:
            return None
        faces = sorted(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
        embedding = faces[0].embedding
        return embedding.astype(np.float32)

    def detect_face_embeddings(
        self, image: np.ndarray
    ) -> List[Tuple[np.ndarray, Tuple[float, float, float, float]]]:
        faces = self.face_app.get(image)
        if not faces:
            return []
        faces = sorted(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
        outputs: List[Tuple[np.ndarray, Tuple[float, float, float, float]]] = []
        for face in faces:
            embedding = face.embedding
            if embedding is None:
                continue
            x1, y1, x2, y2 = face.bbox.tolist()
            outputs.append((embedding.astype(np.float32), (float(x1), float(y1), float(x2), float(y2))))
        return outputs

    def detect_faces(self, image: np.ndarray) -> List[Tuple[float, float, float, float]]:
        faces = self.face_app.get(image)
        if not faces:
            return []
        faces = sorted(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
        return [(float(x1), float(y1), float(x2), float(y2)) for x1, y1, x2, y2 in (f.bbox.tolist() for f in faces)]

    def extract_faces(
        self, image: np.ndarray
    ) -> List[Tuple[np.ndarray, np.ndarray, Tuple[float, float, float, float]]]:
        outputs: List[Tuple[np.ndarray, np.ndarray, Tuple[float, float, float, float]]] = []
        for box in self.detect_person_boxes(image):
            head_result = self.crop_head(image, box)
            if head_result is None:
                continue
            head, head_box = head_result
            embedding = self.face_embedding(head)
            if embedding is None:
                continue
            outputs.append((head, embedding, head_box))
        return outputs
