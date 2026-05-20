from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = PROJECT_ROOT / "weapon-detection.yolov8"
DATA_YAML = DATASET_DIR / "data.yaml"

OUTPUTS_DIR = PROJECT_ROOT / "weapon_detection" / "outputs"
LIVE_PREDICTIONS_DIR = OUTPUTS_DIR / "live_predictions"

DEFAULT_MODEL = os.getenv("WEAPON_BASE_MODEL", "yolov8s.pt")
DEFAULT_WEIGHTS = os.getenv(
    "WEAPON_WEIGHTS_PATH",
    str(OUTPUTS_DIR / "weapon_det" / "weights" / "best.pt"),
)

IMGSZ = int(os.getenv("WEAPON_IMGSZ", "640"))
CONF_THRESHOLD = float(os.getenv("WEAPON_CONF_THRESHOLD", "0.45"))

POSITIVE_CLASSES = {
    "guns",
    "guns perspective",
    "heavy gun",
    "knife",
    "knife_deploy",
    "knife_weapon",
    "long guns",
    "pistol",
    "rifle",
    "shotgun",
    "guns",
    "handgun",
    "heavyweapon",
    "larga",
    "pistols",
    "weapon",
}
NEGATIVE_CLASSES = {"aggressor", "blood", "hand", "person", "victim", "al", "violence", "stabbing"}


def resolve_weights_path() -> str:
    env = str(os.getenv("WEAPON_WEIGHTS_PATH") or "").strip()
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.append(Path(DEFAULT_WEIGHTS))
    candidates.append(PROJECT_ROOT / "runs" / "detect" / "weapon_detection" / "outputs" / "weapon_det" / "weights" / "best.pt")
    runs_root = PROJECT_ROOT / "runs" / "detect" / "weapon_detection" / "outputs"
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
