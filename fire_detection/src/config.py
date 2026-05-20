from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ds1 = PROJECT_ROOT / "Fire-Detection.yolov8"
_ds2 = PROJECT_ROOT / "fire-detection.yolov8"
DATASET_DIR = _ds1 if _ds1.exists() else _ds2
DATA_YAML = DATASET_DIR / "data.yaml"

OUTPUTS_DIR = PROJECT_ROOT / "fire_detection" / "outputs"
LIVE_PREDICTIONS_DIR = OUTPUTS_DIR / "live_predictions"

DEFAULT_MODEL = os.getenv("FIRE_BASE_MODEL", "yolov8n.pt")
DEFAULT_WEIGHTS = os.getenv(
    "FIRE_WEIGHTS_PATH",
    str(OUTPUTS_DIR / "fire_det" / "weights" / "best.pt"),
)

IMGSZ = int(os.getenv("FIRE_IMGSZ", "640"))
CONF_THRESHOLD = float(os.getenv("FIRE_CONF_THRESHOLD", "0.50"))

POSITIVE_CLASSES = {"fire", "smoke"}


def resolve_weights_path() -> str:
    env = str(os.getenv("FIRE_WEIGHTS_PATH") or "").strip()
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.append(Path(DEFAULT_WEIGHTS))
    candidates.append(PROJECT_ROOT / "runs" / "detect" / "fire_detection" / "outputs" / "fire_det" / "weights" / "best.pt")
    runs_root = PROJECT_ROOT / "runs" / "detect" / "fire_detection" / "outputs"
    if runs_root.exists():
        bests = sorted(runs_root.glob("**/weights/best.pt"), key=lambda p: p.stat().st_mtime, reverse=True)
        candidates.extend(bests[:3])
    for p in candidates:
        try:
            if p.exists():
                return str(p)
        except Exception:
            continue
    return str(DEFAULT_MODEL)
