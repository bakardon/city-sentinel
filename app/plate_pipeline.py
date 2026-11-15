import cv2
import numpy as np
import time
import os
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from ultralytics import YOLO
import easyocr
from app.supabase_client import get_supabase

# Configuration
RTSP_URL = os.getenv("RTSP_URL", "")
MODEL_PATH = os.getenv("PLATE_MODEL_PATH", r"D:\hanan_fyp\runs\pk_plate2\weights\best.pt")
CAMERA_ID = os.getenv("CAMERA_ID", "cam_101")
CONFIDENCE_THRESHOLD = 0.4
DUPLICATE_INTERVAL_SECONDS = 10

class PlateDetector:
    """
    Handles vehicle plate detection and recognition pipeline.
    Uses YOLOv8 for detection and EasyOCR for text recognition.
    """
    def __init__(self, model_path: str, use_gpu: bool = True):
        self.use_gpu = use_gpu
        self.device = 0 if use_gpu else "cpu"
        print(f"Loading YOLO model from {model_path} on device={self.device}...")
        try:
            self.model = YOLO(model_path)
        except Exception as e:
            print(f"Failed to load YOLO model: {e}")
            raise

        print(f"Loading EasyOCR (gpu={use_gpu})...")
        try:
            # optimize=True loads the model faster
            self.reader = easyocr.Reader(['en'], gpu=use_gpu)
        except Exception as e:
            print(f"Failed to load EasyOCR: {e}")
            raise

    def detect_and_read(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detects plates in the frame, crops them, and reads text using OCR.
        Returns a list of detection dictionaries.
        """
        # YOLO Inference with half-precision for speed if on GPU
        results = self.model(frame, device=self.device, verbose=False, half=self.use_gpu)[0]
        
        detections = []
        if not results.boxes:
            return detections

        boxes = results.boxes.xyxy.cpu().numpy()
        confs = results.boxes.conf.cpu().numpy()
        classes = results.boxes.cls.cpu().numpy()

        for box, conf, cls in zip(boxes, confs, classes):
            if conf < CONFIDENCE_THRESHOLD:
                continue
            
            x1, y1, x2, y2 = map(int, box)
            # Ensure crop is within frame boundaries
            h, w = frame.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            
            # Skip invalid boxes
            if x2 <= x1 or y2 <= y1:
                continue

            # Crop plate region
            plate_crop = frame[y1:y2, x1:x2]
            
            # Run OCR on the crop
            text, ocr_conf = self._run_ocr(plate_crop)
            
            if text:
                detections.append({
                    "plate_number": text,
                    "confidence": float(conf),
                    "ocr_confidence": float(ocr_conf),
                    "bbox": (x1, y1, x2, y2),
                    "crop": plate_crop
                })
        
        return detections

    def _run_ocr(self, image: np.ndarray) -> Tuple[Optional[str], float]:
        """
        Runs EasyOCR on a cropped plate image.
        Applies preprocessing to improve accuracy.
        """
        try:
            # Preprocessing: Grayscale + Contrast
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
            
            # Read text
            results = self.reader.readtext(gray)
            
            best_text = ""
            best_conf = 0.0
            
            for _, text, conf in results:
                cleaned = self._clean_text(text)
                # Filter out short noise
                if len(cleaned) > 3 and conf > best_conf:
                    best_text = cleaned
                    best_conf = conf
            
            return (best_text, best_conf) if best_text else (None, 0.0)
        except Exception as e:
            print(f"OCR Error: {e}")
            return None, 0.0

    def _clean_text(self, text: str) -> str:
        """
        Cleans OCR text: removes special chars, handles common mistakes.
        """
        # Remove non-alphanumeric characters
        cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
        
        # Common OCR corrections for plates (optional but recommended)
        # cleaned = cleaned.replace('O', '0')  # O -> 0 is very common
        # cleaned = cleaned.replace('I', '1')  # I -> 1 is very common
        
        return cleaned

class SupabaseLogger:
    def __init__(self):
        self.client = get_supabase()
        if not self.client:
            print("Warning: Supabase client not initialized. Check .env")
        self.last_seen: Dict[str, datetime] = {}

    def log_detection(self, plate: str, confidence: float, camera_id: str, image_path: Optional[str] = None):
        if not self.client:
            return

        now = datetime.now(timezone.utc)
        
        # Anti-duplicate logic
        last_time = self.last_seen.get(plate)
        if last_time:
            elapsed = (now - last_time).total_seconds()
            if elapsed < DUPLICATE_INTERVAL_SECONDS:
                # Skip duplicate
                return

        try:
            data = {
                "plate_number": plate,
                "confidence": confidence,
                "camera_id": camera_id,
                "frame_time": now.isoformat(),
                "image_path": image_path
            }
            self.client.table("plate_detections").insert(data).execute()
            print(f"Logged: {plate} ({confidence:.2f})")
            
            # Update cache
            self.last_seen[plate] = now
            
            # Cleanup cache (optional, preventing memory leak for long runs)
            if len(self.last_seen) > 1000:
                self._cleanup_cache(now)
                
        except Exception as e:
            print(f"Supabase Insert Error: {e}")

    def _cleanup_cache(self, now: datetime):
        remove = []
        for pl, ts in self.last_seen.items():
            if (now - ts).total_seconds() > DUPLICATE_INTERVAL_SECONDS * 2:
                remove.append(pl)
        for pl in remove:
            del self.last_seen[pl]

def main():
    if not os.path.exists(MODEL_PATH):
        print(f"Error: Model not found at {MODEL_PATH}")
        return

    if not RTSP_URL:
        print("Error: set RTSP_URL (e.g. rtsp://user:password@camera-host:554/Streaming/Channels/101)")
        return

    detector = PlateDetector(MODEL_PATH, use_gpu=True)
    logger = SupabaseLogger()

    print(f"Connecting to video stream: {RTSP_URL}")
    cap = cv2.VideoCapture(RTSP_URL)
    
    if not cap.isOpened():
        print("Error: Could not open video stream.")
        return

    cv2.namedWindow("Real-time Plate Detection", cv2.WINDOW_NORMAL)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Stream ended or failed to read frame. Retrying...")
                time.sleep(2)
                cap = cv2.VideoCapture(RTSP_URL)
                continue

            # Detect
            detections = detector.detect_and_read(frame)
            
            # Process results
            for d in detections:
                plate = d["plate_number"]
                conf = d["confidence"]
                bbox = d["bbox"]
                
                # Log to DB
                logger.log_detection(plate, conf, CAMERA_ID)
                
                # Draw annotation
                x1, y1, x2, y2 = bbox
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"{plate} ({conf:.2f})", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

            # Display
            cv2.imshow("Real-time Plate Detection", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("Stopped by user.")
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
