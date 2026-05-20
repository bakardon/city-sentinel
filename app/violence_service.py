import base64

import importlib.util

import logging

import os

import sys

import threading

import time

from dataclasses import dataclass

from datetime import datetime

from pathlib import Path

from typing import Any, Dict, List, Optional, Tuple



import cv2

import numpy as np

from .realtime_inference import compute_process_every, get_yolo_runtime, open_optimized_capture, predict_yolo, should_emit_preview





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





def _load_violence_modules() -> Tuple[Any, Any]:

    src_dir = _violence_src_dir()

    violence_config = _load_module_from_path("violence_detection_config", src_dir / "config.py")

    violence_utils = _load_module_from_path("violence_detection_utils", src_dir / "utils.py")

    return violence_config, violence_utils





def _encode_jpeg_b64(bgr: np.ndarray, quality: int = 75) -> str:

    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])

    if not ok:

        return ""

    return base64.b64encode(buf.tobytes()).decode("utf-8")





@dataclass

class ViolenceWorkerStatus:

    running: bool

    configured: bool

    rtsp_url: str

    camera_id: str

    camera_location: str

    last_frame_utc: Optional[str]

    last_error: Optional[str]

    alerts_seen: int





class ViolenceDetectionService:

    def __init__(self, rtsp_url: str = "", camera_id: str = "", camera_location: str = "", autostart: bool = False) -> None:

        self._log = logging.getLogger("violence_worker")

        self._log.setLevel(logging.INFO)

        self._rtsp_url = rtsp_url or ""

        self._camera_id = camera_id or ""

        self._camera_location = camera_location or os.getenv("VIOLENCE_CAMERA_LOCATION", "") or ""

        self._autostart = bool(autostart)

        self._device = str(os.getenv("VIOLENCE_DEVICE", "auto")).strip() or "auto"

        self._events_table = str(os.getenv("VIOLENCE_EVENTS_TABLE", "violence_events")).strip() or "violence_events"
        self._snapshots_bucket = str(os.getenv("VIOLENCE_SNAPSHOTS_BUCKET", "violence-snapshots")).strip() or "violence-snapshots"
        self._live_conf_threshold = float(os.getenv("VIOLENCE_LIVE_CONF_THRESHOLD", "0.80"))
        self._live_consec_frames = max(1, int(os.getenv("VIOLENCE_LIVE_CONSEC_FRAMES", "4")))
        self._process_fps = float(os.getenv("VIOLENCE_PROCESS_FPS", "8.0"))
        self._preview_fps = float(os.getenv("VIOLENCE_PREVIEW_FPS", "4.0"))
        self._reload_interval_s = float(os.getenv("VIOLENCE_MODEL_RELOAD_S", "10.0"))
        self._log_cooldown_s = float(os.getenv("VIOLENCE_LOG_COOLDOWN_S", "8.0"))
        self._webcam_positive_streak_by_camera: Dict[str, int] = {}


        self._thread: Optional[threading.Thread] = None

        self._stop_event = threading.Event()

        self._lock = threading.Lock()



        self._last_error: Optional[str] = None

        self._last_frame_utc: Optional[str] = None

        self._alerts_seen = 0

        self._latest_image_b64: Optional[str] = None

        self._latest_detections: List[Dict[str, Any]] = []

        self._latest_violence: bool = False



    def maybe_autostart(self) -> None:

        if self._autostart:

            self.start()



    def start(self, rtsp_url: Optional[str] = None, camera_id: Optional[str] = None, camera_location: Optional[str] = None) -> bool:

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

                self._last_error = "VIOLENCE_RTSP_URL is not configured"

                return False

            if not self._camera_id:

                self._camera_id = "VIOLENCE_CAM"

            self._stop_event.clear()

            self._thread = threading.Thread(target=self._run_loop, daemon=True)

            self._thread.start()

            return True



    def stop(self, timeout_s: float = 8.0) -> bool:

        with self._lock:

            t = self._thread

            self._stop_event.set()

        if not t:

            return True

        t.join(timeout=timeout_s)

        return not t.is_alive()



    def status(self) -> ViolenceWorkerStatus:

        with self._lock:

            return ViolenceWorkerStatus(

                running=bool(self._thread and self._thread.is_alive()),

                configured=bool(self._rtsp_url),

                rtsp_url=self._rtsp_url,

                camera_id=self._camera_id,

                camera_location=self._camera_location,

                last_frame_utc=self._last_frame_utc,

                last_error=self._last_error,

                alerts_seen=int(self._alerts_seen),

            )



    def latest_frame(self) -> Dict[str, Any]:

        with self._lock:

            return {

                "image_b64": self._latest_image_b64,

                "detections": list(self._latest_detections),

                "violence": bool(self._latest_violence),

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

                elif k == "alerts_seen":

                    self._alerts_seen = int(v)

                elif k == "latest_image_b64":

                    self._latest_image_b64 = v

                elif k == "latest_detections":

                    self._latest_detections = list(v or [])

                elif k == "latest_violence":
                    self._latest_violence = bool(v)


    def _positive_labels(self) -> set:
        try:
            violence_config, _ = _load_violence_modules()
            return {str(x).strip().lower() for x in violence_config.POSITIVE_CLASSES}
        except Exception:
            return {"violence"}

    def _best_positive_confidence(self, detections: List[Any]) -> float:
        pos = self._positive_labels()
        best_pos = 0.0
        for d in detections or []:
            try:
                if isinstance(d, dict):
                    label = str(d.get("label", "")).strip().lower()
                    conf = float(d.get("confidence", 0.0))
                else:
                    label = str(getattr(d, "label", "")).strip().lower()
                    conf = float(getattr(d, "confidence", 0.0))
                if label in pos and conf > best_pos:
                    best_pos = conf
            except Exception:
                continue
        return best_pos

    def evaluate_live_webcam_detection(self, detections: List[Dict[str, Any]], camera_id: Optional[str] = None) -> Tuple[bool, float, int]:
        cam_id = (camera_id or self._camera_id or "VIOLENCE_WEBCAM").strip() or "VIOLENCE_WEBCAM"
        best_pos = self._best_positive_confidence(detections)
        with self._lock:
            if best_pos >= self._live_conf_threshold:
                streak = int(self._webcam_positive_streak_by_camera.get(cam_id, 0)) + 1
            else:
                streak = 0
            self._webcam_positive_streak_by_camera[cam_id] = streak
        return streak >= self._live_consec_frames, best_pos, streak


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
            safe_cam = "".join([c for c in camera_id if c.isalnum() or c in {"-", "_"}]) or "VIOLENCE_CAM"
            obj_path = f"{safe_cam}/{ts.replace(':', '').replace('-', '')}.jpg"
            supabase_admin.storage.from_(self._snapshots_bucket).upload(
                obj_path,
                data,
                file_options={"content-type": "image/jpeg", "upsert": "true"},
            )
            return supabase_admin.storage.from_(self._snapshots_bucket).get_public_url(obj_path)
        except Exception:
            return None

    def _insert_violence_event(
        self,
        ts: str,
        detections: List[Dict[str, Any]],
        best_conf: Optional[float],
        snapshot_bgr: Optional[np.ndarray],
        alert_type: str = "VIOLENCE",
        camera_id: Optional[str] = None,
        camera_location: Optional[str] = None,
    ) -> None:
        try:
            from .supabase_client import get_supabase_admin

            supabase_admin = get_supabase_admin()
            if supabase_admin is None:
                return

            cam_id = (camera_id or self._camera_id or "VIOLENCE_CAM").strip() or "VIOLENCE_CAM"
            cam_loc = camera_location if camera_location is not None else self._camera_location
            conf = float(best_conf) if best_conf is not None else None
            desc = (
                f"Violence detected at {cam_loc or 'Unknown location'} "
                f"(camera_id={cam_id}, confidence={conf if conf is not None else 'n/a'})"
            )
            snapshot_url = self._upload_snapshot(supabase_admin, cam_id, ts, snapshot_bgr) if snapshot_bgr is not None else None
            payload: Dict[str, Any] = {
                "event_time": ts,
                "camera_id": cam_id,
                "camera_location": cam_loc or None,
                "alert_type": str(alert_type or "VIOLENCE"),
                "alert_level": "HIGH",
                "confidence": conf,
                "description": desc,
                "snapshot_url": snapshot_url,
                "detections": detections,
            }
            supabase_admin.table(self._events_table).insert(payload).execute()
        except Exception:
            return

    def log_violence_event(
        self,
        detections: List[Dict[str, Any]],
        snapshot_bgr: Optional[np.ndarray],
        camera_id: Optional[str] = None,
        camera_location: Optional[str] = None,
        alert_type: str = "VIOLENCE",
    ) -> bool:
        cam_id = (camera_id or self._camera_id or "VIOLENCE_CAM").strip() or "VIOLENCE_CAM"
        now = time.time()
        with self._lock:
            last = float(self._last_log_by_camera.get(cam_id, 0.0))
            if (now - last) < max(0.0, self._log_cooldown_s):
                return False
            self._last_log_by_camera[cam_id] = now

        best_pos = self._best_positive_confidence(list(detections or []))

        ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        self._insert_violence_event(
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
        violence_config, violence_utils = _load_violence_modules()
        weights_path = str(violence_config.resolve_weights_path())
        runtime = get_yolo_runtime("VIOLENCE", weights_path, self._device)
        names = runtime.names
        live_conf_thr = max(float(violence_config.CONF_THRESHOLD), float(self._live_conf_threshold))
        positive_streak = 0
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
                    new_weights = str(violence_config.resolve_weights_path())
                except Exception:
                    new_weights = weights_path
                if new_weights:
                    try:
                        new_runtime = get_yolo_runtime("VIOLENCE", new_weights, self._device)
                        if new_runtime.model_path != runtime.model_path or new_runtime.backend != runtime.backend:
                            self._log.info("violence worker runtime backend=%s model=%s", new_runtime.backend, new_runtime.model_path)
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
                self._log.info("violence worker rtsp connected camera_id=%s", self._camera_id)
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
                res = predict_yolo(runtime, frame, violence_config.IMGSZ)[0]
                dets = violence_utils.parse_yolo_detections(res, names)
                best_pos = self._best_positive_confidence(dets)
                if best_pos >= live_conf_thr:
                    positive_streak += 1
                else:
                    positive_streak = 0
                violence = positive_streak >= self._live_consec_frames
                with self._lock:
                    prev_violence = bool(self._latest_violence)
                plotted = None
                status_kwargs: Dict[str, Any] = {
                    "latest_detections": [d.__dict__ for d in dets],
                    "latest_violence": violence,
                }
                if should_emit_preview(last_preview_emit, self._preview_fps) or (violence and not prev_violence):
                    plotted = res.plot() if hasattr(res, "plot") else frame
                    status_kwargs["latest_image_b64"] = _encode_jpeg_b64(plotted)
                    last_preview_emit = time.time()
                self._set_status(**status_kwargs)
                if violence and not prev_violence:
                    self._alerts_seen += 1
                    if plotted is None:
                        plotted = res.plot() if hasattr(res, "plot") else frame
                    self._insert_violence_event(
                        ts,
                        [d.__dict__ for d in dets],
                        best_pos,
                        plotted,
                    )
            except Exception as e:
                self._set_status(last_error=str(e))
            frame_index += 1
        try:
            if cap:
                cap.release()
        except Exception:
            pass

