import argparse
import csv
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Deque, Dict, Optional, Tuple

import cv2
from ultralytics import YOLO


VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--weights",
        default=r"D:\hanan_fyp\accident_detection\outputs\accident_cls\weights\best.pt",
    )
    p.add_argument("--video", required=True)
    p.add_argument(
        "--outdir",
        default=r"D:\hanan_fyp\accident_detection\outputs\video_predictions",
    )
    p.add_argument("--imgsz", type=int, default=224)
    p.add_argument("--device", default="0")
    p.add_argument("--process_fps", type=float, default=10.0)
    p.add_argument("--vote_window", type=int, default=10)
    p.add_argument("--vote_threshold", type=int, default=7)
    p.add_argument("--clear_threshold", type=int, default=3)
    p.add_argument("--min_event_gap_s", type=float, default=8.0)
    p.add_argument("--save_annotated", action="store_true")
    p.add_argument("--no_show", action="store_true")
    return p.parse_args()


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value)


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
        return float(probs.top1conf) if str(result.names.get(int(probs.top1), "")).lower() == "accident" else 0.0
    return float(probs.data[int(accident_idx)])


@dataclass
class TemporalState:
    window_probs: Deque[float]
    window_votes: Deque[int]
    vote_threshold: int
    clear_threshold: int
    min_event_gap_s: float
    in_accident: bool = False
    last_event_ts: float = -1e9

    def update(self, prob_acc: float, is_accident_pred: bool, now_s: float) -> Tuple[bool, bool, float, int]:
        self.window_probs.append(prob_acc)
        self.window_votes.append(1 if is_accident_pred else 0)

        mean_prob = sum(self.window_probs) / max(1, len(self.window_probs))
        vote_sum = int(sum(self.window_votes))

        triggered_start = False
        triggered_end = False

        if not self.in_accident:
            if (
                vote_sum >= self.vote_threshold
                and (now_s - self.last_event_ts) >= self.min_event_gap_s
            ):
                self.in_accident = True
                self.last_event_ts = now_s
                triggered_start = True
        else:
            if vote_sum <= self.clear_threshold:
                self.in_accident = False
                self.last_event_ts = now_s
                triggered_end = True

        return triggered_start, triggered_end, mean_prob, vote_sum


def put_label(frame, text: str, x: int, y: int, color: Tuple[int, int, int]) -> None:
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)


def main() -> None:
    args = parse_args()
    video_path = Path(args.video)
    if not video_path.exists() or not video_path.is_file():
        raise SystemExit(f"Video not found: {video_path}")
    if video_path.suffix.lower() not in VIDEO_EXTS:
        raise SystemExit(f"Unsupported video type: {video_path.suffix}")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = safe_name(video_path.stem)
    run_dir = outdir / f"{stem}_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshots_dir = run_dir / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit("Failed to open video.")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if fps <= 0.0:
        fps = 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    process_every = max(1, int(round(fps / max(1e-6, float(args.process_fps)))))
    window_frames = max(1, int(args.vote_window))

    model = YOLO(args.weights)
    accident_idx = _find_accident_index(getattr(model, "names", {}) or {})

    state = TemporalState(
        window_probs=deque(maxlen=window_frames),
        window_votes=deque(maxlen=window_frames),
        vote_threshold=int(args.vote_threshold),
        clear_threshold=int(args.clear_threshold),
        min_event_gap_s=float(args.min_event_gap_s),
    )

    writer = None
    if args.save_annotated:
        out_video = run_dir / "annotated.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(out_video), fourcc, fps, (width, height))

    csv_path = run_dir / "predictions.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        csvw = csv.writer(f)
        csvw.writerow(
            [
                "frame_index",
                "time_s",
                "predicted_class",
                "top1_conf",
                "accident_prob",
                "window_mean_prob",
                "window_vote_sum",
                "window_size",
                "state",
                "event",
            ]
        )

        frame_index = 0
        processed_index = 0
        last_pred_class = "unknown"
        last_top1 = 0.0
        last_acc_prob = 0.0
        last_mean = 0.0
        last_votes = 0

        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break

            time_s = frame_index / fps
            do_process = (frame_index % process_every) == 0
            event = ""

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
                is_acc_pred = str(pred_class).strip().lower() == "accident"

                started, ended, mean_prob, vote_sum = state.update(acc_prob, is_acc_pred, time_s)

                last_pred_class = pred_class
                last_top1 = top1
                last_acc_prob = acc_prob
                last_mean = mean_prob
                last_votes = vote_sum

                if started:
                    event = "ACCIDENT_START"
                    snap = snapshots_dir / f"start_{processed_index:06d}_{time_s:.2f}.jpg"
                    cv2.imwrite(str(snap), frame)
                elif ended:
                    event = "ACCIDENT_END"
                    snap = snapshots_dir / f"end_{processed_index:06d}_{time_s:.2f}.jpg"
                    cv2.imwrite(str(snap), frame)

                csvw.writerow(
                    [
                        frame_index,
                        f"{time_s:.3f}",
                        pred_class,
                        f"{top1:.6f}",
                        f"{acc_prob:.6f}",
                        f"{mean_prob:.6f}",
                        vote_sum,
                        len(state.window_votes),
                        "ACCIDENT" if state.in_accident else "NORMAL",
                        event,
                    ]
                )
                processed_index += 1

            state_text = "ACCIDENT" if state.in_accident else "NORMAL"
            color = (0, 0, 255) if state.in_accident else (0, 200, 0)
            put_label(frame, f"{state_text}", 20, 40, color)
            put_label(frame, f"class={last_pred_class} conf={last_top1:.3f}", 20, 75, (255, 255, 255))
            put_label(
                frame,
                f"acc_prob={last_acc_prob:.3f} mean={last_mean:.3f} votes={last_votes}/{len(state.window_votes)}",
                20,
                110,
                (255, 255, 255),
            )
            if state.in_accident:
                put_label(frame, "ACCIDENT WARNING", 20, 145, (0, 255, 255))
            elif event:
                put_label(frame, event, 20, 145, (0, 255, 255))

            if writer is not None:
                writer.write(frame)

            if not args.no_show:
                cv2.imshow("Accident Detection", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in {27, ord("q")}:
                    break

            frame_index += 1

    cap.release()
    if writer is not None:
        writer.release()
    if not args.no_show:
        cv2.destroyAllWindows()

    print(f"Saved run folder: {run_dir}")
    print(f"Saved CSV: {csv_path}")
    if args.save_annotated:
        print("Saved annotated video: annotated.mp4")
    print(f"Saved snapshots: {snapshots_dir}")


if __name__ == "__main__":
    main()
