import argparse
import cv2
from collections import deque
from ultralytics import YOLO

import config
from utils import TemporalState, find_accident_index, get_top1_and_prob, put_label

def parse_args():
    parser = argparse.ArgumentParser(description="Predict Accident on a Video File (Local)")
    parser.add_argument("--weights", default=str(config.DEFAULT_WEIGHTS), help="Path to best.pt")
    parser.add_argument("--source", required=True, help="Path to video file")
    parser.add_argument("--no_show", action="store_true")
    parser.add_argument("--max_frames", type=int, default=0)
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Initialize Model & Temporal State
    model = YOLO(args.weights)
    accident_idx = find_accident_index(getattr(model, "names", {}) or {})
    
    state = TemporalState(
        window_probs=deque(maxlen=config.VOTE_WINDOW),
        window_votes=deque(maxlen=config.VOTE_WINDOW),
        vote_threshold=config.VOTE_THRESHOLD,
        clear_threshold=config.CLEAR_THRESHOLD,
        cooldown_s=config.COOLDOWN_S
    )

    cap = cv2.VideoCapture(args.source)
    if not cap.isOpened():
        print(f"Error: Could not open video {args.source}")
        return

    print("Running video inference... Press 'q' to stop.")
    frame_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        frame_count += 1
        if int(args.max_frames) > 0 and frame_count > int(args.max_frames):
            break

        now_s = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        
        # Classify the frame
        results = model.predict(frame, imgsz=config.IMGSZ, verbose=False)
        pred_class, conf, acc_prob = get_top1_and_prob(results[0], accident_idx)

        # Vote and update state
        is_accident = pred_class.lower() == "accident" and acc_prob >= config.CONF_THRESHOLD
        alert, vote_sum, mean_prob = state.update(acc_prob, 1 if is_accident else 0, now_s)

        if alert:
            print(f"ACCIDENT DETECTED! Timestamp: {now_s:.2f}s | Votes: {vote_sum}/{config.VOTE_WINDOW}")

        # UI Drawing
        color = (0, 0, 255) if state.in_accident else (0, 255, 0)
        put_label(frame, "ACCIDENT" if state.in_accident else "NORMAL", 20, 40, color)
        put_label(frame, f"Conf: {acc_prob:.2f} | Votes: {vote_sum}/{config.VOTE_WINDOW}", 20, 80, (255, 255, 255))
        
        if state.in_accident:
            put_label(frame, "WARNING", 20, 120, (0, 255, 255))

        if not args.no_show:
            cv2.imshow("Video Prediction", frame)
            if cv2.waitKey(1) & 0xFF in {27, ord('q')}:
                break

    cap.release()
    if not args.no_show:
        cv2.destroyAllWindows()
    print("Video inference complete.")

if __name__ == "__main__":
    main()
