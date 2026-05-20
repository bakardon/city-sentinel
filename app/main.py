from datetime import datetime, timezone, timedelta
import os
import re
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4
import base64
import threading
import time
import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .supabase_client import get_supabase, get_supabase_admin
from .vision import VisionService
from .accident_service import AccidentDetectionService
from . import accident_testing
from .fire_service import FireDetectionService
from . import fire_testing
from .knife_service import KnifeDetectionService
from . import knife_testing
from .weapon_service import WeaponDetectionService
from . import weapon_testing
from .violence_service import ViolenceDetectionService
from . import violence_testing
from .realtime_inference import get_yolo_runtime, load_module_from_path_cached, predict_yolo

app = FastAPI()
vision_service = VisionService(os.getenv("YOLO_MODEL_PATH", "yolov8m.pt"), os.getenv("PLATE_MODEL_PATH", r"D:\hanan_fyp\runs\pk_plate2\weights\best.pt"))


def _load_detection_utils(module_dir: str, cache_key: str):
    return load_module_from_path_cached(
        cache_key,
        Path(__file__).resolve().parents[1] / module_dir / "src" / "utils.py",
    )

local_people: List[Dict[str, Any]] = []
local_people_lock = threading.Lock()
people_cache: List[Dict[str, Any]] = []
people_cache_at = 0.0
people_cache_lock = threading.Lock()
people_cache_ttl = float(os.getenv("PEOPLE_CACHE_TTL_S", "5"))
plate_reader = None
plate_reader_lock = threading.Lock()
missing_entries: Dict[str, Dict[str, Any]] = {}
missing_alerts: List[Dict[str, Any]] = []
missing_lock = threading.Lock()
missing_threshold_s = int(os.getenv("MISSING_VEHICLE_THRESHOLD_S", "60"))
missing_alert_ttl_s = int(os.getenv("MISSING_VEHICLE_ALERT_TTL_S", "3600"))
alert_job_interval_s = float(os.getenv("ALERT_JOB_INTERVAL_S", "10"))
entry_camera_id = os.getenv("ENTRY_CAMERA_ID", "entry").lower()
exit_camera_id = os.getenv("EXIT_CAMERA_ID", "exit").lower()
vehicle_logs_table = (
    os.getenv("VEHICLE_LOGS_TABLE")
    or "vehicle_records"
)
local_vehicle_events: List[Dict[str, Any]] = []
local_vehicle_lock = threading.Lock()
vehicle_event_lock = threading.Lock()
vehicle_event_last_seen: Dict[str, float] = {}
vehicle_event_min_interval_s = float(os.getenv("VEHICLE_EVENT_MIN_INTERVAL_S", "2.5"))
plate_track_lock = threading.Lock()
plate_tracks_by_camera: Dict[str, List[Dict[str, Any]]] = {}
plate_track_ttl_s = float(os.getenv("PLATE_TRACK_TTL_S", "4.0"))
plate_track_iou_threshold = float(os.getenv("PLATE_TRACK_IOU_THRESHOLD", "0.35"))
plate_track_min_hits = int(os.getenv("PLATE_TRACK_MIN_HITS", "2"))

accident_worker = AccidentDetectionService(
    rtsp_url=os.getenv("ACCIDENT_RTSP_URL", ""),
    camera_id=os.getenv("ACCIDENT_CAMERA_ID", ""),
    autostart=str(os.getenv("ACCIDENT_WORKER_AUTOSTART", "1")).strip() in {"1", "true", "True", "yes", "YES"},
)

fire_worker = FireDetectionService(
    rtsp_url=os.getenv("FIRE_RTSP_URL", ""),
    camera_id=os.getenv("FIRE_CAMERA_ID", ""),
    camera_location=os.getenv("FIRE_CAMERA_LOCATION", ""),
    autostart=str(os.getenv("FIRE_WORKER_AUTOSTART", "0")).strip() in {"1", "true", "True", "yes", "YES"},
)

knife_worker = KnifeDetectionService(
    rtsp_url=os.getenv("KNIFE_RTSP_URL", ""),
    camera_id=os.getenv("KNIFE_CAMERA_ID", ""),
    camera_location=os.getenv("KNIFE_CAMERA_LOCATION", ""),
    autostart=str(os.getenv("KNIFE_WORKER_AUTOSTART", "0")).strip() in {"1", "true", "True", "yes", "YES"},
)

weapon_worker = WeaponDetectionService(
    rtsp_url=os.getenv("WEAPON_RTSP_URL", ""),
    camera_id=os.getenv("WEAPON_CAMERA_ID", ""),
    camera_location=os.getenv("WEAPON_CAMERA_LOCATION", ""),
    autostart=str(os.getenv("WEAPON_WORKER_AUTOSTART", "0")).strip() in {"1", "true", "True", "yes", "YES"},
)

violence_worker = ViolenceDetectionService(
    rtsp_url=os.getenv("VIOLENCE_RTSP_URL", ""),
    camera_id=os.getenv("VIOLENCE_CAMERA_ID", ""),
    camera_location=os.getenv("VIOLENCE_CAMERA_LOCATION", ""),
    autostart=str(os.getenv("VIOLENCE_WORKER_AUTOSTART", "0")).strip() in {"1", "true", "True", "yes", "YES"},
)

allowed_origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
    "http://localhost:8010",
    "http://127.0.0.1:8010",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "null",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    try:
        accident_worker.maybe_autostart()
    except Exception:
        pass
    try:
        fire_worker.maybe_autostart()
    except Exception:
        pass
    try:
        knife_worker.maybe_autostart()
    except Exception:
        pass
    try:
        weapon_worker.maybe_autostart()
    except Exception:
        pass
    try:
        violence_worker.maybe_autostart()
    except Exception:
        pass


@app.on_event("shutdown")
def _shutdown() -> None:
    try:
        accident_worker.stop(timeout_s=8.0)
    except Exception:
        pass
    try:
        fire_worker.stop(timeout_s=8.0)
    except Exception:
        pass
    try:
        knife_worker.stop(timeout_s=8.0)
    except Exception:
        pass
    try:
        weapon_worker.stop(timeout_s=8.0)
    except Exception:
        pass
    try:
        violence_worker.stop(timeout_s=8.0)
    except Exception:
        pass


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def find_best_match(
    embedding: np.ndarray, people: List[Dict[str, Any]], threshold: float
) -> Optional[Tuple[Dict[str, Any], float]]:
    best_score = -1.0
    best_person: Optional[Dict[str, Any]] = None
    for person in people:
        emb_list = person.get("embedding")
        if not emb_list:
            continue
        candidate = np.array(emb_list, dtype=np.float32)
        score = cosine_similarity(embedding, candidate)
        if score > best_score:
            best_score = score
            best_person = person
    if best_person is None or best_score < threshold:
        return None
    return best_person, best_score


def encode_jpg(image: np.ndarray) -> bytes:
    success, buf = cv2.imencode(".jpg", image)
    if not success:
        raise ValueError("Failed to encode image")
    return buf.tobytes()


