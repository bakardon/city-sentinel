import json
import os
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

import cv2

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    # Safely import the main ANPR function if available
    from app.anpr import detect_plates
except Exception:
    detect_plates = None


def find_accident_index(names: Dict[int, str]) -> Optional[int]:
    """Find the class index corresponding to 'accident'."""
    for idx, name in names.items():
        if str(name).strip().lower() == "accident":
            return int(idx)
    return None


def get_top1_and_prob(result, accident_idx: Optional[int]) -> Tuple[str, float, float]:
    """Extracts top-1 class name, confidence, and the specific accident probability."""
    probs = result.probs
    if probs is None:
        return "unknown", 0.0, 0.0
        
    idx = int(probs.top1)
    conf = float(probs.top1conf)
    name = str(result.names.get(idx, str(idx)))
    
    acc_prob = 0.0
    if accident_idx is None:
        if name.strip().lower() == "accident":
            acc_prob = conf
    else:
        acc_prob = float(probs.data[int(accident_idx)])
        
    return name, conf, acc_prob


@dataclass
class TemporalState:
    """Handles temporal smoothing using a sliding window for accident detection."""
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
    """Draws a bordered text label on the OpenCV frame."""
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)


def open_capture(source) -> cv2.VideoCapture:
    """Opens a video capture from a webcam index, file path, or RTSP stream."""
    # Handle Webcam
    if isinstance(source, int) or (isinstance(source, str) and source.isdigit()):
        cap = cv2.VideoCapture(int(source), cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 60)
        return cap
        
    # Handle RTSP or Video File
    if "OPENCV_FFMPEG_CAPTURE_OPTIONS" not in os.environ:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_transport;tcp|stimeout;5000000|max_delay;200000|"
            "buffer_size;1024000|fflags;nobuffer|flags;low_delay|fflags;discardcorrupt"
        )
    cap = cv2.VideoCapture(str(source), cv2.CAP_FFMPEG)
    try:
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 60000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 60000)
    except Exception:
        pass
    return cap


def write_jsonl(path: Path, obj: Dict) -> None:
    """Appends a JSON object to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def run_anpr(frame) -> List[str]:
    """Runs the external ANPR module on the frame and returns formatted plates."""
    if detect_plates is None:
        return []
    
    plates = detect_plates(frame)
    if not isinstance(plates, list):
        return []
        
    out: List[str] = []
    for p in plates:
        if isinstance(p, str):
            v = p.strip()
            if v: out.append(v)
        elif isinstance(p, dict):
            t = p.get("text")
            if t: out.append(str(t).strip())
            
    return [p for p in out if p]
