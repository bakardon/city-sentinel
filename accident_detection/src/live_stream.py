import argparse
import cv2
import os
from collections import deque
from datetime import datetime
from ultralytics import YOLO

import config
import utils as utils_mod
from utils import (
    TemporalState, find_accident_index, get_top1_and_prob, 
    put_label, open_capture, write_jsonl, run_anpr
)
from database import (
    SUPABASE_ENABLED, upload_file, create_accident, upsert_vehicle, 
    link_vehicle_to_accident, log_detection, update_accident_clip
)

def parse_args():
    parser = argparse.ArgumentParser(description="Live Stream Accident Detection with Database Sync")
    parser.add_argument("--weights", default=str(config.DEFAULT_WEIGHTS), help="Path to best.pt")
    
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--webcam", type=int, help="Webcam index (e.g., 0)")
    src.add_argument("--rtsp", type=str, help="RTSP URL")
    src.add_argument("--video", type=str, help="Local video file path (for testing the live pipeline)")
    
    parser.add_argument("--camera_id", type=str, default="", help="Optional camera identifier")
    parser.add_argument("--no_anpr", action="store_true", help="Disable ANPR stage")
    parser.add_argument("--no_db", action="store_true", help="Disable Supabase/database stage")
    parser.add_argument("--no_show", action="store_true", help="Run headless (no OpenCV window)")
    parser.add_argument("--max_frames", type=int, default=0, help="Stop after N frames (0 = no limit)")
    return parser.parse_args()

