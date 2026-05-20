import os
import sys
import re
import threading
import time
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

from .realtime_inference import get_yolo_runtime, load_module_from_path_cached, predict_yolo


def _redact_rtsp_url(url: str) -> str:
    if not url:
        return ""
    return re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:***@", url)


@dataclass
class AccidentWorkerStatus:
    running: bool
    configured: bool
    camera_id: str
    rtsp_url: str
    last_error: Optional[str]
    last_frame_utc: Optional[str]
    last_alert_utc: Optional[str]
    last_supabase_snapshot_url: Optional[str]
    last_supabase_clip_url: Optional[str]
    alerts_seen: int


class AccidentDetectionService:
    def __init__(
        self,
        rtsp_url: str = "",
        camera_id: str = "",
        autostart: bool = False,
    ) -> None:
        self._log = logging.getLogger("accident_worker")
        self._log.setLevel(logging.INFO)
        self._rtsp_url = rtsp_url or ""
        self._camera_id = camera_id or ""
        self._autostart = bool(autostart)
        self._device = str(os.getenv("ACCIDENT_DEVICE", "auto")).strip() or "auto"

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self._last_error: Optional[str] = None
        self._last_frame_utc: Optional[str] = None
        self._last_alert_utc: Optional[str] = None
        self._last_supabase_snapshot_url: Optional[str] = None
        self._last_supabase_clip_url: Optional[str] = None
        self._alerts_seen = 0

    def configure(self, rtsp_url: Optional[str] = None, camera_id: Optional[str] = None) -> None:
        with self._lock:
            if rtsp_url is not None:
                self._rtsp_url = str(rtsp_url)
            if camera_id is not None:
                self._camera_id = str(camera_id)

    def is_running(self) -> bool:
        t = self._thread
        return bool(t and t.is_alive())

    def start(self, rtsp_url: Optional[str] = None, camera_id: Optional[str] = None) -> bool:
        if rtsp_url is not None or camera_id is not None:
            self.configure(rtsp_url=rtsp_url, camera_id=camera_id)

        with self._lock:
            if self.is_running():
                return False
            if not self._rtsp_url:
                self._last_error = "ACCIDENT_RTSP_URL is not configured"
                return False
            if not self._camera_id:
                self._camera_id = "ACCIDENT_CAM"

            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            self._log.info("worker started camera_id=%s rtsp_url=%s", self._camera_id, _redact_rtsp_url(self._rtsp_url))
            return True

    def stop(self, timeout_s: float = 10.0) -> bool:
        t = self._thread
        if not t:
            return False
        self._log.info("worker stopping")
        self._stop_event.set()
        t.join(timeout=max(0.1, float(timeout_s)))
        self._log.info("worker stopped stopped=%s", str(not t.is_alive()).lower())
        return not t.is_alive()

    def maybe_autostart(self) -> bool:
        if not self._autostart:
            return False
        if not self._rtsp_url:
            return False
        return self.start()

    def status(self) -> AccidentWorkerStatus:
        with self._lock:
            return AccidentWorkerStatus(
                running=self.is_running(),
                configured=bool(self._rtsp_url),
                camera_id=self._camera_id,
                rtsp_url=_redact_rtsp_url(self._rtsp_url),
                last_error=self._last_error,
                last_frame_utc=self._last_frame_utc,
                last_alert_utc=self._last_alert_utc,
                last_supabase_snapshot_url=self._last_supabase_snapshot_url,
                last_supabase_clip_url=self._last_supabase_clip_url,
                alerts_seen=int(self._alerts_seen),
            )

    def _set_status(
        self,
        *,
        last_error: Optional[str] = None,
        last_frame_utc: Optional[str] = None,
        last_alert_utc: Optional[str] = None,
        last_supabase_snapshot_url: Optional[str] = None,
        last_supabase_clip_url: Optional[str] = None,
        bump_alerts: bool = False,
    ) -> None:
        with self._lock:
            if last_error is not None:
                self._last_error = last_error
            if last_frame_utc is not None:
                self._last_frame_utc = last_frame_utc
            if last_alert_utc is not None:
                self._last_alert_utc = last_alert_utc
            if last_supabase_snapshot_url is not None:
                self._last_supabase_snapshot_url = last_supabase_snapshot_url
            if last_supabase_clip_url is not None:
                self._last_supabase_clip_url = last_supabase_clip_url
            if bump_alerts:
                self._alerts_seen += 1

    def _load_accident_modules(self) -> Tuple[Any, Any, Any]:
        root = Path(__file__).resolve().parents[1]
        src_dir = root / "accident_detection" / "src"
        acc_config = load_module_from_path_cached("accident_config_module", src_dir / "config.py")
        prev_config = sys.modules.get("config")
        try:
            sys.modules["config"] = acc_config
            acc_utils = load_module_from_path_cached("accident_utils_module", src_dir / "utils.py")
            acc_db = load_module_from_path_cached("accident_database_module", src_dir / "database.py")
        finally:
            if prev_config is not None:
                sys.modules["config"] = prev_config
            else:
                sys.modules.pop("config", None)

        return acc_config, acc_utils, acc_db

    def _sleep_interruptible(self, seconds: float) -> None:
        end = time.time() + max(0.0, float(seconds))
        while not self._stop_event.is_set() and time.time() < end:
            time.sleep(0.1)

    def _run_loop(self) -> None:
        try:
            acc_config, acc_utils, acc_db = self._load_accident_modules()
        except Exception as e:
            self._set_status(last_error=f"Failed to import accident modules: {e}")
            self._log.exception("worker init failed import_error=%s", str(e))
            return

        rtsp_url = ""
        camera_id = ""
        with self._lock:
            rtsp_url = self._rtsp_url
            camera_id = self._camera_id

        outputs_base = Path(acc_config.LIVE_PREDICTIONS_DIR)
        outputs_base.mkdir(parents=True, exist_ok=True)

        session_dir = outputs_base / f"backend_worker_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        snapshots_dir = session_dir / "snapshots"
        clips_dir = session_dir / "clips"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        clips_dir.mkdir(parents=True, exist_ok=True)

        weights_path = str(os.getenv("ACCIDENT_WEIGHTS_PATH") or acc_config.DEFAULT_WEIGHTS)
        try:
            runtime = get_yolo_runtime("ACCIDENT", weights_path, self._device)
        except Exception as e:
            self._set_status(last_error=f"Failed to load YOLO weights: {e}")
            self._log.exception("worker init failed weights_path=%s error=%s", str(weights_path), str(e))
            return
        accident_idx = acc_utils.find_accident_index(runtime.names)
        self._log.info(
            "worker initialized camera_id=%s rtsp_url=%s supabase_enabled=%s weights=%s backend=%s device=%s",
            camera_id,
            _redact_rtsp_url(rtsp_url),
            str(bool(getattr(acc_db, "SUPABASE_ENABLED", False))).lower(),
            str(runtime.model_path),
            str(runtime.backend),
            str(self._device),
        )

        state = acc_utils.TemporalState(
            window_probs=deque(maxlen=acc_config.VOTE_WINDOW),
            window_votes=deque(maxlen=acc_config.VOTE_WINDOW),
            vote_threshold=acc_config.VOTE_THRESHOLD,
            clear_threshold=acc_config.CLEAR_THRESHOLD,
            cooldown_s=acc_config.COOLDOWN_S,
        )

        cap = None
        clip_writer = None
        clip_post_remaining = 0
        clip_path: Optional[Path] = None
        active_accident_id: Optional[int] = None
        active_ts_id: Optional[str] = None
        active_ts_iso: Optional[str] = None

        last_open_attempt = 0.0
        open_failures = 0
        last_read_error_log_at = 0.0
        last_pred_log_at = 0.0
        frame_index = 0
        frame_buffer: Deque[Any] = deque(maxlen=1)
        process_every = 1
        src_fps = 30.0
        pre_frames = 1
        post_frames = 1

        while not self._stop_event.is_set():
            if cap is None or not cap.isOpened():
                now = time.time()
                if now - last_open_attempt < 1.0:
                    self._sleep_interruptible(0.2)
                    continue
                last_open_attempt = now
                try:
                    cap = acc_utils.open_capture(rtsp_url)
                    if not cap or not cap.isOpened():
                        self._set_status(last_error="Failed to open RTSP stream")
                        open_failures += 1
                        backoff_s = min(30.0, 1.0 + (2.0 ** min(5, open_failures)))
                        self._log.warning(
                            "rtsp connect failed attempts=%s backoff_s=%.1f rtsp_url=%s",
                            str(open_failures),
                            float(backoff_s),
                            _redact_rtsp_url(rtsp_url),
                        )
                        self._sleep_interruptible(backoff_s)
                        continue
                    src_fps = float(cap.get(5) or 30.0)
                    process_every = max(1, int(round(src_fps / float(acc_config.PROCESS_FPS))))
                    pre_frames = max(1, int(round(float(acc_config.PRE_S) * src_fps)))
                    post_frames = max(1, int(round(float(acc_config.POST_S) * src_fps)))
                    frame_buffer = deque(maxlen=pre_frames)
                    open_failures = 0
                    self._set_status(last_error=None)
                    self._log.info("rtsp connected camera_id=%s fps=%.2f process_every=%s", camera_id, float(src_fps), str(process_every))
                except Exception as e:
                    self._set_status(last_error=str(e))
                    open_failures += 1
                    backoff_s = min(30.0, 1.0 + (2.0 ** min(5, open_failures)))
                    self._log.exception("rtsp connect exception attempts=%s error=%s", str(open_failures), str(e))
                    self._sleep_interruptible(backoff_s)
                    continue

            ret, frame = cap.read()
            if not ret or frame is None:
                self._set_status(last_error="Failed to read RTSP frame")
                if time.time() - last_read_error_log_at >= 2.0:
                    last_read_error_log_at = time.time()
                    self._log.warning("rtsp read failed, reconnecting")
                try:
                    cap.release()
                except Exception:
                    pass
                cap = None
                self._sleep_interruptible(0.5)
                continue

            now_utc = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
            self._set_status(last_frame_utc=now_utc)

            if clip_writer is not None and clip_post_remaining > 0:
                try:
                    clip_writer.write(frame)
                except Exception:
                    pass
                clip_post_remaining -= 1
                if clip_post_remaining <= 0:
                    try:
                        clip_writer.release()
                    except Exception:
                        pass
                    clip_writer = None
                    if clip_path:
                        self._log.info("clip saved path=%s", str(clip_path))
                    if (
                        bool(acc_db.SUPABASE_ENABLED)
                        and active_accident_id
                        and clip_path
                        and clip_path.exists()
                        and active_ts_id
                        and active_ts_iso
                    ):
                        dest_clip = f"{camera_id}/{active_ts_id}_clip.mp4"
                        public_clip_url = None
                        try:
                            public_clip_url = acc_db.upload_file(str(clip_path), dest_clip, bucket_name="accident-clips")
                        except Exception as e:
                            self._log.exception("clip upload failure error=%s", str(e))
                        if public_clip_url:
                            self._log.info("clip upload success url=%s", str(public_clip_url))
                            try:
                                acc_db.update_accident_clip(active_accident_id, public_clip_url, active_ts_iso, camera_id)
                            except Exception as e:
                                self._log.exception("db update clip failure error=%s", str(e))
                            self._set_status(last_supabase_clip_url=public_clip_url)
                        else:
                            self._log.warning("clip upload failed url=None")
                    active_accident_id = None
                    active_ts_id = None
                    active_ts_iso = None

            if frame_index % process_every == 0:
                try:
                    results = predict_yolo(runtime, frame, acc_config.IMGSZ)
                    pred_class, conf, acc_prob = acc_utils.get_top1_and_prob(results[0], accident_idx)
                except Exception as e:
                    self._set_status(last_error=f"Inference error: {e}")
                    self._log.exception("inference error=%s", str(e))
                    frame_index += 1
                    continue

                is_acc = str(pred_class).lower() == "accident" and float(acc_prob) >= float(acc_config.CONF_THRESHOLD)
                alert, vote_sum, mean_prob = state.update(float(acc_prob), 1 if is_acc else 0, time.time())

                if is_acc and time.time() - last_pred_log_at >= 2.0:
                    last_pred_log_at = time.time()
                    self._log.info(
                        "accident predicted prob=%.3f mean=%.3f votes=%s/%s",
                        float(acc_prob),
                        float(mean_prob),
                        str(vote_sum),
                        str(len(state.window_votes)),
                    )

                if alert:
                    utc = datetime.utcnow()
                    ts_id = utc.strftime("%Y%m%d_%H%M%S")
                    ts_iso = utc.replace(microsecond=0).isoformat() + "Z"

                    self._log.warning(
                        "accident confirmed camera_id=%s ts=%s prob=%.3f mean=%.3f votes=%s/%s",
                        camera_id,
                        ts_iso,
                        float(acc_prob),
                        float(mean_prob),
                        str(vote_sum),
                        str(len(state.window_votes)),
                    )
                    anpr_plates = acc_utils.run_anpr(frame)
                    if anpr_plates:
                        self._log.info("anpr result plates=%s", ",".join([str(p) for p in anpr_plates]))
                    else:
                        self._log.info("anpr result plates=empty")

                    snap_path = snapshots_dir / f"{camera_id}_{ts_id}.jpg"
                    try:
                        ok = bool(acc_utils.cv2.imwrite(str(snap_path), frame))
                        if ok:
                            self._log.info("snapshot saved path=%s", str(snap_path))
                        else:
                            self._log.warning("snapshot save failed path=%s", str(snap_path))
                    except Exception:
                        self._log.exception("snapshot save exception path=%s", str(snap_path))

                    if clip_writer is None:
                        h, w = frame.shape[:2]
                        clip_path = clips_dir / f"{camera_id}_{ts_id}.mp4"
                        clip_writer = acc_utils.cv2.VideoWriter(
                            str(clip_path),
                            acc_utils.cv2.VideoWriter_fourcc(*"mp4v"),
                            src_fps,
                            (w, h),
                        )
                        for bf in frame_buffer:
                            try:
                                clip_writer.write(bf)
                            except Exception:
                                pass
                        try:
                            clip_writer.write(frame)
                        except Exception:
                            pass
                        clip_post_remaining = post_frames - 1
                        self._log.info("clip recording started path=%s pre_frames=%s post_frames=%s", str(clip_path), str(pre_frames), str(post_frames))

                    log_obj = {
                        "timestamp_utc": ts_iso,
                        "camera_id": camera_id,
                        "confidence": float(conf),
                        "plates": anpr_plates,
                    }
                    acc_utils.write_jsonl(session_dir / "alerts.jsonl", log_obj)

                    self._set_status(last_alert_utc=ts_iso, bump_alerts=True)

                    if bool(acc_db.SUPABASE_ENABLED):
                        public_snap_url = None
                        try:
                            public_snap_url = acc_db.upload_file(
                                str(snap_path),
                                f"{camera_id}/{ts_id}_snapshot.jpg",
                                bucket_name="accident-snapshots",
                            )
                        except Exception as e:
                            self._log.exception("snapshot upload exception error=%s", str(e))
                        if public_snap_url:
                            self._set_status(last_supabase_snapshot_url=public_snap_url)
                            self._log.info("snapshot upload success url=%s", str(public_snap_url))
                        else:
                            self._log.warning("snapshot upload failed url=None")

                        accident_record = None
                        try:
                            accident_record = acc_db.create_accident(ts_iso, camera_id, float(conf), public_snap_url, None)
                        except Exception as e:
                            self._log.exception("db insert accident exception error=%s", str(e))
                        if accident_record:
                            self._log.info("db insert accident success id=%s", str(accident_record.get("id")))
                            active_accident_id = int(accident_record["id"])
                            active_ts_id = ts_id
                            active_ts_iso = ts_iso
                        else:
                            self._log.warning("db insert accident failed")

                        linked = 0
                        for plate in anpr_plates:
                            if not active_accident_id:
                                break
                            v_rec = None
                            try:
                                v_rec = acc_db.upsert_vehicle(str(plate))
                            except Exception as e:
                                self._log.exception("db upsert vehicle exception plate=%s error=%s", str(plate), str(e))
                            if v_rec:
                                try:
                                    acc_db.link_vehicle_to_accident(active_accident_id, int(v_rec["id"]))
                                    linked += 1
                                except Exception as e:
                                    self._log.exception("db link vehicle exception plate=%s error=%s", str(plate), str(e))

                        if linked:
                            self._log.info("db link accident_vehicles linked=%s", str(linked))

                        try:
                            det_rec = acc_db.log_detection(
                                ts_iso,
                                camera_id,
                                float(conf),
                                public_snap_url,
                                None,
                                ",".join([str(p) for p in (anpr_plates or [])]) if anpr_plates else None,
                            )
                            if det_rec:
                                self._log.info("db insert detections_log success")
                            else:
                                self._log.warning("db insert detections_log failed")
                        except Exception as e:
                            self._log.exception("db insert detections_log exception error=%s", str(e))

            frame_buffer.append(frame.copy())
            frame_index += 1

        try:
            if cap:
                cap.release()
        except Exception:
            pass

        try:
            if clip_writer:
                clip_writer.release()
        except Exception:
            pass

        self._log.info("worker loop exited")
