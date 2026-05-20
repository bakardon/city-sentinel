import os
import mimetypes
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

SUPABASE_URL = os.environ.get("SUPABASE_URL")
# Use service role key if available for backend operations, otherwise anon key
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in the .env file")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_file(bucket_name: str, file_path: str, destination_path: str) -> str:
    """
    Uploads a file to a Supabase storage bucket.
    
    Args:
        bucket_name (str): Name of the Supabase storage bucket (e.g., 'accidents').
        file_path (str): Local path to the file.
        destination_path (str): The path/name of the file in the bucket.
        
    Returns:
        str: The public URL of the uploaded file, or None if failed.
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found - {file_path}")
        return None
        
    content_type, _ = mimetypes.guess_type(file_path)
    if content_type is None:
        content_type = 'application/octet-stream'
        
    try:
        with open(file_path, 'rb') as f:
            response = supabase.storage.from_(bucket_name).upload(
                file=f,
                path=destination_path,
                file_options={"content-type": content_type, "upsert": "true"}
            )
        
        # Get public URL
        public_url = supabase.storage.from_(bucket_name).get_public_url(destination_path)
        return public_url
    except Exception as e:
        print(f"Failed to upload file {file_path}: {e}")
        return None

def create_accident(event_time: str, camera_id: str, confidence: float, snapshot_path: str = None, clip_path: str = None) -> dict:
    """
    Inserts a new accident record into the 'accidents' table.
    """
    try:
        data = {
            "event_time": event_time,
            "camera_id": camera_id,
            "confidence": float(confidence),
            "snapshot_path": snapshot_path,
            "clip_path": clip_path
        }
        response = supabase.table("accidents").insert(data).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error creating accident: {e}")
        return None

def upsert_vehicle(plate_number: str) -> dict:
    """
    Inserts a vehicle by plate_number or returns existing one.
    """
    try:
        # First check if vehicle exists
        check = supabase.table("vehicles").select("*").eq("plate_number", plate_number).execute()
        if check.data and len(check.data) > 0:
            return check.data[0]
            
        # If not, insert
        data = {"plate_number": plate_number}
        response = supabase.table("vehicles").insert(data).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error upserting vehicle: {e}")
        return None

def link_vehicle_to_accident(accident_id: int, vehicle_id: int) -> dict:
    """
    Links a vehicle to an accident in the 'accident_vehicles' junction table.
    """
    try:
        data = {
            "accident_id": accident_id,
            "vehicle_id": vehicle_id
        }
        response = supabase.table("accident_vehicles").insert(data).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error linking vehicle to accident: {e}")
        return None

def log_detection(event_time: str, camera_id: str, confidence: float, snapshot_path: str = None, clip_path: str = None, plate_number: str = None) -> dict:
    """
    Logs an accident detection along with any identified plate numbers to the 'detections_log' table.
    """
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
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error logging detection: {e}")
        return None

if __name__ == "__main__":
    # Test the connection
    print("Supabase client initialized successfully.")
