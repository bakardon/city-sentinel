import os
import mimetypes
from supabase import create_client, Client
import config

if config.SUPABASE_URL and config.SUPABASE_KEY:
    supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    SUPABASE_ENABLED = True
else:
    supabase = None
    SUPABASE_ENABLED = False
    print("Warning: SUPABASE_URL or SUPABASE_KEY not set. Database integration disabled.")

def upload_file(file_path: str, destination_path: str, bucket_name: str = None) -> str:
    """Uploads a local file to Supabase storage and returns the public URL."""
    if not SUPABASE_ENABLED or not os.path.exists(file_path):
        return None
        
    # Auto-route to the correct bucket based on file extension
    if bucket_name is None:
        if file_path.lower().endswith('.mp4'):
            bucket_name = "accident-clips"
        elif file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
            bucket_name = "accident-snapshots"
        else:
            bucket_name = config.SUPABASE_BUCKET  # Fallback
            
    content_type, _ = mimetypes.guess_type(file_path)
    if content_type is None:
        content_type = 'application/octet-stream'
        
    try:
        with open(file_path, 'rb') as f:
            supabase.storage.from_(bucket_name).upload(
                file=f,
                path=destination_path,
                file_options={"content-type": content_type, "upsert": "true"}
            )
        return supabase.storage.from_(bucket_name).get_public_url(destination_path)
    except Exception as e:
        print(f"Failed to upload file {file_path} to {bucket_name}: {e}")
        return None

def create_accident(event_time: str, camera_id: str, confidence: float, snapshot_path: str = None, clip_path: str = None) -> dict:
    """Inserts a new accident event into the 'accidents' table."""
    if not SUPABASE_ENABLED: return None
    try:
        data = {
            "event_time": event_time,
            "camera_id": camera_id,
            "confidence": float(confidence),
            "snapshot_path": snapshot_path,
            "clip_path": clip_path
        }
        response = supabase.table("accidents").insert(data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error creating accident: {e}")
        return None

def upsert_vehicle(plate_number: str) -> dict:
    """Checks if a vehicle exists; if not, inserts it into the 'vehicles' table."""
    if not SUPABASE_ENABLED: return None
    try:
        check = supabase.table("vehicles").select("*").eq("plate_number", plate_number).execute()
        if check.data and len(check.data) > 0:
            return check.data[0]
            
        response = supabase.table("vehicles").insert({"plate_number": plate_number}).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error upserting vehicle: {e}")
        return None

def link_vehicle_to_accident(accident_id: int, vehicle_id: int) -> dict:
    """Creates a link in the junction table 'accident_vehicles'."""
    if not SUPABASE_ENABLED: return None
    try:
        data = {"accident_id": accident_id, "vehicle_id": vehicle_id}
        response = supabase.table("accident_vehicles").insert(data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error linking vehicle to accident: {e}")
        return None

def log_detection(event_time: str, camera_id: str, confidence: float, snapshot_path: str = None, clip_path: str = None, plate_number: str = None) -> dict:
    """Logs the complete event data to the flat 'detections_log' table."""
    if not SUPABASE_ENABLED: return None
    try:
        data = {
            "event_time": event_time,
            "camera_id": camera_id,
            "confidence": float(confidence),
            "snapshot_path": snapshot_path,
            "clip_path": clip_path,
            "plate_number": plate_number
        }
        response = supabase.table("detections_log").insert(data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error logging detection: {e}")
        return None

def update_accident_clip(accident_id: int, clip_path: str, event_time: str, camera_id: str):
    """Updates an existing accident and log row with the generated video clip URL."""
    if not SUPABASE_ENABLED: return
    try:
        supabase.table("accidents").update({"clip_path": clip_path}).eq("id", accident_id).execute()
        supabase.table("detections_log").update({"clip_path": clip_path}).eq("event_time", event_time).eq("camera_id", camera_id).execute()
    except Exception as e:
        print(f"Error updating clip URL in Supabase: {e}")