def encode_jpg_quality(image: np.ndarray, quality: int) -> bytes:
    quality = int(max(30, min(95, quality)))
    success, buf = cv2.imencode(
        ".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    )
    if not success:
        raise ValueError("Failed to encode image")
    return buf.tobytes()


def base64_to_image(image_b64: str) -> Optional[np.ndarray]:
    try:
        raw = base64.b64decode(image_b64)
        return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        return None


def resize_for_rtsp(image: np.ndarray) -> np.ndarray:
    max_w = int(os.getenv("RTSP_MAX_WIDTH", "640"))
    max_h = int(os.getenv("RTSP_MAX_HEIGHT", "360"))
    h, w = image.shape[:2]
    scale = min(max_w / float(w), max_h / float(h), 1.0)
    if scale >= 1.0:
        return image
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def resize_for_rtsp_processing(image: np.ndarray) -> np.ndarray:
    max_w = int(os.getenv("RTSP_PROCESS_MAX_WIDTH", "1280"))
    max_h = int(os.getenv("RTSP_PROCESS_MAX_HEIGHT", "720"))
    h, w = image.shape[:2]
    scale = min(max_w / float(w), max_h / float(h), 1.0)
    if scale >= 1.0:
        return image
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def _scale_detection_boxes(
    items: List[Dict[str, Any]], sx: float, sy: float
) -> List[Dict[str, Any]]:
    scaled: List[Dict[str, Any]] = []
    for item in items or []:
        box = item.get("box")
        if not isinstance(box, dict):
            scaled.append(item)
            continue
        cloned = dict(item)
        cloned["box"] = {
            "x1": float(box.get("x1", 0.0)) * sx,
            "y1": float(box.get("y1", 0.0)) * sy,
            "x2": float(box.get("x2", 0.0)) * sx,
            "y2": float(box.get("y2", 0.0)) * sy,
        }
        scaled.append(cloned)
    return scaled


def get_plate_reader():
    global plate_reader
    if plate_reader is not None:
        return plate_reader
    with plate_reader_lock:
        if plate_reader is not None:
            return plate_reader
        try:
            import torch
            ocr_gpu_env = str(os.getenv("PLATE_OCR_USE_GPU", "auto")).strip().lower()
            try:
                cuda_ok = torch.cuda.is_available()
            except Exception:
                cuda_ok = False
            if ocr_gpu_env in {"0", "false", "no", "off", "cpu"}:
                use_gpu = False
            elif ocr_gpu_env in {"1", "true", "yes", "on", "cuda", "gpu"}:
                use_gpu = cuda_ok
            else:
                use_gpu = cuda_ok
            import easyocr
            plate_reader = easyocr.Reader(["en"], gpu=use_gpu)
        except Exception:
            plate_reader = None
    return plate_reader


def _clean_plate_text(text: Any) -> str:
    raw = str(text).upper().strip()
    cleaned = re.sub(r"[^A-Z0-9]", "", raw)
    return cleaned


def _normalize_plate_digits(value: str) -> str:
    return (
        value.replace("G", "0")
        .replace("O", "0")
        .replace("I", "1")
    )


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
    best_conf = None
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


def _box_iou(
    a: Dict[str, float],
    b: Dict[str, float],
) -> float:
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


def detect_plates(image: np.ndarray, camera_id: Optional[str] = None) -> List[Dict[str, Any]]:
    reader = get_plate_reader()
    if reader is None:
        return []
    plates: List[Dict[str, Any]] = []
    plate_boxes = vision_service.detect_plate_boxes(image)
    if plate_boxes:
        h, w = image.shape[:2]
        for x1, y1, x2, y2, det_conf in plate_boxes:
            ix1 = max(0, min(w - 1, int(x1)))
            iy1 = max(0, min(h - 1, int(y1)))
            ix2 = max(1, min(w, int(x2)))
            iy2 = max(1, min(h, int(y2)))
            if ix2 <= ix1 or iy2 <= iy1:
                continue
            crop = image[iy1:iy2, ix1:ix2]

            # Apply same preprocessing as plate_pipeline.py
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)

            text, conf = _pick_ocr_text(reader.readtext(gray))
            if not text or conf is None:
                continue
            candidate = {
                "text": text,
                "confidence": float(conf),
                "box": {
                    "x1": float(ix1),
                    "y1": float(iy1),
                    "x2": float(ix2),
                    "y2": float(iy2),
                },
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


def _iso_from_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def _frame_snapshot_b64(image: Optional[np.ndarray]) -> Optional[str]:
    if image is None:
        return None
    return base64.b64encode(encode_jpg_quality(image, 70)).decode("utf-8")


def _db_insert_entry(
    db: Any, plate: str, camera_id: Optional[str], snapshot_b64: Optional[str]
) -> None:
    existing = (
        db.table(vehicle_logs_table)
        .select("id,entry_time")
        .eq("plate_number", plate)
        .eq("status", "IN")
        .is_("exit_time", None)
        .order("entry_time", desc=True)
        .limit(1)
        .execute()
    )
    if existing.data:
        # Already logged as inside; update last seen or ignore
        return

    entry_time = datetime.now(timezone.utc).isoformat()
    try:
        db.table(vehicle_logs_table).insert(
            {
                "plate_number": plate,
                "entry_time": entry_time,
                "status": "IN",
                "entry_camera_id": camera_id,
                "alert_flag": False,
            }
        ).execute()
        print(f"DEBUG: Inserted ENTRY for {plate}")
    except Exception as e:
        print(f"ERROR: Failed to insert entry for {plate}: {e}")


def _db_update_exit(
    db: Any, plate: str, camera_id: Optional[str], snapshot_b64: Optional[str]
) -> None:
    existing = (
        db.table(vehicle_logs_table)
        .select("id,entry_time")
        .eq("plate_number", plate)
        .eq("status", "IN")
        .is_("exit_time", None)
        .order("entry_time", desc=True)
        .limit(1)
        .execute()
    )
    exit_time = datetime.now(timezone.utc).isoformat()
    if existing.data:
        row_id = existing.data[0].get("id")
        if row_id is not None:
            db.table(vehicle_logs_table).update(
                {
                    "exit_time": exit_time,
                    "status": "OUT",
                    "exit_camera_id": camera_id,
                    "alert_flag": False,
                }
            ).eq("id", row_id).execute()
            return
    db.table(vehicle_logs_table).insert(
        {
            "plate_number": plate,
            "exit_time": exit_time,
            "status": "OUT",
            "exit_camera_id": camera_id,
            "alert_flag": False,
        }
    ).execute()


def _local_insert_entry(
    plate: str, camera_id: Optional[str], snapshot_b64: Optional[str]
) -> None:
    entry_time = datetime.now(timezone.utc).isoformat()
    with local_vehicle_lock:
        for row in reversed(local_vehicle_events):
            if row.get("plate_number") == plate and row.get("status") in {
                "IN",
            }:
                return
        local_vehicle_events.append(
            {
                "plate_number": plate,
                "entry_time": entry_time,
                "status": "IN",
                "entry_camera_id": camera_id,
                "alert_flag": False,
            }
        )
        print(f"DEBUG: Local Insert ENTRY for {plate}")


def _local_update_exit(
    plate: str, camera_id: Optional[str], snapshot_b64: Optional[str]
) -> None:
    exit_time = datetime.now(timezone.utc).isoformat()
    with local_vehicle_lock:
        for row in reversed(local_vehicle_events):
            if row.get("plate_number") == plate and row.get("status") in {
                "IN",
            }:
                row["status"] = "OUT"
                row["exit_time"] = exit_time
                row["exit_camera_id"] = camera_id
                row["alert_flag"] = False
                return
        local_vehicle_events.append(
            {
                "plate_number": plate,
                "exit_time": exit_time,
                "status": "OUT",
                "exit_camera_id": camera_id,
                "alert_flag": False,
            }
        )


def _record_missing_plate(plate: str, camera_id: Optional[str]) -> None:
    if not plate:
        return
    cam = (camera_id or "").lower()
    now = time.time()
    with missing_lock:
        if entry_camera_id and entry_camera_id in cam:
            entry = missing_entries.get(plate)
            if entry is None:
                missing_entries[plate] = {
                    "plate_number": plate,
                    "first_seen": now,
                    "last_seen": now,
                    "alerted": False,
                }
            else:
                entry["last_seen"] = now
        elif exit_camera_id and exit_camera_id in cam:
            if plate in missing_entries:
                del missing_entries[plate]
            if missing_alerts:
                missing_alerts[:] = [
                    a for a in missing_alerts if a.get("plate_number") != plate
                ]
        _refresh_missing_alerts(now)


def _refresh_missing_alerts(now: Optional[float] = None) -> None:
    current = time.time() if now is None else now
    for plate, entry in list(missing_entries.items()):
        if entry.get("alerted"):
            continue
        first_seen = float(entry.get("first_seen", current))
        if current - first_seen >= missing_threshold_s:
            missing_alerts.append(
                {
                    "plate_number": plate,
                    "entry_time": _iso_from_ts(first_seen),
                    "alert_at": _iso_from_ts(current),
                    "missing_for_s": int(current - first_seen),
                    "created_at": current,
                }
            )
            entry["alerted"] = True
    if missing_alerts:
        missing_alerts[:] = [
            a
            for a in missing_alerts
            if current - float(a.get("created_at", current)) < missing_alert_ttl_s
        ]


def _update_local_alert_status(now: datetime, threshold: timedelta) -> None:
    with local_vehicle_lock:
        for row in local_vehicle_events:
            if str(row.get("status")).upper() != "IN":
                continue
            entry_time = row.get("entry_time")
            entry_dt = _parse_dt(entry_time) if entry_time else None
            if entry_dt is None:
                continue
            if now - entry_dt > threshold:
                row["alert_flag"] = True


def _alert_job_loop() -> None:
    while True:
        now = datetime.now(timezone.utc)
        threshold = timedelta(seconds=missing_threshold_s)
        supabase = get_supabase()
        if supabase:
            try:
                threshold_time = now - threshold
                supabase.table(vehicle_logs_table).update(
                    {"alert_flag": True}
                ).eq("status", "IN").lt(
                    "entry_time", threshold_time.isoformat()
                ).execute()
            except Exception:
                pass
        else:
            _update_local_alert_status(now, threshold)
        time.sleep(max(1.0, alert_job_interval_s))


threading.Thread(target=_alert_job_loop, daemon=True).start()


def record_plate_events(
    image: Optional[np.ndarray],
    plates: List[Dict[str, Any]],
    camera_id: Optional[str],
    event_type: Optional[str] = None,
) -> None:
    if not plates:
        return
    db_client = get_supabase_admin() or get_supabase()
    seen: set[str] = set()
    cam = (camera_id or "").lower()
    
    event = (event_type or "").strip().lower()
    if event in {"entry", "exit"}:
        is_entry = event == "entry"
        is_exit = event == "exit"
    else:
        is_entry = "rtsp" in cam or (entry_camera_id and entry_camera_id in cam)
        is_exit = "webcam" in cam or (exit_camera_id and exit_camera_id in cam)
    if not is_entry and not is_exit:
        return

    for plate in plates:
        text = plate.get("text")
        if not text:
            continue
        text = str(text)
        if text in seen:
            continue
        seen.add(text)
        event_name = "entry" if is_entry else "exit"
        event_key = f"{event_name}|{cam}|{text}"
        now = time.time()
        with vehicle_event_lock:
            previous = vehicle_event_last_seen.get(event_key, 0.0)
            if now - previous < vehicle_event_min_interval_s:
                continue
            vehicle_event_last_seen[event_key] = now
            if len(vehicle_event_last_seen) > 2000:
                expiry = now - max(30.0, vehicle_event_min_interval_s * 20.0)
                stale_keys = [k for k, v in vehicle_event_last_seen.items() if v < expiry]
                for key in stale_keys:
                    vehicle_event_last_seen.pop(key, None)
        
        snapshot_b64 = _frame_snapshot_b64(image)
        
        if db_client is None:
            if is_entry:
                _local_insert_entry(text, camera_id, snapshot_b64)
            elif is_exit:
                _local_update_exit(text, camera_id, snapshot_b64)
            _record_missing_plate(text, camera_id)
            continue
            
        try:
            if is_entry:
                _db_insert_entry(db_client, text, camera_id, snapshot_b64)
            elif is_exit:
                _db_update_exit(db_client, text, camera_id, snapshot_b64)
        except Exception:
            _record_missing_plate(text, camera_id)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _filter_vehicle_events(
    events: List[Dict[str, Any]],
    plate: Optional[str],
    status: Optional[str],
    start_time: Optional[str],
    end_time: Optional[str],
) -> List[Dict[str, Any]]:
    plate_q = (plate or "").strip().upper()
    status_q = (status or "").strip().upper()
    start_dt = _parse_dt(start_time)
    end_dt = _parse_dt(end_time)
    filtered: List[Dict[str, Any]] = []
    for row in events:
        row_plate = str(row.get("plate_number") or "").upper()
        if plate_q and plate_q not in row_plate:
            continue
        if status_q and str(row.get("status") or "").upper() != status_q:
            continue
        entry_time = row.get("entry_time")
        entry_dt = _parse_dt(entry_time) if entry_time else None
        if start_dt and entry_dt and entry_dt < start_dt:
            continue
        if end_dt and entry_dt and entry_dt > end_dt:
            continue
        filtered.append(row)
    return filtered


def parse_tags(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",")]
    tags = [p for p in parts if p]
    seen = set()
    ordered: List[str] = []
    for tag in tags:
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(tag)
    return ordered


