import base64
import os
import sys
import threading
import time
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from .realtime_inference import compute_process_every, get_yolo_runtime, open_optimized_capture, predict_yolo, should_emit_preview


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


def _encode_jpeg_b64(bgr: np.ndarray, quality: int = 75) -> str:
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        return ""
    return base64.b64encode(buf.tobytes()).decode("utf-8")


@dataclass
class FireWorkerStatus:
    running: bool
    configured: bool
    rtsp_url: str
    camera_id: str
    camera_location: str
    last_frame_utc: Optional[str]
    last_alert_utc: Optional[str]
    last_error: Optional[str]
    alerts_seen: int


class FireDetectionService:
    def __init__(
        self, rtsp_url: str = "", camera_id: str = "", camera_location: str = "", autostart: bool = False
    ) -> None:
        self._log = logging.getLogger("fire_worker")
        self._log.setLevel(logging.INFO)
        self._rtsp_url = rtsp_url or ""
        self._camera_id = camera_id or ""
        self._camera_location = camera_location or os.getenv("FIRE_CAMERA_LOCATION", "") or ""
        self._autostart = bool(autostart)
        self._device = str(os.getenv("FIRE_DEVICE", "auto")).strip() or "auto"
        self._events_table = str(os.getenv("FIRE_EVENTS_TABLE", "fire_events")).strip() or "fire_events"
        self._snapshots_bucket = str(os.getenv("FIRE_SNAPSHOTS_BUCKET", "fire-snapshots")).strip() or "fire-snapshots"
        self._log_cooldown_s = float(os.getenv("FIRE_LOG_COOLDOWN_S", "8.0"))
        self._process_fps = float(os.getenv("FIRE_PROCESS_FPS", "8.0"))
        self._preview_fps = float(os.getenv("FIRE_PREVIEW_FPS", "4.0"))
        self._reload_interval_s = float(os.getenv("FIRE_MODEL_RELOAD_S", "10.0"))
        self._last_log_by_camera: Dict[str, float] = {}

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self._last_error: Optional[str] = None
        self._last_frame_utc: Optional[str] = None
        self._last_alert_utc: Optional[str] = None
        self._alerts_seen = 0

        self._latest_image_b64: Optional[str] = None
        self._latest_detections: List[Dict[str, Any]] = []
        self._latest_fire: bool = False

    def maybe_autostart(self) -> None:
        if self._autostart:
            self.start()

    def start(
        self,
        rtsp_url: Optional[str] = None,
        camera_id: Optional[str] = None,
        camera_location: Optional[str] = None,
    ) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            if rtsp_url is not None:
                self._rtsp_url = rtsp_url
            if camera_id is not None:
                self._camera_id = camera_id
            if camera_location is not None:
                self._camera_location = camera_location
            if not self._rtsp_url:
                self._last_error = "FIRE_RTSP_URL is not configured"
                return False
            if not self._camera_id:
                self._camera_id = "FIRE_CAM"
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            return True

    def stop(self, timeout_s: float = 8.0) -> bool:
        t = None
        with self._lock:
            t = self._thread
            self._stop_event.set()
        if not t:
            return True
        t.join(timeout=timeout_s)
        return not t.is_alive()

    def status(self) -> FireWorkerStatus:
        with self._lock:
            running = bool(self._thread and self._thread.is_alive())
            configured = bool(self._rtsp_url)
            return FireWorkerStatus(
                running=running,
                configured=configured,
                rtsp_url=self._rtsp_url,
                camera_id=self._camera_id,
                camera_location=self._camera_location,
                last_frame_utc=self._last_frame_utc,
                last_alert_utc=self._last_alert_utc,
                last_error=self._last_error,
                alerts_seen=int(self._alerts_seen),
            )

    def latest_frame(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "image_b64": self._latest_image_b64,
                "detections": list(self._latest_detections),
                "fire": bool(self._latest_fire),
                "frame_utc": self._last_frame_utc,
                "error": self._last_error,
            }

    def _set_status(self, **kwargs: Any) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if k == "last_error":
                    self._last_error = v
                elif k == "last_frame_utc":
                    self._last_frame_utc = v
                elif k == "last_alert_utc":
                    self._last_alert_utc = v
                elif k == "alerts_seen":
                    self._alerts_seen = int(v)
                elif k == "latest_image_b64":
                    self._latest_image_b64 = v
                elif k == "latest_detections":
                    self._latest_detections = list(v or [])
                elif k == "latest_fire":
                    self._latest_fire = bool(v)

    def _encode_jpeg_bytes(self, bgr: np.ndarray, quality: int = 85) -> Optional[bytes]:
        ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
        if not ok:
            return None
        return buf.tobytes()

    def _upload_snapshot(self, supabase_admin: Any, camera_id: str, ts: str, bgr: np.ndarray) -> Optional[str]:
        try:
            data = self._encode_jpeg_bytes(bgr, quality=85)
            if not data:
                return None
            safe_cam = "".join([c for c in camera_id if c.isalnum() or c in {"-", "_"}]) or "FIRE_CAM"
            obj_path = f"{safe_cam}/{ts.replace(':', '').replace('-', '')}.jpg"
            supabase_admin.storage.from_(self._snapshots_bucket).upload(
                obj_path,
                data,
                file_options={"content-type": "image/jpeg", "upsert": "true"},
            )
            return supabase_admin.storage.from_(self._snapshots_bucket).get_public_url(obj_path)
        except Exception:
            return None

    def _insert_fire_event(
        self,
        ts: str,
        detections: List[Dict[str, Any]],
        best_conf: Optional[float],
        snapshot_bgr: Optional[np.ndarray],
        alert_type: str = "FIRE",
        camera_id: Optional[str] = None,
        camera_location: Optional[str] = None,
    ) -> None:
        try:
            from .supabase_client import get_supabase_admin

            supabase_admin = get_supabase_admin()
            if supabase_admin is None:
                return

            cam_id = (camera_id or self._camera_id or "FIRE_CAM").strip() or "FIRE_CAM"
            cam_loc = camera_location if camera_location is not None else self._camera_location
            conf = float(best_conf) if best_conf is not None else None
            desc = (
                f"Fire/Smoke detected at {cam_loc or 'Unknown location'} "
                f"(camera_id={cam_id}, confidence={conf if conf is not None else 'n/a'})"
            )
            snapshot_url = self._upload_snapshot(supabase_admin, cam_id, ts, snapshot_bgr) if snapshot_bgr is not None else None
            payload: Dict[str, Any] = {
                "event_time": ts,
                "camera_id": cam_id,
                "camera_location": cam_loc or None,
                "alert_type": str(alert_type or "FIRE"),
                "alert_level": "HIGH",
                "confidence": conf,
                "description": desc,
                "snapshot_url": snapshot_url,
                "detections": detections,
            }
            supabase_admin.table(self._events_table).insert(payload).execute()
        except Exception:
            return

    def log_fire_event(
        self,
        detections: List[Dict[str, Any]],
        snapshot_bgr: Optional[np.ndarray],
        camera_id: Optional[str] = None,
        camera_location: Optional[str] = None,
        alert_type: str = "FIRE",
    ) -> bool:
        cam_id = (camera_id or self._camera_id or "FIRE_CAM").strip() or "FIRE_CAM"
        now = time.time()
        with self._lock:
            last = float(self._last_log_by_camera.get(cam_id, 0.0))
            if (now - last) < max(0.0, self._log_cooldown_s):
                return False
            self._last_log_by_camera[cam_id] = now

        pos = {"fire", "smoke"}
        best_pos = 0.0
        for d in detections or []:
            try:
                label = str((d or {}).get("label", "")).strip().lower()
                conf = float((d or {}).get("confidence", 0.0))
                if label in pos and conf > best_pos:
                    best_pos = conf
            except Exception:
                continue
        ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        self._insert_fire_event(
            ts,
            list(detections or []),
            best_pos,
            snapshot_bgr,
            alert_type=alert_type,
            camera_id=cam_id,
            camera_location=camera_location,
        )
        return True

    def _run_loop(self) -> None:
        fire_config, fire_utils = _load_fire_modules()

        weights_path = str(fire_config.resolve_weights_path())
        runtime = get_yolo_runtime("FIRE", weights_path, self._device)
        names = runtime.names
        conf_thr = float(fire_config.CONF_THRESHOLD)
        last_weights_check = 0.0

        cap = None
        backoff_s = 1.0
        frame_index = 0
        process_every = 1
        last_preview_emit = 0.0
        while not self._stop_event.is_set():
            now = time.time()
            if (now - last_weights_check) >= self._reload_interval_s:
                last_weights_check = now
                try:
                    new_weights = str(fire_config.resolve_weights_path())
                except Exception:
                    new_weights = weights_path
                if new_weights:
                    try:
                        new_runtime = get_yolo_runtime("FIRE", new_weights, self._device)
                        if new_runtime.model_path != runtime.model_path or new_runtime.backend != runtime.backend:
                            self._log.info("fire worker runtime backend=%s model=%s", new_runtime.backend, new_runtime.model_path)
                        runtime = new_runtime
                        names = runtime.names
                        weights_path = new_weights
                    except Exception as e:
                        self._set_status(last_error=str(e))

            if cap is None or not cap.isOpened():
                try:
                    cap = open_optimized_capture(self._rtsp_url)
                except Exception:
                    cap = None
                if cap is None or not cap.isOpened():
                    self._set_status(last_error="Failed to open RTSP stream")
                    time.sleep(backoff_s)
                    backoff_s = min(10.0, backoff_s * 1.5)
                    continue
                backoff_s = 1.0
                src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
                process_every = compute_process_every(src_fps, self._process_fps)
                frame_index = 0
                self._log.info("fire worker rtsp connected camera_id=%s", self._camera_id)

            ok, frame = cap.read()
            if not ok or frame is None:
                self._set_status(last_error="Failed to read RTSP frame")
                try:
                    cap.release()
                except Exception:
                    pass
                cap = None
                continue

            ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
            self._set_status(last_frame_utc=ts, last_error=None)

            if (frame_index % process_every) != 0:
                frame_index += 1
                continue

            try:
                res = predict_yolo(runtime, frame, fire_config.IMGSZ)[0]
                dets = fire_utils.parse_yolo_detections(res, names)
                fire = fire_utils.is_fire_present(dets, positive_labels=fire_config.POSITIVE_CLASSES, min_conf=conf_thr)
                with self._lock:
                    prev_fire = bool(self._latest_fire)
                plotted = None
                status_kwargs: Dict[str, Any] = {
                    "latest_detections": [d.__dict__ for d in dets],
                    "latest_fire": fire,
                }
                if should_emit_preview(last_preview_emit, self._preview_fps) or (fire and not prev_fire):
                    plotted = res.plot() if hasattr(res, "plot") else frame
                    status_kwargs["latest_image_b64"] = _encode_jpeg_b64(plotted)
                    last_preview_emit = time.time()
                self._set_status(**status_kwargs)
                if fire and not prev_fire:
                    self._alerts_seen += 1
                    self._last_alert_utc = ts
                    pos = {str(x).strip().lower() for x in (fire_config.POSITIVE_CLASSES or set())}
                    best_pos = 0.0
                    for d in dets:
                        if str(d.label).strip().lower() in pos and float(d.confidence) > best_pos:
                            best_pos = float(d.confidence)
                    if plotted is None:
                        plotted = res.plot() if hasattr(res, "plot") else frame
                    self._insert_fire_event(ts, [d.__dict__ for d in dets], best_pos, plotted)
            except Exception as e:
                self._set_status(last_error=str(e))
            frame_index += 1

        try:
            if cap:
                cap.release()
        except Exception:
            pass
