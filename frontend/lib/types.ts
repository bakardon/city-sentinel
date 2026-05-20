export interface PersonRecord {
  id: string;
  name?: string | null;
  age?: number | null;
  address?: string | null;
  phone?: string | null;
  notes?: string | null;
  image_b64?: string | null;
  tags?: string[] | null;
}

export interface VehicleEvent {
  plate_number: string;
  status: "IN" | "OUT" | string;
  entry_time?: string | null;
  exit_time?: string | null;
  entry_camera_id?: string | null;
  exit_camera_id?: string | null;
  alert_flag?: boolean;
}

export interface MissingAlert {
  plate_number: string;
  entry_time?: string | null;
  alert_at?: string | null;
  missing_for_s?: number | null;
}

export interface VehiclesEventsResponse {
  events: VehicleEvent[];
  inside: VehicleEvent[];
  exited: VehicleEvent[];
  missing: MissingAlert[];
  threshold_s: number;
}

export interface AccidentRecord {
  id: number | string;
  event_time: string;
  camera_id?: string | null;
  confidence?: number | null;
  snapshot_path?: string | null;
  clip_path?: string | null;
}

export interface DetectionEvent {
  id: number | string;
  event_time: string;
  camera_id: string;
  camera_location?: string | null;
  alert_type: string;
  alert_level?: string | null;
  confidence?: number | null;
  description?: string | null;
  snapshot_url?: string | null;
  detections?: unknown;
}

export interface AccidentWorkerStatus {
  running: boolean;
  configured: boolean;
  camera_id: string;
  rtsp_url: string;
  last_error: string | null;
  last_frame_utc: string | null;
  last_alert_utc: string | null;
  last_supabase_snapshot_url: string | null;
  last_supabase_clip_url: string | null;
  alerts_seen: number;
}

export interface DetectionWorkerStatus {
  running: boolean;
  configured: boolean;
  rtsp_url: string;
  camera_id: string;
  camera_location: string;
  last_frame_utc: string | null;
  last_alert_utc: string | null;
  last_error: string | null;
  alerts_seen: number;
}

export interface WorkerFrame {
  image_b64?: string | null;
  ts?: number | null;
  camera_id?: string | null;
  stale?: boolean;
  error?: string | null;
  [key: string]: unknown;
}

export interface ModuleTestImageResult {
  ok: boolean;
  kind: string;
  label?: string | null;
  confidence?: number | null;
  fire?: boolean;
  artifact_url?: string | null;
  error?: string | null;
}

export interface ModuleTestVideoResult {
  ok: boolean;
  kind: string;
  label?: string | null;
  confidence?: number | null;
  fire?: boolean;
  artifact_snapshot_url?: string | null;
  artifact_clip_url?: string | null;
  error?: string | null;
}

export interface RecognitionMatch {
  person_id?: string | null;
  name?: string | null;
  similarity?: number | null;
  tags?: string[] | null;
  box?: { x1: number; y1: number; x2: number; y2: number } | null;
  image_b64?: string | null;
  tag_status?: string | null;
  camera_id?: string | null;
  location?: string | null;
  recognized_at?: string | null;
  event_ts?: number | null;
  info?: Record<string, unknown> | null;
}

export interface RecognitionPlate {
  text: string;
  confidence?: number | null;
  det_confidence?: number | null;
  box?: { x1: number; y1: number; x2: number; y2: number } | null;
}

export interface RecognizeRtspResponse {
  matches: RecognitionMatch[];
  image_b64?: string | null;
  frame_ts?: number | null;
  plates: RecognitionPlate[];
  stale?: boolean;
  error?: string | null;
}