def box_iou(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
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


def rect_from_box(box: Tuple[float, float, float, float]) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    x = int(x1)
    y = int(y1)
    w = max(1, int(x2 - x1))
    h = max(1, int(y2 - y1))
    return x, y, w, h


def box_from_rect(rect: Tuple[float, float, float, float]) -> Tuple[int, int, int, int]:
    x, y, w, h = rect
    x1 = max(0, int(x))
    y1 = max(0, int(y))
    x2 = max(1, int(x + w))
    y2 = max(1, int(y + h))
    return x1, y1, x2, y2


def create_tracker():
    if hasattr(cv2, "legacy") and hasattr(cv2.legacy, "TrackerCSRT_create"):
        return cv2.legacy.TrackerCSRT_create()
    if hasattr(cv2, "TrackerCSRT_create"):
        return cv2.TrackerCSRT_create()
    if hasattr(cv2, "legacy") and hasattr(cv2.legacy, "TrackerKCF_create"):
        return cv2.legacy.TrackerKCF_create()
    if hasattr(cv2, "TrackerKCF_create"):
        return cv2.TrackerKCF_create()
    return None


def clamp_box(box: Tuple[float, float, float, float], width: int, height: int) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    x1 = max(0, min(width - 1, int(x1)))
    y1 = max(0, min(height - 1, int(y1)))
    x2 = max(1, min(width, int(x2)))
    y2 = max(1, min(height, int(y2)))
    if x2 <= x1:
        x2 = min(width, x1 + 1)
    if y2 <= y1:
        y2 = min(height, y1 + 1)
    return x1, y1, x2, y2


def init_flow_points(gray: np.ndarray, box: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
    x1, y1, x2, y2 = box
    mask = np.zeros_like(gray)
    mask[y1:y2, x1:x2] = 255
    points = cv2.goodFeaturesToTrack(
        gray, mask=mask, maxCorners=40, qualityLevel=0.01, minDistance=5
    )
    return points


class FlowTracker:
    def __init__(self, frame: np.ndarray, rect: Tuple[int, int, int, int]) -> None:
        h, w = frame.shape[:2]
        x, y, rw, rh = rect
        box = (float(x), float(y), float(x + rw), float(y + rh))
        self.box = clamp_box(box, w, h)
        self.prev_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self.points = init_flow_points(self.prev_gray, self.box)
        self.fail_count = 0

    def update(self, frame: np.ndarray) -> Tuple[bool, Tuple[int, int, int, int]]:
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.points is None or len(self.points) == 0:
            self.points = init_flow_points(gray, self.box)
            if self.points is None or len(self.points) == 0:
                self.fail_count += 1
                self.prev_gray = gray
                x1, y1, x2, y2 = self.box
                return False, (int(x1), int(y1), int(x2 - x1), int(y2 - y1))
        next_pts, status, err = cv2.calcOpticalFlowPyrLK(
            self.prev_gray, gray, self.points, None,
            winSize=(21, 21), maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
        )
        if status is None or next_pts is None:
            self.fail_count += 1
            self.prev_gray = gray
            x1, y1, x2, y2 = self.box
            return False, (int(x1), int(y1), int(x2 - x1), int(y2 - y1))
        mask = status.reshape(-1) == 1
        good_old = self.points.reshape(-1, 2)[mask]
        good_new = next_pts.reshape(-1, 2)[mask]
        if good_new is None or len(good_new) == 0 or len(good_old) == 0:
            self.fail_count += 1
            self.prev_gray = gray
            x1, y1, x2, y2 = self.box
            return False, (int(x1), int(y1), int(x2 - x1), int(y2 - y1))
        dx = float(np.median(good_new[:, 0] - good_old[:, 0]))
        dy = float(np.median(good_new[:, 1] - good_old[:, 1]))
        x1, y1, x2, y2 = self.box
        nx1 = x1 + dx
        ny1 = y1 + dy
        nx2 = x2 + dx
        ny2 = y2 + dy
        nx1, ny1, nx2, ny2 = clamp_box((nx1, ny1, nx2, ny2), w, h)
        self.box = (nx1, ny1, nx2, ny2)
        self.prev_gray = gray
        self.points = good_new.reshape(-1, 1, 2)
        self.fail_count = 0
        return True, (int(nx1), int(ny1), int(nx2 - nx1), int(ny2 - ny1))


class RtspStream:
    def __init__(self, url: str) -> None:
        self.url = url
        self.lock = threading.Lock()
        self.latest_matches: List[Dict[str, Any]] = []
        self.latest_image_b64: Optional[str] = None
        self.latest_frame: Optional[np.ndarray] = None
        self.last_result_at: float = 0.0
        self.last_processed_at: float = 0.0
        self.last_request_at: float = time.time()
        self.location: Optional[str] = None
        self.camera_id: Optional[str] = None
        self.event_type: Optional[str] = None
        self.running = True
        self.process_interval = max(
            0.05, float(os.getenv("RTSP_PROCESS_INTERVAL_MS", "300")) / 1000.0
        )
        self.jpeg_quality = int(os.getenv("RTSP_JPEG_QUALITY", "65"))
        self.plate_detect_interval = max(
            0.1, float(os.getenv("RTSP_PLATE_INTERVAL_MS", "1200")) / 1000.0
        )
        self.trackers: List[Dict[str, Any]] = []
        self.tracker_ttl = max(0.5, float(os.getenv("TRACKER_TTL_MS", "1500")) / 1000.0)
        self.face_detect_interval = max(
            0.05, float(os.getenv("RTSP_FACE_DETECT_INTERVAL_MS", "250")) / 1000.0
        )
        self.face_match_threshold = float(os.getenv("RTSP_FACE_MATCH_THRESHOLD", "0.40"))
        self.poll_timeout = max(
            0.05, float(os.getenv("RTSP_POLL_TIMEOUT_MS", "300")) / 1000.0
        )
        self.reconnect_interval = max(
            0.5, float(os.getenv("RTSP_RECONNECT_MS", "2000")) / 1000.0
        )
        self.last_face_detect_at = 0.0
        self.last_tracker_update_at = 0.0
        self.last_plate_detect_at = 0.0
        self.latest_face_boxes: List[Tuple[float, float, float, float]] = []
        self.latest_plates: List[Dict[str, Any]] = []
        self.last_capture_ok_at: float = 0.0
        self.last_reconnect_at: float = 0.0
        self.last_capture_error: Optional[str] = None
        self.decode_failures = 0
        self.max_decode_failures = int(os.getenv("RTSP_MAX_DECODE_FAILURES", "10"))
        self.capture_thread = threading.Thread(target=self._run_capture, daemon=True)
        self.recognize_thread = threading.Thread(
            target=self._run_recognition, daemon=True
        )
        self.capture_thread.start()
        self.recognize_thread.start()

    def _run_capture(self) -> None:
        def open_capture() -> cv2.VideoCapture:
            if "OPENCV_FFMPEG_CAPTURE_OPTIONS" not in os.environ:
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                    "rtsp_transport;tcp|stimeout;10000000|max_delay;500000|buffer_size;2097152|fflags;discardcorrupt"
                )
            new_cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
            new_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            new_cap.set(cv2.CAP_PROP_FPS, 30)
            if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
                new_cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
            if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
                new_cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)
            return new_cap

        cap = open_capture()
        while self.running:
            if time.time() - self.last_request_at > 10:
                time.sleep(0.2)
                continue
            if not cap.isOpened():
                now = time.time()
                if now - self.last_reconnect_at >= self.reconnect_interval:
                    cap.release()
                    cap = open_capture()
                    self.last_reconnect_at = now
                    with self.lock:
                        self.last_capture_error = "RTSP stream not opened"
                time.sleep(0.1)
                continue
            
            # Use read() instead of grab() for better compatibility with some streams
            # This mimics plate_pipeline.py behavior more closely
            ret, frame = cap.read()
            
            if not ret or frame is None:
                now = time.time()
                self.decode_failures += 1
                should_reconnect = (
                    self.decode_failures >= self.max_decode_failures
                    and now - self.last_reconnect_at >= self.reconnect_interval
                )
                with self.lock:
                    # Corrupted H264 packets are common on RTSP. Keep serving the
                    # last good frame unless failures persist long enough to matter.
                    if should_reconnect or self.latest_image_b64 is None:
                        self.last_capture_error = "Failed to read RTSP frame"

                if should_reconnect:
                    cap.release()
                    time.sleep(0.1)
                    cap = open_capture()
                    self.last_reconnect_at = now
                    self.decode_failures = 0
                time.sleep(0.03)
                continue

            process_frame = resize_for_rtsp_processing(frame)
            now = time.time()
            self.last_capture_ok_at = now
            self.decode_failures = 0
            with self.lock:
                self.last_capture_error = None
            if now - self.last_face_detect_at >= self.face_detect_interval:
                face_boxes = vision_service.detect_faces(process_frame)
                with self.lock:
                    self.latest_face_boxes = list(face_boxes)
                    self.latest_matches = self._build_face_matches(
                        self.latest_face_boxes, self.latest_matches
                    )
                self.last_face_detect_at = now
            encoded = base64.b64encode(
                encode_jpg_quality(process_frame, self.jpeg_quality)
            ).decode("utf-8")
            with self.lock:
                self.latest_frame = process_frame.copy()
                self.latest_image_b64 = encoded
                self.last_result_at = now
        cap.release()

    def _run_recognition(self) -> None:
        while self.running:
            now = time.time()
            if now - self.last_processed_at < self.process_interval:
                time.sleep(0.01)
                continue
            with self.lock:
                frame = None if self.latest_frame is None else self.latest_frame.copy()
                location = self.location
                camera_id = self.camera_id
                event_type = self.event_type
                has_faces = len(self.latest_face_boxes) > 0
            if frame is None:
                time.sleep(0.02)
                continue
            do_plate = now - self.last_plate_detect_at >= self.plate_detect_interval
            matches: List[Dict[str, Any]] = []
            plates: List[Dict[str, Any]] = []
            if has_faces:
                matches = recognize_from_image(
                    frame,
                    location,
                    camera_id,
                    match_threshold=self.face_match_threshold,
                )
                if matches:
                    self._merge_recognition(matches)
                    self._refresh_trackers(frame, matches)
                else:
                    self._update_trackers(frame)
            elif self.trackers:
                self._update_trackers(frame)
            if do_plate:
                plates = detect_plates(frame, camera_id)
                record_plate_events(frame, plates, camera_id, event_type)
            with self.lock:
                if do_plate:
                    self.latest_plates = plates
                    self.last_plate_detect_at = now
                self.last_processed_at = now

    def update_context(
        self,
        location: Optional[str],
        camera_id: Optional[str],
        event_type: Optional[str] = None,
    ) -> None:
        with self.lock:
            self.location = location
            self.camera_id = camera_id
            self.event_type = event_type

    def get_latest_result(
        self, timeout_s: float, min_timestamp: Optional[float] = None
    ) -> Optional[Tuple[List[Dict[str, Any]], str, float, List[Dict[str, Any]]]]:
        self.last_request_at = time.time()
        end = time.time() + timeout_s
        while time.time() < end:
            with self.lock:
                if self.latest_image_b64 is not None:
                    if min_timestamp is None or self.last_result_at > min_timestamp:
                        proc_h, proc_w = (
                            self.latest_frame.shape[:2]
                            if self.latest_frame is not None
                            else (0, 0)
                        )
                        prev = base64_to_image(self.latest_image_b64)
                        prev_h, prev_w = prev.shape[:2] if prev is not None else (0, 0)
                        sx = (float(prev_w) / float(proc_w)) if proc_w and prev_w else 1.0
                        sy = (float(prev_h) / float(proc_h)) if proc_h and prev_h else 1.0
                        return (
                            _scale_detection_boxes(self.latest_matches, sx, sy),
                            self.latest_image_b64,
                            self.last_result_at,
                            _scale_detection_boxes(list(self.latest_plates), sx, sy),
                        )
            time.sleep(0.02)
        return None

    def _refresh_trackers(self, frame: np.ndarray, matches: List[Dict[str, Any]], reinit: bool = False) -> None:
        now = time.time()
        with self.lock:
            for m in matches:
                box = (
                    float(m["box"]["x1"]),
                    float(m["box"]["y1"]),
                    float(m["box"]["x2"]),
                    float(m["box"]["y2"]),
                )
                rect = rect_from_box(box)
                if rect[2] <= 0 or rect[3] <= 0:
                    continue
                key = m.get("person_id")
                found = None
                if key:
                    for t in self.trackers:
                        if t.get("person_id") == key:
                            found = t
                            break
                best = None
                best_iou = 0.0
                if found is None:
                    for t in self.trackers:
                        i = box_iou(box, tuple(t["last_box"]))
                        if i > best_iou:
                            best_iou = i
                            best = t
                if found is None and best is not None and (best_iou >= 0.2 or len(self.trackers) == 1):
                    found = best
                entry = found
                if entry is None:
                    tracker_obj = create_tracker()
                    flow_obj = None
                    if tracker_obj is not None:
                        tracker_obj.init(frame, rect)
                    else:
                        flow_obj = FlowTracker(frame, rect)
                    entry = {"tracker": tracker_obj, "flow_tracker": flow_obj}
                    entry["person_id"] = m.get("person_id")
                    entry["name"] = m.get("name")
                    entry["similarity"] = m.get("similarity")
                    entry["image_b64"] = m.get("image_b64")
                    entry["tags"] = m.get("tags")
                    entry["info"] = m.get("info")
                else:
                    if reinit:
                        tracker_obj = create_tracker()
                        flow_obj = None
                        if tracker_obj is not None:
                            tracker_obj.init(frame, rect)
                        else:
                            flow_obj = FlowTracker(frame, rect)
                        entry["tracker"] = tracker_obj
                        entry["flow_tracker"] = flow_obj
                    if m.get("person_id") is not None:
                        entry["person_id"] = m.get("person_id")
                    if m.get("name") is not None:
                        entry["name"] = m.get("name")
                    if m.get("similarity") is not None:
                        entry["similarity"] = m.get("similarity")
                    if m.get("image_b64") is not None:
                        entry["image_b64"] = m.get("image_b64")
                    if m.get("tags") is not None:
                        entry["tags"] = m.get("tags")
                    if m.get("info") is not None:
                        entry["info"] = m.get("info")
                entry["last_box"] = box
                entry["last_seen_at"] = now
                if found is None:
                    self.trackers.append(entry)
            self._dedupe_trackers()

    def _serialize_trackers(self) -> List[Dict[str, Any]]:
        return [
            {
                "person_id": t.get("person_id"),
                "name": t.get("name"),
                "similarity": t.get("similarity"),
                "image_b64": t.get("image_b64"),
                "tags": t.get("tags"),
                "info": t.get("info"),
                "box": {
                    "x1": t["last_box"][0],
                    "y1": t["last_box"][1],
                    "x2": t["last_box"][2],
                    "y2": t["last_box"][3],
                },
            }
            for t in self.trackers
        ]

    def _build_face_matches(
        self,
        face_boxes: List[Tuple[float, float, float, float]],
        previous: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        matches: List[Dict[str, Any]] = []
        for box in face_boxes:
            entry = {
                "person_id": None,
                "name": None,
                "similarity": None,
                "image_b64": None,
                "tags": None,
                "info": None,
                "box": {
                    "x1": box[0],
                    "y1": box[1],
                    "x2": box[2],
                    "y2": box[3],
                },
            }
            best = None
            best_iou = 0.0
            for prev in previous:
                pbox = prev.get("box", {})
                i = box_iou(
                    box,
                    (
                        float(pbox.get("x1", 0.0)),
                        float(pbox.get("y1", 0.0)),
                        float(pbox.get("x2", 0.0)),
                        float(pbox.get("y2", 0.0)),
                    ),
                )
                if i > best_iou:
                    best_iou = i
                    best = prev
            if best is not None and best_iou >= 0.3:
                entry["person_id"] = best.get("person_id")
                entry["name"] = best.get("name")
                entry["similarity"] = best.get("similarity")
                entry["image_b64"] = best.get("image_b64")
                entry["tags"] = best.get("tags")
                entry["info"] = best.get("info")
            matches.append(entry)
        return matches

    def _merge_recognition(self, matches: List[Dict[str, Any]]) -> None:
        with self.lock:
            if not self.latest_matches:
                self.latest_matches = matches
                return
            for m in matches:
                box = (
                    float(m["box"]["x1"]),
                    float(m["box"]["y1"]),
                    float(m["box"]["x2"]),
                    float(m["box"]["y2"]),
                )
                best = None
                best_iou = 0.0
                for existing in self.latest_matches:
                    ebox = existing.get("box", {})
                    i = box_iou(
                        box,
                        (
                            float(ebox.get("x1", 0.0)),
                            float(ebox.get("y1", 0.0)),
                            float(ebox.get("x2", 0.0)),
                            float(ebox.get("y2", 0.0)),
                        ),
                    )
                    if i > best_iou:
                        best_iou = i
                        best = existing
                if best is not None and best_iou >= 0.2:
                    if m.get("person_id") is not None:
                        best["person_id"] = m.get("person_id")
                    if m.get("name") is not None:
                        best["name"] = m.get("name")
                    if m.get("similarity") is not None:
                        best["similarity"] = m.get("similarity")
                    if m.get("image_b64") is not None:
                        best["image_b64"] = m.get("image_b64")
                    if m.get("tags") is not None:
                        best["tags"] = m.get("tags")
                    if m.get("info") is not None:
                        best["info"] = m.get("info")

    def _update_trackers(self, frame: np.ndarray) -> None:
        now = time.time()
        updated: List[Dict[str, Any]] = []
        with self.lock:
            kept: List[Dict[str, Any]] = []
            any_ok = False
            for t in self.trackers:
                tr = t.get("tracker")
                flow = t.get("flow_tracker")
                ok = False
                rect = None
                if tr is not None:
                    ok, rect = tr.update(frame)
                elif flow is not None:
                    ok, rect = flow.update(frame)
                if not ok or rect is None:
                    last_seen = float(t.get("last_seen_at", 0.0))
                    if now - last_seen < self.tracker_ttl:
                        kept.append(t)
                        box = t["last_box"]
                        updated.append(
                            {
                                "person_id": t.get("person_id"),
                                "name": t.get("name"),
                                "similarity": t.get("similarity"),
                                "image_b64": t.get("image_b64"),
                                "tags": t.get("tags"),
                                "info": t.get("info"),
                                "box": {
                                    "x1": box[0],
                                    "y1": box[1],
                                    "x2": box[2],
                                    "y2": box[3],
                                },
                            }
                        )
                    continue
                any_ok = True
                box = box_from_rect(rect)
                t["last_box"] = box
                t["last_seen_at"] = now
                kept.append(t)
                updated.append(
                    {
                        "person_id": t.get("person_id"),
                        "name": t.get("name"),
                        "similarity": t.get("similarity"),
                        "image_b64": t.get("image_b64"),
                        "tags": t.get("tags"),
                        "info": t.get("info"),
                        "box": {
                            "x1": box[0],
                            "y1": box[1],
                            "x2": box[2],
                            "y2": box[3],
                        },
                    }
                )
            ttl = self.tracker_ttl
            self.trackers = [t for t in kept if now - float(t.get("last_seen_at", 0.0)) < ttl]
            self._dedupe_trackers()
            if updated:
                self.latest_matches = updated
            if any_ok:
                self.last_tracker_update_at = now

    def _dedupe_trackers(self) -> None:
        if len(self.trackers) <= 1:
            return
        merged: List[Dict[str, Any]] = []
        for t in self.trackers:
            merged_into = None
            for keep in merged:
                if box_iou(tuple(t["last_box"]), tuple(keep["last_box"])) >= 0.4:
                    merged_into = keep
                    break
            if merged_into is None:
                merged.append(t)
                continue
            if merged_into.get("person_id") is None and t.get("person_id") is not None:
                merged_into["person_id"] = t.get("person_id")
                merged_into["name"] = t.get("name")
                merged_into["similarity"] = t.get("similarity")
                merged_into["image_b64"] = t.get("image_b64")
                merged_into["tags"] = t.get("tags")
                merged_into["info"] = t.get("info")
            if merged_into.get("tracker") is None and t.get("tracker") is not None:
                merged_into["tracker"] = t.get("tracker")
            if merged_into.get("flow_tracker") is None and t.get("flow_tracker") is not None:
                merged_into["flow_tracker"] = t.get("flow_tracker")
            if t.get("last_seen_at", 0) > merged_into.get("last_seen_at", 0):
                merged_into["last_box"] = t.get("last_box")
                merged_into["last_seen_at"] = t.get("last_seen_at")
        self.trackers = merged


rtsp_streams: Dict[str, RtspStream] = {}


def get_rtsp_stream(url: str) -> RtspStream:
    stream = rtsp_streams.get(url)
    if stream is None or not stream.running:
        stream = RtspStream(url)
        rtsp_streams[url] = stream
    return stream


def recognize_from_image(
    image: np.ndarray,
    location: Optional[str],
    camera_id: Optional[str],
    match_threshold: Optional[float] = None,
) -> List[Dict[str, Any]]:
    global people_cache_at
    face_embeddings = vision_service.detect_face_embeddings(image)
    if not face_embeddings:
        return []

    supabase = get_supabase()
    threshold = float(
        match_threshold
        if match_threshold is not None
        else os.getenv("FACE_MATCH_THRESHOLD", "0.45")
    )

    people: List[Dict[str, Any]] = []
    if supabase:
        now = time.time()
        with people_cache_lock:
            if people_cache and now - people_cache_at < people_cache_ttl:
                people = list(people_cache)
            else:
                res = supabase.table("persons").select(
                    "id,name,embedding,age,address,phone,notes,image_b64,tags"
                ).execute()
                people = list(res.data or [])
                people_cache.clear()
                people_cache.extend(people)
                people_cache_at = now
    else:
        with local_people_lock:
            people = list(local_people)

    results: List[Dict[str, Any]] = []
    h, w = image.shape[:2]
    for embedding, face_box in face_embeddings:
        person_id: Optional[str] = None
        person_name: Optional[str] = None
        similarity: Optional[float] = None
        info: Optional[Dict[str, Any]] = None
        tags: List[str] = []
        image_b64: Optional[str] = None
        if people:
            matched = find_best_match(embedding, people, threshold)
            if matched:
                best_person, similarity = matched
                person_id = best_person.get("id")
                person_name = best_person.get("name")
                info = {
                    "age": best_person.get("age"),
                    "address": best_person.get("address"),
                    "phone": best_person.get("phone"),
                    "notes": best_person.get("notes"),
                    "tags": tags,
                }
                raw_tags = best_person.get("tags")
                if isinstance(raw_tags, list):
                    tags = [str(t) for t in raw_tags if t]
                elif isinstance(raw_tags, str):
                    tags = parse_tags(raw_tags)
                image_b64 = best_person.get("image_b64")
        if person_id and not image_b64:
            x1, y1, x2, y2 = face_box
            ix1 = max(0, min(w - 1, int(x1)))
            iy1 = max(0, min(h - 1, int(y1)))
            ix2 = max(1, min(w, int(x2)))
            iy2 = max(1, min(h, int(y2)))
            if ix2 > ix1 and iy2 > iy1:
                face_crop = image[iy1:iy2, ix1:ix2]
            else:
                face_crop = image
            image_b64 = base64.b64encode(encode_jpg(face_crop)).decode("utf-8")
            if supabase:
                try:
                    supabase.table("persons").update(
                        {"image_b64": image_b64}
                    ).eq("id", person_id).execute()
                except Exception:
                    pass

        recognized_at = datetime.now(timezone.utc).isoformat()

        if supabase and person_id:
            try:
                supabase.table("person_events").insert(
                    {
                        "person_id": person_id,
                        "timestamp": recognized_at,
                        "location": location,
                        "camera_id": camera_id,
                    }
                ).execute()
            except Exception:
                pass

        results.append(
            {
                "person_id": person_id,
                "name": person_name,
                "similarity": similarity,
                "image_b64": image_b64,
                "tags": tags,
                "recognized_at": recognized_at,
                "location": location,
                "camera_id": camera_id,
                "info": info,
                "box": {
                    "x1": face_box[0],
                    "y1": face_box[1],
                    "x2": face_box[2],
                    "y2": face_box[3],
                },
            }
        )
    return results


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/persons")
def list_persons() -> JSONResponse:
    supabase = get_supabase()
    if supabase:
        res = supabase.table("persons").select(
            "id,name,age,address,phone,notes,image_b64,tags"
        ).execute()
        people = list(res.data or [])
    else:
        with local_people_lock:
            people = list(local_people)
    return JSONResponse({"persons": people})


@app.get("/alerts/missing")
def list_missing_alerts() -> JSONResponse:
    supabase = get_supabase()
    if supabase:
        try:
            now = datetime.now(timezone.utc)
            threshold_time = now - timedelta(seconds=missing_threshold_s)
            res = (
                supabase.table(vehicle_logs_table)
                .select("plate_number,entry_time,status,alert_flag")
                .eq("status", "IN")
                .lt("entry_time", threshold_time.isoformat())
                .execute()
            )
            alerts: List[Dict[str, Any]] = []
            for row in res.data or []:
                entry_time = row.get("entry_time")
                missing_for_s = None
                if entry_time:
                    try:
                        parsed = datetime.fromisoformat(
                            str(entry_time).replace("Z", "+00:00")
                        )
                        missing_for_s = int((now - parsed).total_seconds())
                    except Exception:
                        missing_for_s = None
                alerts.append(
                    {
                        "plate_number": row.get("plate_number"),
                        "entry_time": entry_time,
                        "alert_at": now.isoformat(),
                        "missing_for_s": missing_for_s,
                    }
                )
            return JSONResponse({"alerts": alerts, "threshold_s": missing_threshold_s})
        except Exception:
            pass
    with missing_lock:
        _refresh_missing_alerts()
        alerts = list(missing_alerts)
    return JSONResponse({"alerts": alerts, "threshold_s": missing_threshold_s})


@app.get("/accidents")
def list_accidents(
    camera_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 50,
) -> JSONResponse:
    limit = max(1, min(200, int(limit)))
    supabase = get_supabase()
    accidents: List[Dict[str, Any]] = []
    if supabase:
        try:
            q = (
                supabase.table("accidents")
                .select("id,event_time,camera_id,confidence,snapshot_path,clip_path")
                .order("event_time", desc=True)
                .limit(limit)
            )
            if camera_id:
                q = q.eq("camera_id", camera_id)
            if start_time:
                q = q.gte("event_time", start_time)
            if end_time:
                q = q.lte("event_time", end_time)
            res = q.execute()
            accidents = list(res.data or [])
        except Exception:
            accidents = []
    return JSONResponse({"accidents": accidents})


@app.get("/fire-events")
def list_fire_events(
    camera_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 50,
) -> JSONResponse:
    limit = max(1, min(200, int(limit)))
    table = str(os.getenv("FIRE_EVENTS_TABLE", "fire_events")).strip() or "fire_events"
    supabase = get_supabase()
    events: List[Dict[str, Any]] = []
    if supabase:
        try:
            q = (
                supabase.table(table)
                .select(
                    "id,event_time,camera_id,camera_location,alert_type,alert_level,confidence,description,snapshot_url,detections"
                )
                .order("event_time", desc=True)
                .limit(limit)
            )
            if camera_id:
                q = q.eq("camera_id", camera_id)
            if start_time:
                q = q.gte("event_time", start_time)
            if end_time:
                q = q.lte("event_time", end_time)
            res = q.execute()
            events = list(res.data or [])
        except Exception:
            events = []
    return JSONResponse({"events": events})


@app.get("/accident-worker/status")
def accident_worker_status() -> JSONResponse:
    s = accident_worker.status()
    return JSONResponse({"status": s.__dict__})


@app.post("/accident-worker/start")
async def accident_worker_start(payload: Optional[Dict[str, Any]] = None) -> JSONResponse:
    payload = payload or {}
    rtsp_url = payload.get("rtsp_url")
    camera_id = payload.get("camera_id")
    started = accident_worker.start(rtsp_url=rtsp_url, camera_id=camera_id)
    s = accident_worker.status()
    return JSONResponse({"success": True, "started": started, "status": s.__dict__})


@app.post("/accident-worker/stop")
def accident_worker_stop() -> JSONResponse:
    stopped = accident_worker.stop(timeout_s=8.0)
    s = accident_worker.status()
    return JSONResponse({"success": True, "stopped": stopped, "status": s.__dict__})


@app.get("/fire-worker/status")
def fire_worker_status() -> JSONResponse:
    s = fire_worker.status()
    return JSONResponse({"status": s.__dict__})


@app.post("/fire-worker/start")
async def fire_worker_start(payload: Optional[Dict[str, Any]] = None) -> JSONResponse:
    payload = payload or {}
    rtsp_url = payload.get("rtsp_url")
    camera_id = payload.get("camera_id")
    camera_location = payload.get("camera_location")
    started = fire_worker.start(rtsp_url=rtsp_url, camera_id=camera_id, camera_location=camera_location)
    s = fire_worker.status()
    return JSONResponse({"success": True, "started": started, "status": s.__dict__})


@app.post("/fire-worker/stop")
def fire_worker_stop() -> JSONResponse:
    stopped = fire_worker.stop(timeout_s=8.0)
    s = fire_worker.status()
    return JSONResponse({"success": True, "stopped": stopped, "status": s.__dict__})


@app.get("/fire-worker/frame")
def fire_worker_frame() -> JSONResponse:
    return JSONResponse(fire_worker.latest_frame())


@app.post("/fire/predict/image")
async def fire_predict_image(
    file: UploadFile = File(...),
    camera_id: Optional[str] = Form(None),
    camera_location: Optional[str] = Form(None),
) -> JSONResponse:
    image_bytes = await file.read()
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image")

    fire_config = fire_testing.get_fire_config()
    fire_utils = _load_detection_utils("fire_detection", "fire_predict_utils")
    weights_path = str(fire_config.resolve_weights_path())
    runtime = get_yolo_runtime("FIRE", weights_path, os.getenv("FIRE_DEVICE", "auto"))
    res = predict_yolo(runtime, image, fire_config.IMGSZ)[0]
    dets = fire_utils.parse_yolo_detections(res, runtime.names)
    fire = fire_utils.is_fire_present(dets, positive_labels=fire_config.POSITIVE_CLASSES, min_conf=float(fire_config.CONF_THRESHOLD))
    plotted = res.plot() if hasattr(res, "plot") else image
    if fire:
        fire_worker.log_fire_event(
            detections=[d.__dict__ for d in dets],
            snapshot_bgr=plotted,
            camera_id=(camera_id or "FIRE_WEBCAM"),
            camera_location=camera_location,
            alert_type="WEBCAM_FIRE",
        )
    encoded = base64.b64encode(encode_jpg_quality(plotted, 70)).decode("utf-8")
    return JSONResponse({"fire": bool(fire), "detections": [d.__dict__ for d in dets], "image_b64": encoded})


@app.post("/fire-test/image")
async def fire_test_image(file: UploadFile = File(...)) -> JSONResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    tmp_dir = Path(os.getenv("TEMP", r"D:\hanan_fyp")) / "fire_test_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    tmp_path = tmp_dir / f"image_{ts}_{file.filename or 'upload.jpg'}"
    tmp_path.write_bytes(data)
    result, local_path = fire_testing.predict_image_file(tmp_path)
    return JSONResponse(
        {
            "ok": result.ok,
            "kind": result.kind,
            "label": result.label,
            "confidence": result.confidence,
            "fire": result.fire,
            "artifact_url": result.artifact_url,
            "error": result.error,
        }
    )


@app.post("/fire-test/video")
async def fire_test_video(file: UploadFile = File(...)) -> JSONResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    tmp_dir = Path(os.getenv("TEMP", r"D:\hanan_fyp")) / "fire_test_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    tmp_path = tmp_dir / f"video_{ts}_{file.filename or 'upload.mp4'}"
    tmp_path.write_bytes(data)
    result, local_snap, local_clip = fire_testing.predict_video_file(tmp_path)
    snap_url = None
    clip_url = None
    ui_root = fire_testing.get_fire_config().LIVE_PREDICTIONS_DIR / "ui_tests"
    if local_snap is not None:
        rel = str(local_snap.relative_to(ui_root)).replace("\\", "/")
        snap_url = f"/fire-test/artifacts/{rel}"
    if local_clip is not None:
        rel = str(local_clip.relative_to(ui_root)).replace("\\", "/")
        clip_url = f"/fire-test/artifacts/{rel}"
    return JSONResponse(
        {
            "ok": result.ok,
            "kind": result.kind,
            "label": result.label,
            "confidence": result.confidence,
            "fire": result.fire,
            "artifact_snapshot_url": snap_url,
            "artifact_clip_url": clip_url,
            "error": result.error,
        }
    )


@app.get("/fire-test/artifacts/{rel_path:path}")
def fire_test_artifact(rel_path: str) -> FileResponse:
    p = fire_testing.safe_artifact_path(rel_path)
    if p is None:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(str(p))


@app.get("/knife-worker/status")
def knife_worker_status() -> JSONResponse:
    s = knife_worker.status()
    return JSONResponse({"status": s.__dict__})


@app.post("/knife-worker/start")
async def knife_worker_start(payload: Optional[Dict[str, Any]] = None) -> JSONResponse:
    payload = payload or {}
    rtsp_url = payload.get("rtsp_url")
    camera_id = payload.get("camera_id")
    camera_location = payload.get("camera_location")
    started = knife_worker.start(rtsp_url=rtsp_url, camera_id=camera_id, camera_location=camera_location)
    s = knife_worker.status()
    return JSONResponse({"success": True, "started": started, "status": s.__dict__})


@app.post("/knife-worker/stop")
def knife_worker_stop() -> JSONResponse:
    stopped = knife_worker.stop(timeout_s=8.0)
    s = knife_worker.status()
    return JSONResponse({"success": True, "stopped": stopped, "status": s.__dict__})


@app.get("/knife-worker/frame")
def knife_worker_frame() -> JSONResponse:
    return JSONResponse(knife_worker.latest_frame())


@app.get("/knife-events")
def list_knife_events(
    camera_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 50,
) -> JSONResponse:
    limit = max(1, min(200, int(limit)))
    table = str(os.getenv("KNIFE_EVENTS_TABLE", "knife_events")).strip() or "knife_events"
    supabase = get_supabase()
    events: List[Dict[str, Any]] = []
    if supabase:
        try:
            q = (
                supabase.table(table)
                .select(
                    "id,event_time,camera_id,camera_location,alert_type,alert_level,confidence,description,snapshot_url,detections"
                )
                .order("event_time", desc=True)
                .limit(limit)
            )
            if camera_id:
                q = q.eq("camera_id", camera_id)
            if start_time:
                q = q.gte("event_time", start_time)
            if end_time:
                q = q.lte("event_time", end_time)
            res = q.execute()
            events = list(res.data or [])
        except Exception:
            events = []
    return JSONResponse({"events": events})


@app.post("/knife/predict/image")
async def knife_predict_image(
    file: UploadFile = File(...),
    camera_id: Optional[str] = Form(None),
    camera_location: Optional[str] = Form(None),
) -> JSONResponse:
    image_bytes = await file.read()
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image")

    knife_config = knife_testing.get_knife_config()
    knife_utils = _load_detection_utils("knife_detection", "knife_predict_utils")

    weights_path = str(knife_config.resolve_weights_path())
    runtime = get_yolo_runtime("KNIFE", weights_path, os.getenv("KNIFE_DEVICE", "auto"))
    res = predict_yolo(runtime, image, knife_config.IMGSZ)[0]
    dets = knife_utils.parse_yolo_detections(res, runtime.names)
    knife = knife_utils.is_knife_present(dets, positive_labels=knife_config.POSITIVE_CLASSES, min_conf=float(knife_config.CONF_THRESHOLD))
    plotted = res.plot() if hasattr(res, "plot") else image
    if knife:
        knife_worker.log_knife_event(
            detections=[d.__dict__ for d in dets],
            snapshot_bgr=plotted,
            camera_id=(camera_id or "KNIFE_WEBCAM"),
            camera_location=camera_location,
            alert_type="WEBCAM_KNIFE",
        )
    encoded = base64.b64encode(encode_jpg_quality(plotted, 70)).decode("utf-8")
    return JSONResponse({"knife": bool(knife), "detections": [d.__dict__ for d in dets], "image_b64": encoded})


@app.post("/knife-test/image")
async def knife_test_image(file: UploadFile = File(...)) -> JSONResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    tmp_dir = Path(os.getenv("TEMP", r"D:\hanan_fyp")) / "knife_test_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    tmp_path = tmp_dir / f"image_{ts}_{file.filename or 'upload.jpg'}"
    tmp_path.write_bytes(data)
    result, _ = knife_testing.predict_image_file(tmp_path)
    return JSONResponse(
        {
            "ok": result.ok,
            "kind": result.kind,
            "label": result.label,
            "confidence": result.confidence,
            "knife": result.knife,
            "artifact_url": result.artifact_url,
            "error": result.error,
        }
    )


@app.post("/knife-test/video")
async def knife_test_video(file: UploadFile = File(...)) -> JSONResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    tmp_dir = Path(os.getenv("TEMP", r"D:\hanan_fyp")) / "knife_test_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    tmp_path = tmp_dir / f"video_{ts}_{file.filename or 'upload.mp4'}"
    tmp_path.write_bytes(data)
    result, local_snap, local_clip = knife_testing.predict_video_file(tmp_path)
    snap_url = None
    clip_url = None
    ui_root = knife_testing.get_knife_config().LIVE_PREDICTIONS_DIR / "ui_tests"
    if local_snap is not None:
        rel = str(local_snap.relative_to(ui_root)).replace("\\", "/")
        snap_url = f"/knife-test/artifacts/{rel}"
    if local_clip is not None:
        rel = str(local_clip.relative_to(ui_root)).replace("\\", "/")
        clip_url = f"/knife-test/artifacts/{rel}"
    return JSONResponse(
        {
            "ok": result.ok,
            "kind": result.kind,
            "label": result.label,
            "confidence": result.confidence,
            "knife": result.knife,
            "artifact_snapshot_url": snap_url,
            "artifact_clip_url": clip_url,
            "error": result.error,
        }
    )


@app.get("/knife-test/artifacts/{rel_path:path}")
def knife_test_artifact(rel_path: str) -> FileResponse:
    p = knife_testing.safe_artifact_path(rel_path)
    if p is None:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(str(p))


@app.get("/weapon-worker/status")
def weapon_worker_status() -> JSONResponse:
    s = weapon_worker.status()
    return JSONResponse({"status": s.__dict__})


@app.post("/weapon-worker/start")
async def weapon_worker_start(payload: Optional[Dict[str, Any]] = None) -> JSONResponse:
    payload = payload or {}
    rtsp_url = payload.get("rtsp_url")
    camera_id = payload.get("camera_id")
    camera_location = payload.get("camera_location")
    started = weapon_worker.start(rtsp_url=rtsp_url, camera_id=camera_id, camera_location=camera_location)
    s = weapon_worker.status()
    return JSONResponse({"success": True, "started": started, "status": s.__dict__})


@app.post("/weapon-worker/stop")
def weapon_worker_stop() -> JSONResponse:
    stopped = weapon_worker.stop(timeout_s=8.0)
    s = weapon_worker.status()
    return JSONResponse({"success": True, "stopped": stopped, "status": s.__dict__})


@app.get("/weapon-worker/frame")
def weapon_worker_frame() -> JSONResponse:
    return JSONResponse(weapon_worker.latest_frame())


@app.get("/weapon-events")
def list_weapon_events(
    camera_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 50,
) -> JSONResponse:
    limit = max(1, min(200, int(limit)))
    table = str(os.getenv("WEAPON_EVENTS_TABLE", "weapon_events")).strip() or "weapon_events"
    supabase = get_supabase()
    events: List[Dict[str, Any]] = []
    if supabase:
        try:
            q = (
                supabase.table(table)
                .select(
                    "id,event_time,camera_id,camera_location,alert_type,alert_level,confidence,description,snapshot_url,detections"
                )
                .order("event_time", desc=True)
                .limit(limit)
            )
            if camera_id:
                q = q.eq("camera_id", camera_id)
            if start_time:
                q = q.gte("event_time", start_time)
            if end_time:
                q = q.lte("event_time", end_time)
            res = q.execute()
            events = list(res.data or [])
        except Exception:
            events = []
    return JSONResponse({"events": events})


@app.post("/weapon/predict/image")
async def weapon_predict_image(
    file: UploadFile = File(...),
    camera_id: Optional[str] = Form(None),
    camera_location: Optional[str] = Form(None),
) -> JSONResponse:
    image_bytes = await file.read()
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image")

    weapon_config = weapon_testing.get_weapon_config()
    weapon_utils = _load_detection_utils("weapon_detection", "weapon_predict_utils")

    weights_path = str(weapon_config.resolve_weights_path())
    runtime = get_yolo_runtime("WEAPON", weights_path, os.getenv("WEAPON_DEVICE", "auto"))
    res = predict_yolo(runtime, image, weapon_config.IMGSZ)[0]
    dets = weapon_utils.parse_yolo_detections(res, runtime.names)
    weapon = weapon_utils.is_weapon_present(
        dets,
        positive_labels=weapon_config.POSITIVE_CLASSES,
        min_conf=float(weapon_config.CONF_THRESHOLD),
    )
    plotted = res.plot() if hasattr(res, "plot") else image
    if weapon:
        weapon_worker.log_weapon_event(
            detections=[d.__dict__ for d in dets],
            snapshot_bgr=plotted,
            camera_id=(camera_id or "WEAPON_WEBCAM"),
            camera_location=camera_location,
            alert_type="WEBCAM_WEAPON",
        )
    encoded = base64.b64encode(encode_jpg_quality(plotted, 70)).decode("utf-8")
    return JSONResponse({"weapon": bool(weapon), "detections": [d.__dict__ for d in dets], "image_b64": encoded})


@app.post("/weapon-test/image")
async def weapon_test_image(file: UploadFile = File(...)) -> JSONResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    tmp_dir = Path(os.getenv("TEMP", r"D:\hanan_fyp")) / "weapon_test_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    tmp_path = tmp_dir / f"image_{ts}_{file.filename or 'upload.jpg'}"
    tmp_path.write_bytes(data)
    result, _ = weapon_testing.predict_image_file(tmp_path)
    return JSONResponse(
        {
            "ok": result.ok,
            "kind": result.kind,
            "label": result.label,
            "confidence": result.confidence,
            "weapon": result.weapon,
            "artifact_url": result.artifact_url,
            "error": result.error,
        }
    )


@app.post("/weapon-test/video")
async def weapon_test_video(file: UploadFile = File(...)) -> JSONResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    tmp_dir = Path(os.getenv("TEMP", r"D:\hanan_fyp")) / "weapon_test_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    tmp_path = tmp_dir / f"video_{ts}_{file.filename or 'upload.mp4'}"
    tmp_path.write_bytes(data)
    result, local_snap, local_clip = weapon_testing.predict_video_file(tmp_path)
    ui_root = Path(weapon_testing.get_weapon_config().LIVE_PREDICTIONS_DIR) / "ui_tests"
    snap_url = None
    clip_url = None
    if local_snap is not None:
        rel = str(local_snap.relative_to(ui_root)).replace("\\", "/")
        snap_url = f"/weapon-test/artifacts/{rel}"
    if local_clip is not None:
        rel = str(local_clip.relative_to(ui_root)).replace("\\", "/")
        clip_url = f"/weapon-test/artifacts/{rel}"
    return JSONResponse(
        {
            "ok": result.ok,
            "kind": result.kind,
            "label": result.label,
            "confidence": result.confidence,
            "weapon": result.weapon,
            "artifact_snapshot_url": snap_url,
            "artifact_clip_url": clip_url,
            "error": result.error,
        }
    )


@app.get("/weapon-test/artifacts/{rel_path:path}")
def weapon_test_artifact(rel_path: str) -> FileResponse:
    p = weapon_testing.safe_artifact_path(rel_path)
    if p is None:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(str(p))


@app.get("/violence-worker/status")
def violence_worker_status() -> JSONResponse:
    s = violence_worker.status()
    return JSONResponse({"status": s.__dict__})


@app.post("/violence-worker/start")
async def violence_worker_start(payload: Optional[Dict[str, Any]] = None) -> JSONResponse:
    payload = payload or {}
    rtsp_url = payload.get("rtsp_url")
    camera_id = payload.get("camera_id")
    camera_location = payload.get("camera_location")
    started = violence_worker.start(rtsp_url=rtsp_url, camera_id=camera_id, camera_location=camera_location)
    s = violence_worker.status()
    return JSONResponse({"success": True, "started": started, "status": s.__dict__})


@app.post("/violence-worker/stop")
def violence_worker_stop() -> JSONResponse:
    stopped = violence_worker.stop(timeout_s=8.0)
    s = violence_worker.status()
    return JSONResponse({"success": True, "stopped": stopped, "status": s.__dict__})


@app.get("/violence-worker/frame")
def violence_worker_frame() -> JSONResponse:
    return JSONResponse(violence_worker.latest_frame())


@app.get("/violence-events")
def list_violence_events(
    camera_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 50,
) -> JSONResponse:
    limit = max(1, min(200, int(limit)))
    table = str(os.getenv("VIOLENCE_EVENTS_TABLE", "violence_events")).strip() or "violence_events"
    supabase = get_supabase()
    events: List[Dict[str, Any]] = []
    if supabase:
        try:
            q = (
                supabase.table(table)
                .select(
                    "id,event_time,camera_id,camera_location,alert_type,alert_level,confidence,description,snapshot_url,detections"
                )
                .order("event_time", desc=True)
                .limit(limit)
            )
            if camera_id:
                q = q.eq("camera_id", camera_id)
            if start_time:
                q = q.gte("event_time", start_time)
            if end_time:
                q = q.lte("event_time", end_time)
            res = q.execute()
            events = list(res.data or [])
        except Exception:
            events = []
    return JSONResponse({"events": events})


@app.post("/violence/predict/image")
async def violence_predict_image(
    file: UploadFile = File(...),
    camera_id: Optional[str] = Form(None),
    camera_location: Optional[str] = Form(None),
) -> JSONResponse:
    image_bytes = await file.read()
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image")

    violence_config = violence_testing.get_violence_config()
    violence_utils = _load_detection_utils("violence_detection", "violence_predict_utils")

    weights_path = str(violence_config.resolve_weights_path())
    runtime = get_yolo_runtime("VIOLENCE", weights_path, os.getenv("VIOLENCE_DEVICE", "auto"))
    res = predict_yolo(runtime, image, violence_config.IMGSZ)[0]
    dets = violence_utils.parse_yolo_detections(res, runtime.names)
    det_dicts = [d.__dict__ for d in dets]
    violence, best_pos, streak = violence_worker.evaluate_live_webcam_detection(
        det_dicts,
        camera_id=(camera_id or "VIOLENCE_WEBCAM"),
    )
    plotted = res.plot() if hasattr(res, "plot") else image
    if violence:
        violence_worker.log_violence_event(
            detections=det_dicts,
            snapshot_bgr=plotted,
            camera_id=(camera_id or "VIOLENCE_WEBCAM"),
            camera_location=camera_location,
            alert_type="WEBCAM_VIOLENCE",
        )
    encoded = base64.b64encode(encode_jpg_quality(plotted, 70)).decode("utf-8")
    return JSONResponse(
        {
            "violence": bool(violence),
            "detections": det_dicts,
            "image_b64": encoded,
            "best_positive_confidence": float(best_pos),
            "positive_streak": int(streak),
        }
    )


@app.post("/violence-test/image")
async def violence_test_image(file: UploadFile = File(...)) -> JSONResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    tmp_dir = Path(os.getenv("TEMP", r"D:\hanan_fyp")) / "violence_test_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    tmp_path = tmp_dir / f"image_{ts}_{file.filename or 'upload.jpg'}"
    tmp_path.write_bytes(data)
    result, _ = violence_testing.predict_image_file(tmp_path)
    return JSONResponse(
        {
            "ok": result.ok,
            "kind": result.kind,
            "label": result.label,
            "confidence": result.confidence,
            "violence": result.violence,
            "artifact_url": result.artifact_url,
            "error": result.error,
        }
    )


@app.post("/violence-test/video")
async def violence_test_video(file: UploadFile = File(...)) -> JSONResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    tmp_dir = Path(os.getenv("TEMP", r"D:\hanan_fyp")) / "violence_test_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    tmp_path = tmp_dir / f"video_{ts}_{file.filename or 'upload.mp4'}"
    tmp_path.write_bytes(data)
    result, local_snap, local_clip = violence_testing.predict_video_file(tmp_path)
    ui_root = Path(violence_testing.get_violence_config().LIVE_PREDICTIONS_DIR) / "ui_tests"
    snap_url = None
    clip_url = None
    if local_snap is not None:
        rel = str(local_snap.relative_to(ui_root)).replace("\\", "/")
        snap_url = f"/violence-test/artifacts/{rel}"
    if local_clip is not None:
        rel = str(local_clip.relative_to(ui_root)).replace("\\", "/")
        clip_url = f"/violence-test/artifacts/{rel}"
    return JSONResponse(
        {
            "ok": result.ok,
            "kind": result.kind,
            "label": result.label,
            "confidence": result.confidence,
            "violence": result.violence,
            "artifact_snapshot_url": snap_url,
            "artifact_clip_url": clip_url,
            "error": result.error,
        }
    )


@app.get("/violence-test/artifacts/{rel_path:path}")
def violence_test_artifact(rel_path: str) -> FileResponse:
    p = violence_testing.safe_artifact_path(rel_path)
    if p is None:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(str(p))


@app.post("/accident-test/image")
async def accident_test_image(file: UploadFile = File(...)) -> JSONResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    tmp_dir = Path(os.getenv("TEMP", r"D:\hanan_fyp")) / "accident_test_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    tmp_path = tmp_dir / f"image_{ts}_{file.filename or 'upload.jpg'}"
    tmp_path.write_bytes(data)

    try:
        nparr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception:
        img = None

    if img is not None:
        try:
            det = vision_service.person_detector(img, verbose=False, device=vision_service.yolo_device)[0]
            has_vehicle = False
            if det.boxes is not None and len(det.boxes) > 0:
                cls = det.boxes.cls.cpu().numpy()
                conf = det.boxes.conf.cpu().numpy()
                vehicle_classes = {1, 2, 3, 5, 6, 7}
                min_conf = float(os.getenv("ACCIDENT_TEST_VEHICLE_MIN_CONF", "0.25"))
                for c, p in zip(cls, conf):
                    if int(c) in vehicle_classes and float(p) >= min_conf:
                        has_vehicle = True
                        break
            if not has_vehicle:
                ui_root = accident_testing.get_accident_config().LIVE_PREDICTIONS_DIR / "ui_tests"
                run_dir = ui_root / f"image_{ts}"
                run_dir.mkdir(parents=True, exist_ok=True)
                out_path = run_dir / "input.jpg"
                cv2.imwrite(str(out_path), img)
                rel = str(out_path.relative_to(ui_root)).replace("\\", "/")
                raise HTTPException(
                    status_code=400,
                    detail=f"No vehicle detected in image (min_conf={min_conf}).",
                    headers={"x-artifact-url": f"/accident-test/artifacts/{rel}"},
                )
        except HTTPException:
            raise
        except Exception:
            pass

    if img is not None:
        try:
            faces = vision_service.detect_face_embeddings(img) or []
        except Exception:
            faces = []
        if faces:
            h, w = img.shape[:2]
            max_area = 0.0
            for _, face_box in faces:
                x1, y1, x2, y2 = face_box
                ix1 = max(0, min(w - 1, int(x1)))
                iy1 = max(0, min(h - 1, int(y1)))
                ix2 = max(1, min(w, int(x2)))
                iy2 = max(1, min(h, int(y2)))
                if ix2 <= ix1 or iy2 <= iy1:
                    continue
                area = float((ix2 - ix1) * (iy2 - iy1)) / float(max(1, w * h))
                if area > max_area:
                    max_area = area
            if max_area >= 0.08:
                ui_root = accident_testing.get_accident_config().LIVE_PREDICTIONS_DIR / "ui_tests"
                run_dir = ui_root / f"image_{ts}"
                run_dir.mkdir(parents=True, exist_ok=True)
                out_path = run_dir / "snapshot.jpg"
                cv2.imwrite(str(out_path), img)
                rel = str(out_path.relative_to(ui_root)).replace("\\", "/")
                raise HTTPException(status_code=400, detail="Face image detected; upload a road scene with a vehicle.")

    result, local_path = accident_testing.predict_image_file(tmp_path)
    artifact_url = None
    if local_path is not None:
        ui_root = accident_testing.get_accident_config().LIVE_PREDICTIONS_DIR / "ui_tests"
        rel = str(local_path.relative_to(ui_root)).replace("\\", "/")
        artifact_url = f"/accident-test/artifacts/{rel}"
    return JSONResponse(
        {
            "ok": result.ok,
            "kind": result.kind,
            "label": result.label,
            "confidence": result.confidence,
            "accident": result.accident,
            "snapshot_url": result.snapshot_url,
            "clip_url": result.clip_url,
            "artifact_url": artifact_url,
            "error": result.error,
        }
    )


@app.post("/accident-test/video")
async def accident_test_video(file: UploadFile = File(...)) -> JSONResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    tmp_dir = Path(os.getenv("TEMP", r"D:\hanan_fyp")) / "accident_test_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    tmp_path = tmp_dir / f"video_{ts}_{file.filename or 'upload.mp4'}"
    tmp_path.write_bytes(data)

    try:
        cap = cv2.VideoCapture(str(tmp_path))
        has_vehicle = False
        min_conf = float(os.getenv("ACCIDENT_TEST_VEHICLE_MIN_CONF", "0.25"))
        vehicle_classes = {1, 2, 3, 5, 6, 7}
        checked = 0
        while cap.isOpened() and checked < 60:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            checked += 1
            if checked % 5 != 0:
                continue
            det = vision_service.person_detector(frame, verbose=False, device=vision_service.yolo_device)[0]
            if det.boxes is None or len(det.boxes) == 0:
                continue
            cls = det.boxes.cls.cpu().numpy()
            conf = det.boxes.conf.cpu().numpy()
            for c, p in zip(cls, conf):
                if int(c) in vehicle_classes and float(p) >= min_conf:
                    has_vehicle = True
                    break
            if has_vehicle:
                break
        cap.release()
        if not has_vehicle:
            raise HTTPException(status_code=400, detail=f"No vehicle detected in video (min_conf={min_conf}).")
    except HTTPException:
        raise
    except Exception:
        pass

    result, local_snap, local_clip = accident_testing.predict_video_file(tmp_path)

    snap_artifact_url = None
    clip_artifact_url = None
    ui_root = accident_testing.get_accident_config().LIVE_PREDICTIONS_DIR / "ui_tests"
    if local_snap is not None:
        snap_rel = str(local_snap.relative_to(ui_root)).replace("\\", "/")
        snap_artifact_url = f"/accident-test/artifacts/{snap_rel}"
    if local_clip is not None:
        clip_rel = str(local_clip.relative_to(ui_root)).replace("\\", "/")
        clip_artifact_url = f"/accident-test/artifacts/{clip_rel}"

    return JSONResponse(
        {
            "ok": result.ok,
            "kind": result.kind,
            "label": result.label,
            "confidence": result.confidence,
            "accident": result.accident,
            "snapshot_url": result.snapshot_url,
            "clip_url": result.clip_url,
            "artifact_snapshot_url": snap_artifact_url,
            "artifact_clip_url": clip_artifact_url,
            "error": result.error,
        }
    )


@app.get("/accident-test/artifacts/{rel_path:path}")
def accident_test_artifact(rel_path: str) -> FileResponse:
    p = accident_testing.safe_artifact_path(rel_path)
    if p is None:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(str(p))


@app.get("/vehicles/events")
def list_vehicle_events(
    plate: Optional[str] = None,
    status: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 200,
) -> JSONResponse:
    limit = max(1, min(500, int(limit)))
    supabase = get_supabase()
    events: List[Dict[str, Any]] = []
    if supabase:
        try:
            res = (
                supabase.table(vehicle_logs_table)
                .select(
                    "plate_number,status,entry_time,exit_time,entry_camera_id,exit_camera_id,alert_flag"
                )
                .order("entry_time", desc=True)
                .limit(limit)
                .execute()
            )
            events = list(res.data or [])
        except Exception:
            events = []
    if not events:
        with local_vehicle_lock:
            events = list(local_vehicle_events)[-limit:]
    filtered = _filter_vehicle_events(events, plate, status, start_time, end_time)
    now = datetime.now(timezone.utc)
    inside = [
        e
        for e in filtered
        if str(e.get("status")).upper() == "IN" and not e.get("exit_time")
    ]
    exited = [
        e
        for e in filtered
        if str(e.get("status")).upper() == "OUT" and e.get("exit_time")
    ]
    missing: List[Dict[str, Any]] = []
    for row in inside:
        entry_time = row.get("entry_time")
        entry_dt = _parse_dt(entry_time) if entry_time else None
        if entry_dt is None:
            continue
        missing_for_s = int((now - entry_dt).total_seconds())
        if missing_for_s >= missing_threshold_s:
            row["alert_flag"] = True
            missing.append(
                {
                    "plate_number": row.get("plate_number"),
                    "entry_time": entry_time,
                    "alert_at": now.isoformat(),
                    "missing_for_s": missing_for_s,
                }
            )
    return JSONResponse(
        {
            "events": filtered,
            "inside": inside,
            "exited": exited,
            "missing": missing,
            "threshold_s": missing_threshold_s,
        }
    )


@app.delete("/persons/{person_id}")
async def delete_person(person_id: str) -> JSONResponse:
    supabase = get_supabase()
    db_client = get_supabase_admin() or supabase
    deleted = False

    if db_client:
        try:
            db_client.table("person_events").delete().eq("person_id", person_id).execute()
        except Exception:
            pass
        res = (
            db_client.table("persons")
            .delete()
            .eq("id", person_id)
            .execute()
        )
        if res.data:
            deleted = True
        with people_cache_lock:
            before = len(people_cache)
            people_cache[:] = [p for p in people_cache if p.get("id") != person_id]
            if len(people_cache) != before:
                deleted = True

    with local_people_lock:
        before = len(local_people)
        local_people[:] = [p for p in local_people if p.get("id") != person_id]
        if len(local_people) != before:
            deleted = True

    if not deleted:
        raise HTTPException(status_code=404, detail="Person not found")
    return JSONResponse({"person_id": person_id, "deleted": True})


@app.post("/persons/{person_id}/tags")
async def update_person_tags(
    person_id: str, tags: Optional[str] = Form(None)
) -> JSONResponse:
    tag_list = parse_tags(tags)
    supabase = get_supabase()
    db_client = get_supabase_admin() or supabase
    if db_client:
        res = (
            db_client.table("persons")
            .update({"tags": tag_list})
            .eq("id", person_id)
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Person not found")
        with people_cache_lock:
            for person in people_cache:
                if person.get("id") == person_id:
                    person["tags"] = tag_list
                    break
        return JSONResponse({"person_id": person_id, "tags": tag_list})
    with local_people_lock:
        for person in local_people:
            if person.get("id") == person_id:
                person["tags"] = tag_list
                return JSONResponse({"person_id": person_id, "tags": tag_list})
    raise HTTPException(status_code=404, detail="Person not found")


@app.post("/profiles")
async def create_profile(
    name: str = Form(...),
    file: UploadFile = File(...),
    age: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
) -> JSONResponse:
    supabase = get_supabase()
    db_client = get_supabase_admin() or supabase

    image_bytes = await file.read()
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image")

    faces = vision_service.detect_face_embeddings(image)
    if not faces:
        raise HTTPException(status_code=400, detail="No face found")

    embedding, face_box = faces[0]
    x1, y1, x2, y2 = face_box
    h, w = image.shape[:2]
    ix1 = max(0, min(w - 1, int(x1)))
    iy1 = max(0, min(h - 1, int(y1)))
    ix2 = max(1, min(w, int(x2)))
    iy2 = max(1, min(h, int(y2)))
    if ix2 <= ix1 or iy2 <= iy1:
        face_crop = image
    else:
        face_crop = image[iy1:iy2, ix1:ix2]
    person_id: Optional[str] = None
    image_b64: Optional[str] = None
    if db_client:
        image_b64 = base64.b64encode(encode_jpg(face_crop)).decode("utf-8")
        insert_res = (
            db_client.table("persons")
            .insert(
                {
                    "name": name,
                    "embedding": embedding.tolist(),
                    "age": age,
                    "address": address,
                    "phone": phone,
                    "notes": notes,
                    "image_b64": image_b64,
                    "tags": [],
                }
            )
            .execute()
        )
        if not insert_res.data:
            raise HTTPException(status_code=500, detail="Failed to create profile")
        person_id = insert_res.data[0].get("id")
    else:
        person_id = str(uuid4())
        image_b64 = base64.b64encode(encode_jpg(face_crop)).decode("utf-8")
        with local_people_lock:
            local_people.append(
                {
                    "id": person_id,
                    "name": name,
                    "embedding": embedding.tolist(),
                    "age": age,
                    "address": address,
                    "phone": phone,
                    "notes": notes,
                    "image_b64": image_b64,
                    "tags": [],
                }
            )

    return JSONResponse(
        {
            "person_id": person_id,
            "name": name,
            "age": age,
            "address": address,
            "phone": phone,
            "notes": notes,
            "image_b64": image_b64,
            "tags": [],
            "box": {
                "x1": face_box[0],
                "y1": face_box[1],
                "x2": face_box[2],
                "y2": face_box[3],
            },
        }
    )


@app.post("/recognize/person")
async def recognize_person(
    file: UploadFile = File(...),
    location: Optional[str] = Form(None),
    camera_id: Optional[str] = Form(None),
    event_type: Optional[str] = Form(None),
    enable_face: bool = Form(True),
) -> JSONResponse:
    image_bytes = await file.read()
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image")

    results = recognize_from_image(image, location, camera_id) if enable_face else []
    plates = detect_plates(image, camera_id)
    record_plate_events(image, plates, camera_id, event_type)
    if not results:
        return JSONResponse({"matches": [], "plates": plates, "message": "No face found"})
    return JSONResponse({"matches": results, "plates": plates})


@app.post("/recognize/rtsp")
async def recognize_rtsp(
    rtsp_url: str = Form(...),
    location: Optional[str] = Form(None),
    camera_id: Optional[str] = Form(None),
    last_ts: Optional[float] = Form(None),
    event_type: Optional[str] = Form(None),
) -> JSONResponse:
    stream = get_rtsp_stream(rtsp_url)
    stream.update_context(location, camera_id, event_type)
    latest = stream.get_latest_result(stream.poll_timeout, last_ts)
    if latest is None:
        with stream.lock:
            results = stream.latest_matches
            encoded = stream.latest_image_b64
            frame_ts = stream.last_result_at
            plates = list(stream.latest_plates)
            last_error = stream.last_capture_error
        if encoded is None:
            return JSONResponse(
                {
                    "matches": results,
                    "image_b64": None,
                    "frame_ts": frame_ts,
                    "plates": plates,
                    "stale": True,
                    "error": last_error or "Failed to read RTSP frame",
                }
            )
        return JSONResponse(
            {
                "matches": results,
                "image_b64": encoded,
                "frame_ts": frame_ts,
                "plates": plates,
                "stale": True,
                "error": last_error,
            }
        )
    results, encoded, frame_ts, plates = latest
    return JSONResponse(
        {"matches": results, "image_b64": encoded, "frame_ts": frame_ts, "plates": plates}
    )
