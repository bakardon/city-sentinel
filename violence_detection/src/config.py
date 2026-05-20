from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = PROJECT_ROOT / "violence_dectection.yolov8"
DATA_YAML = DATASET_DIR / "data.yaml"

OUTPUTS_DIR = PROJECT_ROOT / "violence_detection" / "outputs"
LIVE_PREDICTIONS_DIR = OUTPUTS_DIR / "live_predictions"

DEFAULT_MODEL = os.getenv("VIOLENCE_BASE_MODEL", "yolov8s.pt")
DEFAULT_WEIGHTS = os.getenv(
    "VIOLENCE_WEIGHTS_PATH",
    str(OUTPUTS_DIR / "violence_det" / "weights" / "best.pt"),
)

IMGSZ = int(os.getenv("VIOLENCE_IMGSZ", "640"))
CONF_THRESHOLD = float(os.getenv("VIOLENCE_CONF_THRESHOLD", "0.45"))

POSITIVE_CLASSES = {"violence"}
NEGATIVE_CLASSES = {"nonviolence"}


def resolve_weights_path() -> str:
    env = str(os.getenv("VIOLENCE_WEIGHTS_PATH") or "").strip()
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.append(Path(DEFAULT_WEIGHTS))
    candidates.append(PROJECT_ROOT / "runs" / "detect" / "violence_detection" / "outputs" / "violence_det" / "weights" / "best.pt")
    runs_root = PROJECT_ROOT / "runs" / "detect" / "violence_detection" / "outputs"
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
