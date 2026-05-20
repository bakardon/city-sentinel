import argparse
import json
import os
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

import cv2
from ultralytics import YOLO

try:
    from app.main import detect_plates as detect_plates
except Exception:
    detect_plates = None

try:
    from supabase_helpers import (
        upload_file,
        create_accident,
        upsert_vehicle,
        link_vehicle_to_accident,
        log_detection
    )
    SUPABASE_ENABLED = True
except Exception as e:
    print(f"Warning: Supabase helpers not available: {e}")
    SUPABASE_ENABLED = False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--weights",
        default=r"D:\hanan_fyp\accident_detection\outputs\accident_cls\weights\best.pt",
    )

    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--webcam", type=int, help="Webcam index (e.g., 0).")
    src.add_argument("--rtsp", type=str, help="RTSP URL.")
    p.add_argument("--camera_id", type=str, default="", help="Optional camera identifier for logs/artifacts.")

    p.add_argument("--device", default="0")
    p.add_argument("--imgsz", type=int, default=224)
    p.add_argument("--process_fps", type=float, default=15.0)

    p.add_argument("--vote_window", type=int, default=10)
    p.add_argument("--vote_threshold", type=int, default=7)
    p.add_argument("--clear_threshold", type=int, default=3)
    p.add_argument("--conf_threshold", type=float, default=0.60)
    p.add_argument("--cooldown_s", type=float, default=10.0)
    p.add_argument("--pre_s", type=float, default=5.0)
    p.add_argument("--post_s", type=float, default=5.0)

    p.add_argument(
        "--outdir",
        default=r"D:\hanan_fyp\accident_detection\outputs\live_predictions",
    )
    p.add_argument("--no_save", action="store_true")
    p.add_argument("--no_show", action="store_true")
    return p.parse_args()


def _find_accident_index(names: Dict[int, str]) -> Optional[int]:
    for idx, name in names.items():
        if str(name).strip().lower() == "accident":
            return int(idx)
    return None


def _top1(result) -> Tuple[str, float]:
    probs = result.probs
    if probs is None:
        return "unknown", 0.0
    idx = int(probs.top1)
    conf = float(probs.top1conf)
    name = result.names.get(idx, str(idx))
    return str(name), conf


def _accident_prob(result, accident_idx: Optional[int]) -> float:
    probs = result.probs
    if probs is None:
        return 0.0
    if accident_idx is None:
        top1_idx = int(probs.top1)
        name = str(result.names.get(top1_idx, "")).strip().lower()
        return float(probs.top1conf) if name == "accident" else 0.0
    return float(probs.data[int(accident_idx)])


@dataclass
class TemporalState:
    window_probs: Deque[float]
    window_votes: Deque[int]
    vote_threshold: int
    clear_threshold: int
    cooldown_s: float
    in_accident: bool = False
    last_alert_ts: float = -1e9

    def update(self, prob_acc: float, vote: int, now_s: float) -> Tuple[bool, int, float]:
        self.window_probs.append(prob_acc)
        self.window_votes.append(vote)
        vote_sum = int(sum(self.window_votes))
        mean_prob = sum(self.window_probs) / max(1, len(self.window_probs))

        alert = False
        if not self.in_accident:
            if vote_sum >= self.vote_threshold and (now_s - self.last_alert_ts) >= self.cooldown_s:
                self.in_accident = True
                self.last_alert_ts = now_s
                alert = True
        else:
            if vote_sum <= self.clear_threshold:
                self.in_accident = False

        return alert, vote_sum, mean_prob


def put_label(frame, text: str, x: int, y: int, color: Tuple[int, int, int]) -> None:
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)


def _open_capture(args: argparse.Namespace) -> cv2.VideoCapture:
    if args.webcam is not None:
        cap = cv2.VideoCapture(int(args.webcam), cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 60)
        return cap
    if "OPENCV_FFMPEG_CAPTURE_OPTIONS" not in os.environ:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_transport;tcp|stimeout;5000000|max_delay;200000|buffer_size;1024000|fflags;nobuffer|flags;low_delay|fflags;discardcorrupt"
        )
    return cv2.VideoCapture(str(args.rtsp), cv2.CAP_FFMPEG)


def _default_camera_id(args: argparse.Namespace) -> str:
    if args.camera_id:
        return str(args.camera_id)
    if args.webcam is not None:
        return f"webcam_{int(args.webcam)}"
    return "rtsp"


