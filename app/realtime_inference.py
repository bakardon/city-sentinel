from __future__ import annotations

import importlib.util
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2

try:
    import torch
except Exception:  # pragma: no cover
    torch = None


_MODEL_CACHE_LOCK = threading.Lock()
_MODEL_CACHE: Dict[Tuple[str, str, str], Tuple[float, Any]] = {}

_MODULE_CACHE_LOCK = threading.Lock()
_MODULE_CACHE: Dict[Tuple[str, str], Any] = {}


@dataclass(frozen=True)
class YoloRuntime:
    prefix: str
    backend: str
    device: str
    model_path: str
    task: str
    names: Dict[int, str]
    model: Any
    half: bool


def _gpu_available() -> bool:
    try:
        return bool(torch is not None and torch.cuda.is_available())
    except Exception:
        return False


def resolve_device(device: Optional[str]) -> str:
    requested = str(device or "auto").strip().lower()
    if requested in {"", "auto"}:
        return "0" if _gpu_available() else "cpu"
    if requested == "cuda":
        return "0" if _gpu_available() else "cpu"
    if requested.startswith("cuda:"):
        return requested.split(":", 1)[1] if _gpu_available() else "cpu"
    if requested.isdigit():
        return requested if _gpu_available() else "cpu"
    return requested


def uses_cuda(device: str) -> bool:
    d = str(device or "").strip().lower()
    return d not in {"", "cpu"} and _gpu_available()


def load_module_from_path_cached(cache_key: str, file_path: Path) -> Any:
    key = (cache_key, str(file_path.resolve()))
    with _MODULE_CACHE_LOCK:
        cached = _MODULE_CACHE.get(key)
        if cached is not None:
            return cached
        spec = importlib.util.spec_from_file_location(cache_key, str(file_path))
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Failed to load module: {file_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODULE_CACHE[key] = module
        return module


def _artifact_candidates(prefix: str, weights_path: str) -> Tuple[Path, Path]:
    env_engine = str(os.getenv(f"{prefix}_ENGINE_PATH", "")).strip()
    env_onnx = str(os.getenv(f"{prefix}_ONNX_PATH", "")).strip()
    weights = Path(weights_path)
    default_engine = Path(env_engine) if env_engine else weights.with_suffix(".engine")
    default_onnx = Path(env_onnx) if env_onnx else weights.with_suffix(".onnx")
    return default_engine, default_onnx


def resolve_runtime_artifact(prefix: str, weights_path: str) -> Tuple[str, str]:
    backend_pref = str(os.getenv(f"{prefix}_INFERENCE_BACKEND", os.getenv("YOLO_INFERENCE_BACKEND", "auto"))).strip().lower()
    default_engine, default_onnx = _artifact_candidates(prefix, weights_path)

    if backend_pref in {"tensorrt", "engine"}:
        return ("tensorrt", str(default_engine))
    if backend_pref == "onnx":
        return ("onnx", str(default_onnx))

    if backend_pref == "auto":
        if default_engine.exists():
            return ("tensorrt", str(default_engine))
        if default_onnx.exists() and not _gpu_available():
            return ("onnx", str(default_onnx))
    return ("pytorch", str(weights_path))


def resolve_yolo_task(prefix: str) -> str:
    task = str(os.getenv(f"{prefix}_YOLO_TASK", os.getenv("YOLO_TASK", "auto"))).strip().lower()
    if task and task != "auto":
        return task
    return "classify" if str(prefix).strip().upper() == "ACCIDENT" else "detect"


def get_yolo_runtime(prefix: str, weights_path: str, device: Optional[str]) -> YoloRuntime:
    backend, model_path = resolve_runtime_artifact(prefix, weights_path)
    resolved_device = resolve_device(device)
    resolved_task = resolve_yolo_task(prefix)
    path = Path(model_path)
    mtime = path.stat().st_mtime if path.exists() else 0.0
    cache_key = (backend, f"{str(path.resolve()) if path.exists() else model_path}|{resolved_task}", resolved_device)

    with _MODEL_CACHE_LOCK:
        cached = _MODEL_CACHE.get(cache_key)
        if cached is not None and abs(float(cached[0]) - float(mtime)) < 1e-9:
            model = cached[1]
        else:
            from ultralytics import YOLO

            model = YOLO(model_path, task=resolved_task)
            _MODEL_CACHE[cache_key] = (mtime, model)

    names = getattr(model, "names", {}) or {}
    fp16_env = str(os.getenv(f"{prefix}_FP16", os.getenv("YOLO_FP16", "1"))).strip().lower()
    half = uses_cuda(resolved_device) and fp16_env not in {"0", "false", "no"}
    return YoloRuntime(
        prefix=prefix,
        backend=backend,
        device=resolved_device,
        model_path=model_path,
        task=resolved_task,
        names=names,
        model=model,
        half=half,
    )


def predict_yolo(runtime: YoloRuntime, image: Any, imgsz: int):
    kwargs = {"imgsz": int(imgsz), "verbose": False}
    if runtime.backend == "pytorch":
        kwargs["device"] = runtime.device
        if runtime.half:
            kwargs["half"] = True
    return runtime.model.predict(image, **kwargs)


def open_optimized_capture(url: str):
    cap = None
    try:
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    except Exception:
        cap = None
    if cap is None or not cap.isOpened():
        try:
            cap = cv2.VideoCapture(url)
        except Exception:
            cap = None
    if cap is not None and cap.isOpened():
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
    return cap


def compute_process_every(source_fps: float, target_fps: float) -> int:
    fps = float(source_fps or 0.0)
    target = float(target_fps or 0.0)
    if fps <= 0.0 or target <= 0.0 or target >= fps:
        return 1
    return max(1, int(round(fps / target)))


def should_emit_preview(last_emit_at: float, preview_fps: float) -> bool:
    fps = float(preview_fps or 0.0)
    if fps <= 0.0:
        return True
    return (time.time() - float(last_emit_at)) >= (1.0 / fps)