def main():
    args = parse_args()
    camera_id = args.camera_id or (
        f"webcam_{args.webcam}"
        if args.webcam is not None
        else ("rtsp" if args.rtsp is not None else "video")
    )
    anpr_enabled = not bool(args.no_anpr)
    db_enabled = bool(SUPABASE_ENABLED) and not bool(args.no_db)
    print(f"ANPR enabled={anpr_enabled} available={utils_mod.detect_plates is not None}")
    print(f"Supabase enabled={db_enabled}")
    
    # Setup Output Directories
    run_dir = config.LIVE_PREDICTIONS_DIR / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    snapshots_dir = run_dir / "snapshots"
    clips_dir = run_dir / "clips"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    clips_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize Model & Temporal Logic
    model = YOLO(args.weights)
    accident_idx = find_accident_index(getattr(model, "names", {}) or {})
    
    state = TemporalState(
        window_probs=deque(maxlen=config.VOTE_WINDOW),
        window_votes=deque(maxlen=config.VOTE_WINDOW),
        vote_threshold=config.VOTE_THRESHOLD,
        clear_threshold=config.CLEAR_THRESHOLD,
        cooldown_s=config.COOLDOWN_S
    )

    # Initialize Video Capture & Buffer
    source = args.webcam if args.webcam is not None else (args.rtsp if args.rtsp is not None else args.video)
    cap = open_capture(source)
    if not cap.isOpened():
        print(f"Failed to open source: {source}")
        return

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    process_every = max(1, int(round(src_fps / config.PROCESS_FPS)))
    
    pre_frames = max(1, int(round(config.PRE_S * src_fps)))
    post_frames = max(1, int(round(config.POST_S * src_fps)))
    frame_buffer = deque(maxlen=pre_frames)
    
    # Clip Tracking State
    clip_writer = None
    clip_post_remaining = 0
    clip_path = None
    active_accident_id = None
    active_ts_id = None
    active_ts_iso = None
    
    frame_index = 0
    frame_count = 0

    print(f"Starting live stream on {camera_id}... Press 'q' to stop.")

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        frame_count += 1
        if int(args.max_frames) > 0 and frame_count > int(args.max_frames):
            break

        # ---------------------------------------------------------
        # 1. Handle Video Clip Recording
        # ---------------------------------------------------------
        if clip_writer is not None and clip_post_remaining > 0:
            clip_writer.write(frame)
            clip_post_remaining -= 1
            if clip_post_remaining <= 0:
                clip_writer.release()
                clip_writer = None
                
                # Upload the completed clip to Supabase
                if db_enabled and active_accident_id and clip_path and os.path.exists(clip_path):
                    dest_clip = f"{camera_id}/{active_ts_id}_clip.mp4"
                    public_clip_url = upload_file(str(clip_path), dest_clip)
                    if public_clip_url:
                        update_accident_clip(active_accident_id, public_clip_url, active_ts_iso, camera_id)
                
                # Reset tracking
                active_accident_id = None
                active_ts_id = None
                active_ts_iso = None

        # ---------------------------------------------------------
        # 2. Process Current Frame
        # ---------------------------------------------------------
        if frame_index % process_every == 0:
            now_s = cv2.getTickCount() / cv2.getTickFrequency()
            
            # Predict
            results = model.predict(frame, imgsz=config.IMGSZ, verbose=False)
            pred_class, conf, acc_prob = get_top1_and_prob(results[0], accident_idx)
            
            # Vote
            is_acc = pred_class.lower() == "accident" and acc_prob >= config.CONF_THRESHOLD
            alert, vote_sum, mean_prob = state.update(acc_prob, 1 if is_acc else 0, now_s)

            # Confirm Accident
            if alert:
                utc = datetime.utcnow()
                ts_id = utc.strftime("%Y%m%d_%H%M%S")
                ts_iso = utc.replace(microsecond=0).isoformat() + "Z"
                
                # Run ANPR
                anpr_plates = run_anpr(frame) if anpr_enabled else []
                
                # Save Snapshot Local
                snap_path = snapshots_dir / f"{camera_id}_{ts_id}.jpg"
                cv2.imwrite(str(snap_path), frame)
                
                # Initialize Video Clip Recording
                if clip_writer is None:
                    h, w = frame.shape[:2]
                    clip_path = clips_dir / f"{camera_id}_{ts_id}.mp4"
                    clip_writer = cv2.VideoWriter(str(clip_path), cv2.VideoWriter_fourcc(*"mp4v"), src_fps, (w, h))
                    for bf in frame_buffer:
                        clip_writer.write(bf)
                    clip_writer.write(frame)
                    clip_post_remaining = post_frames - 1

                # Local JSONL Log
                log_obj = {"timestamp_utc": ts_iso, "camera_id": camera_id, "confidence": conf, "plates": anpr_plates}
                write_jsonl(run_dir / "alerts.jsonl", log_obj)
                print(f"[{ts_iso}] ACCIDENT CONFIRMED! Camera: {camera_id} | Plates: {anpr_plates}")

                # Database Upload & Sync
                if db_enabled:
                    public_snap_url = upload_file(str(snap_path), f"{camera_id}/{ts_id}_snapshot.jpg")
                    accident_record = create_accident(ts_iso, camera_id, conf, public_snap_url, None)
                    
                    if accident_record:
                        active_accident_id = accident_record["id"]
                        active_ts_id = ts_id
                        active_ts_iso = ts_iso
                        
                        # Process Plates
                        for plate in anpr_plates:
                            v_rec = upsert_vehicle(plate)
                            if v_rec:
                                link_vehicle_to_accident(active_accident_id, v_rec["id"])
                            
                    # Unified Log
                    log_detection(ts_iso, camera_id, conf, public_snap_url, None, ",".join(anpr_plates) if anpr_plates else None)

        # ---------------------------------------------------------
        # 3. Draw & Display
        # ---------------------------------------------------------
        color = (0, 0, 255) if state.in_accident else (0, 200, 0)
        put_label(frame, "ACCIDENT" if state.in_accident else "NORMAL", 20, 40, color)
        
        if not args.no_show:
            cv2.imshow("Live Accident Detection", frame)
            if cv2.waitKey(1) & 0xFF in {27, ord('q')}:
                break
        
        # Buffer the frame
        frame_buffer.append(frame.copy())
        frame_index += 1

    # Cleanup
    cap.release()
    if clip_writer:
        clip_writer.release()
        if db_enabled and active_accident_id and clip_path and os.path.exists(clip_path):
            dest_clip = f"{camera_id}/{active_ts_id}_clip.mp4"
            public_clip_url = upload_file(str(clip_path), dest_clip)
            if public_clip_url:
                update_accident_clip(active_accident_id, public_clip_url, active_ts_iso, camera_id)
    if not args.no_show:
        cv2.destroyAllWindows()
    print(f"Run finished. Artifacts saved in: {run_dir}")

if __name__ == "__main__":
    main()
