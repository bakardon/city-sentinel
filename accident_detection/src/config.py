import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from the root .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Paths Configuration
BASE_DIR = Path(r"D:\hanan_fyp\accident_detection")
DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = BASE_DIR / "outputs"

DEFAULT_WEIGHTS = OUTPUTS_DIR / "accident_cls" / "weights" / "best.pt"
LIVE_PREDICTIONS_DIR = OUTPUTS_DIR / "live_predictions"

# Supabase Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
SUPABASE_BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET") or "accidents"

# Model & Camera Defaults
PROCESS_FPS = 15.0       # Limit the FPS processed by the model to save resources
IMGSZ = 224              # Image size for YOLO classification

# Temporal Smoothing Logic
VOTE_WINDOW = 10         # Look at the last N frames
VOTE_THRESHOLD = 7       # Require N positive votes to trigger an accident alert
CLEAR_THRESHOLD = 3      # If votes drop below this, clear the accident state
CONF_THRESHOLD = 0.60    # Minimum confidence to count as an accident vote
COOLDOWN_S = 10.0        # Seconds to wait before a new alert can be fired

# Clip Buffer Logic
PRE_S = 5.0              # Seconds to buffer BEFORE the accident
POST_S = 5.0             # Seconds to record AFTER the accident