def _write_jsonl(path: Path, obj: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _run_anpr(frame) -> List[str]:
    if detect_plates is None:
        return []
    plates = detect_plates(frame)
    if not isinstance(plates, list):
        return []
    out: List[str] = []
    for p in plates:
        if isinstance(p, str):
            v = p.strip()
            if v:
                out.append(v)
            continue
        if isinstance(p, dict):
            t = p.get("text")
            if t:
                out.append(str(t).strip())
    return [p for p in out if p]



def main() -> None:
    args = parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = outdir / f"run_{run_id}"
    snapshots_dir = run_dir / "snapshots"
    run_dir.mkdir(parents=True, exist_ok=True)
    clips_dir = run_dir / "clips"
    alerts_log_path = run_dir / "alerts.jsonl"
    if not args.no_save:
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        clips_dir.mkdir(parents=True, exist_ok=True)

    model = YOLO(args.weights)
    accident_idx = _find_accident_index(getattr(model, "names", {}) or {})

    window_n = max(1, int(args.vote_window))
    state = TemporalState(
        window_probs=deque(maxlen=window_n),
        window_votes=deque(maxlen=window_n),
        vote_threshold=int(args.vote_threshold),
        clear_threshold=int(args.clear_threshold),
        cooldown_s=float(args.cooldown_s),
    )

    cap = _open_capture(args)
    if not cap.isOpened():
        raise SystemExit("Failed to open capture source.")

    src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if src_fps <= 0.0:
        src_fps = 30.0
    process_every = max(1, int(round(src_fps / max(1e-6, float(args.process_fps)))))
    camera_id = _default_camera_id(args)

    pre_frames = max(1, int(round(float(args.pre_s) * src_fps)))
    post_frames = max(1, int(round(float(args.post_s) * src_fps)))
    frame_buffer: Deque = deque(maxlen=pre_frames)

    clip_writer: Optional[cv2.VideoWriter] = None
    clip_post_remaining = 0
    clip_path: Optional[Path] = None
    
    # Track current active accident_id to link clip later
    active_accident_id = None
    active_ts_id = None
    active_ts_iso = None

    frame_index = 0
    last_pred_class = "unknown"
    last_top1 = 0.0
    last_acc_prob = 0.0
    last_vote_sum = 0
    last_mean_prob = 0.0

    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            break

        if clip_writer is not None and clip_post_remaining > 0:
            clip_writer.write(frame)
            clip_post_remaining -= 1
            if clip_post_remaining <= 0:
                clip_writer.release()
                clip_writer = None
                
                # --- Upload Clip to Supabase when it finishes ---
                if SUPABASE_ENABLED and active_accident_id and clip_path and os.path.exists(clip_path):
                    from supabase_helpers import supabase
                    dest_clip = f"{camera_id}/{active_ts_id}_clip.mp4"
                    public_clip_url = upload_file("accidents", str(clip_path), dest_clip)
                    if public_clip_url:
                        try:
                            supabase.table("accidents").update({"clip_path": public_clip_url}).eq("id", active_accident_id).execute()
                            # Optionally update detections_log as well
                            supabase.table("detections_log").update({"clip_path": public_clip_url}).eq("event_time", active_ts_iso).eq("camera_id", camera_id).execute()
                        except Exception as e:
                            print(f"Error updating clip URL in Supabase: {e}")
                
                active_accident_id = None
                active_ts_id = None
                active_ts_iso = None

        do_process = (frame_index % process_every) == 0
        now_s = cv2.getTickCount() / cv2.getTickFrequency()
        alert = False

        if do_process:
            results = model.predict(
                source=frame,
                imgsz=args.imgsz,
                device=args.device,
                verbose=False,
            )
            r0 = results[0]
            pred_class, top1 = _top1(r0)
            acc_prob = _accident_prob(r0, accident_idx)

            is_accident = str(pred_class).strip().lower() == "accident" and acc_prob >= float(args.conf_threshold)
            vote = 1 if is_accident else 0

            alert, vote_sum, mean_prob = state.update(acc_prob, vote, now_s)

            last_pred_class = pred_class
            last_top1 = top1
            last_acc_prob = acc_prob
            last_vote_sum = vote_sum
            last_mean_prob = mean_prob

            if alert:
                utc = datetime.utcnow()
                ts_id = utc.strftime("%Y%m%d_%H%M%S")
                ts_iso = utc.replace(microsecond=0).isoformat() + "Z"
                vote_state = f"{vote_sum}/{len(state.window_votes)}"

                anpr_plates: List[str] = _run_anpr(frame)
                snapshot_path = None
                if not args.no_save:
                    snapshot_path = snapshots_dir / f"{camera_id}__{ts_id}__frame_{frame_index:09d}.jpg"
                    cv2.imwrite(str(snapshot_path), frame)

                    if clip_writer is None:
                        h, w = frame.shape[:2]
                        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                        clip_path = clips_dir / f"{camera_id}__{ts_id}__frame_{frame_index:09d}.mp4"
                        clip_writer = cv2.VideoWriter(str(clip_path), fourcc, float(src_fps), (w, h))
                        for bf in list(frame_buffer):
                            clip_writer.write(bf)
                        clip_writer.write(frame)
                        clip_post_remaining = max(0, post_frames - 1)

                log_obj = {
                    "timestamp_utc": ts_iso,
                    "camera_id": camera_id,
                    "source": {"type": "webcam" if args.webcam is not None else "rtsp", "value": args.webcam if args.webcam is not None else args.rtsp},
                    "frame_index": frame_index,
                    "predicted_class": last_pred_class,
                    "top1_confidence": float(last_top1),
                    "accident_prob": float(acc_prob),
                    "window_mean_prob": float(mean_prob),
                    "window_vote": vote_state,
                    "vote_window": int(args.vote_window),
                    "vote_threshold": int(args.vote_threshold),
                    "clear_threshold": int(args.clear_threshold),
                    "conf_threshold": float(args.conf_threshold),
                    "cooldown_s": float(args.cooldown_s),
                    "pre_s": float(args.pre_s),
                    "post_s": float(args.post_s),
                    "snapshot_path": str(snapshot_path) if snapshot_path else None,
                    "clip_path": str(clip_path) if clip_path else None,
                    "plates": anpr_plates,
                }
                _write_jsonl(alerts_log_path, log_obj)
                print(f"ACCIDENT_CONFIRMED utc={ts_iso} camera_id={camera_id} vote={vote_state} mean={mean_prob:.3f}")
                
                # --- Supabase Integration ---
                if SUPABASE_ENABLED:
                    # Upload snapshot to Supabase
                    public_snap_url = None
                    if snapshot_path and os.path.exists(snapshot_path):
                        dest_snap = f"{camera_id}/{ts_id}_snapshot.jpg"
                        public_snap_url = upload_file("accidents", str(snapshot_path), dest_snap)
                        
                    # (Note: The clip is still recording here, so we upload the clip later when it finishes)
                    
                    # Create accident record in DB
                    accident_record = create_accident(
                        event_time=ts_iso,
                        camera_id=camera_id,
                        confidence=float(last_top1),
                        snapshot_path=public_snap_url,
                        clip_path=None  # We'll update this later or leave it empty if clip not ready
                    )
                    
                    if accident_record:
                        accident_id = accident_record.get("id")
                        
                        # Store active info so the clip can update it later
                        active_accident_id = accident_id
                        active_ts_id = ts_id
                        active_ts_iso = ts_iso
                        
                        # Process plates detected during the accident frame
                        for plate in anpr_plates:
                            vehicle_record = upsert_vehicle(plate)
                            if vehicle_record:
                                link_vehicle_to_accident(accident_id, vehicle_record.get("id"))
                                
                    # Log detection to flat table
                    log_detection(
                        event_time=ts_iso,
                        camera_id=camera_id,
                        confidence=float(last_top1),
                        snapshot_path=public_snap_url,
                        clip_path=None,
                        plate_number=",".join(anpr_plates) if anpr_plates else None
                    )

        state_text = "ACCIDENT" if state.in_accident else "NORMAL"
        color = (0, 0, 255) if state.in_accident else (0, 200, 0)
        put_label(frame, state_text, 20, 40, color)
        put_label(frame, f"class={last_pred_class} conf={last_top1:.3f}", 20, 75, (255, 255, 255))
        put_label(
            frame,
            f"acc_prob={last_acc_prob:.3f} mean={last_mean_prob:.3f} votes={last_vote_sum}/{len(state.window_votes)}",
            20,
            110,
            (255, 255, 255),
        )
        if state.in_accident:
            put_label(frame, "ACCIDENT WARNING", 20, 145, (0, 255, 255))

        if not args.no_show:
            cv2.imshow("Accident Detection (Live)", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in {27, ord("q")}:
                break

        frame_buffer.append(frame.copy())
        frame_index += 1

    cap.release()
    if clip_writer is not None:
        clip_writer.release()
    if not args.no_show:
        cv2.destroyAllWindows()

    print(f"Saved run folder: {run_dir}")


if __name__ == "__main__":
    main()
