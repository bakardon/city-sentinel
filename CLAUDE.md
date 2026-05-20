# CLAUDE.md — City Sentinel: Project Memory

> This file is the single source of truth for any AI agent working on this codebase.
> Read it in full before touching anything. Update it whenever you make significant changes.

---

## 1. Project Overview

**City Sentinel** is a Final Year Project (FYP) submitted for a Bachelor of Science in Computer Science (Academic Year 2025–2026).

- **Full title:** City Sentinel: An Intelligent Data-Engineering Framework for Smart-City Threat Detection
- **University:** Department of Computer Science, Faculty of Computing and Information Technology
- **Supervisor:** Dr. Masroor Hussain | **Co-Supervisor:** Dr. Farhan Khan
- **Team:**
  | Name | Reg No |
  |------|--------|
  | Syed Hanan Shabir | 2022565 |
  | Abu Bakar Bin Mazhar | 2022039 |
  | Muhammad Aqeeb Ahmad | 2022349 |

**What it does:** A production-grade smart-city surveillance platform that unifies six AI detection modules under one FastAPI backend + Next.js dashboard:
1. **Face recognition** — enrolment, embedding match, suspect tracking over RTSP
2. **ANPR** — YOLO plate localization + EasyOCR, Pakistan-style plate formatting, vehicle entry/exit logging and "still inside too long" alerts
3. **Fire & smoke detection** — RTSP worker + webcam/image test API
4. **Knife / armed threat detection** — same pattern
5. **Weapon detection** — same pattern
6. **Violence / fighting detection** — same pattern
7. **Vehicle accident detection** — richer pipeline; includes vehicle/face guards

All events are persisted to **Supabase** (PostgreSQL). The system gracefully degrades to in-memory fallback if Supabase is unavailable.

---

## 2. Tech Stack

| Layer | Technology |
|-------|------------|
| Backend language | Python 3.10+ |
| Backend framework | FastAPI + Uvicorn |
| Vision / inference | Ultralytics YOLOv8, InsightFace (`buffalo_l`), EasyOCR, ONNX Runtime GPU |
| Video capture | OpenCV + FFmpeg (RTSP streams) |
| Database / storage | Supabase (PostgreSQL + Storage buckets) |
| Frontend framework | Next.js 14 (App Router) |
| Frontend language | TypeScript + React 18 |
| Frontend styling | Tailwind CSS + Radix UI (shadcn-style) |
| Frontend state | TanStack Query + Zustand |
| Package manager (FE) | npm |

**`requirements.txt` (pinned):**
```
fastapi==0.128.4
uvicorn==0.40.0
ultralytics==8.4.12
opencv-python==4.9.0.80
insightface==0.7.3
numpy==1.26.4
onnxruntime-gpu==1.19.2
supabase==2.27.3
easyocr==1.7.2
```

---

## 3. Directory Structure

```
D:\hanan_fyp\
│
├── CLAUDE.md                          ← this file
├── requirements.txt
├── .env  (gitignored)                 ← Supabase + runtime config
├── supabase.env  (gitignored)         ← alternative env file
├── deployment_diagram.drawio
│
├── app\                               ← FastAPI backend (main codebase)
│   ├── main.py                        ← ALL routes, RtspStream, worker lifecycle
│   ├── vision.py                      ← VisionService: YOLO + InsightFace
│   ├── supabase_client.py             ← get_supabase(), get_supabase_admin()
│   ├── realtime_inference.py          ← YOLO loader (TensorRT / ONNX / ultralytics)
│   ├── accident_service.py            ← AccidentDetectionService (RTSP worker)
│   ├── accident_testing.py            ← Accident test pipeline (image/video upload)
│   ├── fire_service.py                ← FireDetectionService
│   ├── fire_testing.py
│   ├── knife_service.py               ← KnifeDetectionService
│   ├── knife_testing.py
│   ├── weapon_service.py              ← WeaponDetectionService
│   ├── weapon_testing.py
│   ├── violence_service.py            ← ViolenceDetectionService
│   ├── violence_testing.py
│   ├── anpr.py                        ← ANPR helpers (standalone)
│   └── plate_pipeline.py             ← Standalone RTSP plate pipeline
│
├── accident_detection\
│   ├── src\  config.py, utils.py, database.py, live_stream.py, predict_image.py, test_video.py
│   └── scripts\  (train, predict, verify, supabase helpers)
├── fire_detection\       src\config.py, src\utils.py, train.py, prepare_dataset.py, dataset.yaml
├── knife_detection\      (same shape as fire_detection)
├── weapon_detection\     (same shape)
├── violence_detection\   (same shape)
│
├── tools\
│   └── export_tensorrt_engines.py     ← batch export TRT engines from project configs
│
├── frontend\                          ← Next.js 14 dashboard
│   ├── app\                           ← App Router pages
│   │   ├── page.tsx                   ← home / redirect
│   │   ├── dashboard\
│   │   ├── persons\
│   │   ├── tags\
│   │   ├── profiles\
│   │   ├── fire-detection\
│   │   ├── armed-detection\
│   │   ├── violence-detection\
│   │   ├── accident-testing\
│   │   ├── fire-test\
│   │   ├── knife-test\
│   │   ├── weapon-test\
│   │   └── violence-test\
│   ├── components\
│   │   ├── ui\                        ← Radix/shadcn primitives
│   │   ├── layout\                    ← Sidebar, Topbar, shell
│   │   ├── dashboard\                 ← live feeds: accidents, vehicles, missing alerts
│   │   ├── workers\                   ← generic WorkerControl + frame preview
│   │   ├── testing\                   ← DetectionModulePage, TestModulePage
│   │   ├── common\
│   │   ├── modules\
│   │   └── persons\                   ← enrol, list, delete persons
│   └── lib\
│       ├── api.ts                     ← fetch wrapper using configurable serverUrl
│       ├── endpoints.ts               ← all backend route strings
│       ├── types.ts                   ← shared TypeScript interfaces
│       ├── hooks\
│       ├── stores\                    ← Zustand stores (serverUrl, etc.)
│       ├── providers.tsx
│       └── utils.ts
│
├── Report\
│   ├── FYP_Report.md / .docx          ← full academic write-up
│   ├── md_to_docx.py                  ← report tooling (not runtime)
│   └── *.xml                          ← Draw.io diagrams (architecture, ER, UML, etc.)
│
└── setup_*.sql                        ← Supabase table creation scripts
    ├── setup_fire_events_table.sql
    ├── setup_knife_events_table.sql
    ├── setup_plate_detections_table.sql
    ├── setup_vehicle_table.sql
    ├── setup_violence_events_table.sql
    └── setup_weapon_events_table.sql
```

**Gitignored (not in repo, must be provided on fresh clone):**
- `.env`, `supabase.env`
- `venv` / `.venv`
- Model weights: `*.pt`, `*.onnx`, `*.engine`
- Datasets and training outputs (`runs/`, each `*_detection/data/`, `*_detection/runs/`)
- Video/image outputs

---

## 4. Backend Architecture (`app/`)

### Running the backend
```bash
cd D:\hanan_fyp
uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```
Frontend default API base: `http://127.0.0.1:8010`

### `main.py` — the monolith
Everything routes through here. Key responsibilities:
- **`RtspStream`** class: background thread that captures RTSP frames, runs face recognition + ANPR every N frames, tracks people and plates across frames
- **`recognize_from_image()`**: one-shot image face match
- Vehicle entry/exit logic via `IN`/`OUT` events written to Supabase `vehicle_records` table
- "Missing vehicle" background job (alert if `INSIDE` time exceeds threshold)
- Registers and starts/stops detection workers (accident, fire, knife, weapon, violence)

### `vision.py` — `VisionService`
- Loads YOLO (for person/vehicle bounding boxes) and InsightFace `buffalo_l`
- `detect_faces()`: returns face bounding boxes + 512-dim embeddings
- `detect_objects()`: returns YOLO detections (persons, vehicles)
- `match_embedding()`: cosine similarity against in-memory people cache from Supabase

### `supabase_client.py`
- Reads from `.env`, `supabase.env`, or path in `SUPABASE_ENV_FILE` env var
- `get_supabase()`: general client (tries service_role → service_key → generic key → anon)
- `get_supabase_admin()`: admin client (service role / service key)
- Graceful: returns `None` if no env is found — app continues with in-memory fallback

### `realtime_inference.py`
- `get_yolo_runtime(model_path)`: returns TensorRT engine if `.engine` file exists, else ONNX if `.onnx` exists, else falls back to Ultralytics `.pt`
- `predict_yolo(model, frame)`: normalized wrapper around all three backends

### Detection Services (pattern repeated for all five domains)
```
{module}_service.py  → {Module}DetectionService
  - __init__: loads model via realtime_inference
  - start() / stop(): manage background RTSP capture thread
  - _worker_loop(): OpenCV capture → predict_yolo → parse detections → log to Supabase
  - get_status(): returns running state + recent stats
  - get_latest_frame(): returns base64-encoded annotated frame for preview

{module}_testing.py  → used by /test/image and /test/video routes
  - Loads module's src/config.py + src/utils.py
  - Runs inference on uploaded file, saves annotated output
  - Returns artifact URLs + detection metadata
```

### `plate_pipeline.py` / `anpr.py`
- **Warning:** `plate_pipeline.py` currently has a hardcoded default RTSP URL with credentials. Rotate and move to env before any deployment.
- ANPR uses YOLO for plate bounding box → EasyOCR for text → regex for Pakistan plate format

---

## 5. Database Schema

### Supabase tables (live schema — use SQL files + main.py as truth)

**`persons`** (no SQL file; managed via API)
```sql
id          UUID PRIMARY KEY
name        TEXT
embedding   FLOAT[]        -- 512-dim InsightFace vector
image_b64   TEXT
age         TEXT
phone       TEXT
address     TEXT
notes       TEXT
tags        TEXT[]
created_at  TIMESTAMPTZ
```

**`person_events`** (no SQL file; managed via API)
```sql
id          UUID PRIMARY KEY
person_id   UUID REFERENCES persons(id)
event_type  TEXT
camera_id   TEXT
location    TEXT
timestamp   TIMESTAMPTZ
similarity  FLOAT
```

**`vehicle_records`** (see `setup_vehicle_table.sql`)
```sql
id                UUID / bigint PK
plate_number      TEXT
status            TEXT   -- 'IN' or 'OUT' (code) — SQL comment says INSIDE/EXITED (mismatch, see Known Issues)
entry_time        TIMESTAMPTZ
exit_time         TIMESTAMPTZ
entry_camera_id   TEXT
exit_camera_id    TEXT
alert_flag        BOOLEAN
created_at        TIMESTAMPTZ
```

**`fire_events` / `knife_events` / `weapon_events` / `violence_events`** (see respective `setup_*.sql`)
```sql
id               bigint IDENTITY PK
event_time       TIMESTAMPTZ
camera_id        TEXT
camera_location  TEXT
alert_type       TEXT
alert_level      TEXT
confidence       FLOAT
description      TEXT
snapshot_url     TEXT    -- Supabase storage URL
detections       JSONB
```
All four have RLS enabled with a public SELECT policy.

**`plate_detections`** (`setup_plate_detections_table.sql`) — raw ANPR log

**`accidents`** (no SQL file; accident_detection/src/database.py + main.py queries)
```sql
id               UUID
event_time       TIMESTAMPTZ
camera_id        TEXT
confidence       FLOAT
snapshot_path    TEXT
clip_path        TEXT
```
The accident pipeline also references `vehicles`, `accident_vehicles`, `detections_log` — verify existence in Supabase before use.

**Configurable table names via env:**
```
FIRE_EVENTS_TABLE      (default: fire_events)
KNIFE_EVENTS_TABLE     (default: knife_events)
WEAPON_EVENTS_TABLE    (default: weapon_events)
VIOLENCE_EVENTS_TABLE  (default: violence_events)
VEHICLE_LOGS_TABLE     (default: vehicle_records)
```

---

## 6. API Endpoints (all in `app/main.py`)

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |

### Persons / Face Recognition
| Method | Path | Description |
|--------|------|-------------|
| GET | `/persons` | List all enrolled persons |
| DELETE | `/persons/{person_id}` | Delete person + their events (uses admin client) |
| POST | `/persons/{person_id}/tags` | Update tags array |
| POST | `/profiles` | Enrol a face — multipart: image + metadata |
| POST | `/recognize/person` | Run face recognition on uploaded image |
| POST | `/recognize/rtsp` | Poll RTSP stream for face/plate matches |

### Vehicles / ANPR
| Method | Path | Description |
|--------|------|-------------|
| GET | `/vehicles/events` | Full vehicle log (IN/OUT/INSIDE/EXITED/MISSING) |
| GET | `/alerts/missing` | Vehicles inside longer than threshold |

### Accidents
| Method | Path | Description |
|--------|------|-------------|
| GET | `/accidents` | List accident events |
| GET/POST | `/accident-worker/status` | Get worker status |
| POST | `/accident-worker/start` | Start RTSP worker |
| POST | `/accident-worker/stop` | Stop RTSP worker |
| POST | `/accident-test/image` | Upload image → accident inference |
| POST | `/accident-test/video` | Upload video → accident inference |
| GET | `/accident-test/artifacts/{rel_path}` | Serve test output files |

### Fire
| Method | Path | Description |
|--------|------|-------------|
| GET | `/fire-events` | List fire events |
| GET/POST | `/fire-worker/status`, `/fire-worker/start`, `/fire-worker/stop` | Worker lifecycle |
| GET | `/fire-worker/frame` | Latest annotated frame (base64 JSON) |
| POST | `/fire/predict/image` | Webcam/image inference + optional Supabase log |
| POST | `/fire-test/image`, `/fire-test/video` | Batch test uploads |
| GET | `/fire-test/artifacts/{rel_path}` | Serve test output |

### Knife / Weapon / Violence (same pattern as Fire)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/{module}-events` | List events |
| GET/POST | `/{module}-worker/status`, `start`, `stop` | Worker lifecycle |
| GET | `/{module}-worker/frame` | Latest frame |
| POST | `/{module}/predict/image` | Webcam inference |
| POST | `/{module}-test/image`, `/{module}-test/video` | Batch test |
| GET | `/{module}-test/artifacts/{rel_path}` | Serve artifacts |

`{module}` = `knife`, `weapon`, `violence`

---

## 7. Environment Variables

Place in `D:\hanan_fyp\.env` (or `supabase.env`, or set `SUPABASE_ENV_FILE`).

### Supabase
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PROJECT_URL=...          # alternative key name
SUPABASE_KEY=...                  # anon key
SUPABASE_SERVICE_ROLE_KEY=...     # service role (for admin ops)
```

### Vision / Models
```
YOLO_MODEL_PATH=path/to/yolo.pt         # person/vehicle detector
PLATE_MODEL_PATH=path/to/plate.pt       # ANPR plate locator
FACE_MATCH_THRESHOLD=0.45               # cosine sim threshold
PEOPLE_CACHE_TTL_S=60                   # how often to refresh persons from Supabase
VISION_USE_CUDA=true
PLATE_USE_CUDA=true
PLATE_OCR_USE_GPU=true
FORCE_GPU=true
```

### Vehicle tracking
```
VEHICLE_LOGS_TABLE=vehicle_records
ENTRY_CAMERA_ID=cam_entry
EXIT_CAMERA_ID=cam_exit
MISSING_VEHICLE_THRESHOLD_S=3600        # 1 hour before "missing" alert
MISSING_VEHICLE_ALERT_TTL_S=300
ALERT_JOB_INTERVAL_S=60
VEHICLE_EVENT_MIN_INTERVAL_S=30
```

### Per-worker (repeat pattern for each module)
```
FIRE_RTSP_URL=rtsp://...
FIRE_CAMERA_ID=cam_fire_01
FIRE_WORKER_AUTOSTART=false
FIRE_DEVICE=cuda:0
FIRE_EVENTS_TABLE=fire_events

KNIFE_RTSP_URL=...
KNIFE_CAMERA_ID=...
KNIFE_WORKER_AUTOSTART=false
KNIFE_DEVICE=cuda:0
KNIFE_EVENTS_TABLE=knife_events

WEAPON_RTSP_URL=...
WEAPON_CAMERA_ID=...
WEAPON_WORKER_AUTOSTART=false
WEAPON_DEVICE=cuda:0
WEAPON_EVENTS_TABLE=weapon_events

VIOLENCE_RTSP_URL=...
VIOLENCE_CAMERA_ID=...
VIOLENCE_WORKER_AUTOSTART=false
VIOLENCE_DEVICE=cuda:0
VIOLENCE_EVENTS_TABLE=violence_events

ACCIDENT_RTSP_URL=...
ACCIDENT_CAMERA_ID=...
ACCIDENT_WORKER_AUTOSTART=false
ACCIDENT_DEVICE=cuda:0
ACCIDENT_TEST_VEHICLE_MIN_CONF=0.4
```

### RTSP tuning
```
RTSP_TRANSPORT=tcp
RTSP_TIMEOUT_US=5000000
RTSP_MAX_RETRIES=5
TRACKER_TTL_MS=3000
```

---

## 8. Frontend Details

### Running the frontend
```bash
cd D:\hanan_fyp\frontend
npm install
npm run dev       # dev server on http://localhost:3000
```

### Configuring backend URL
The frontend stores the backend URL in Zustand. Default is `http://127.0.0.1:8010`. It can be changed at runtime from the settings/header UI without a rebuild.

### Key files
- `lib/endpoints.ts` — all API route strings (single source of truth for FE–BE contract)
- `lib/api.ts` — `apiFetch(endpoint, options)` wrapper that reads `serverUrl` from Zustand
- `lib/types.ts` — shared TypeScript interfaces (Person, FireEvent, VehicleRecord, etc.)
- `lib/stores/` — Zustand stores
- `lib/hooks/` — TanStack Query hooks per domain

### Pages and status
| Route | Status |
|-------|--------|
| `/dashboard` | Built — live feeds for accidents, vehicles, missing alerts |
| `/persons` | Built — list, enrol, delete persons |
| `/profiles` | Built — enrolment form |
| `/tags` | Built — tag management |
| `/fire-detection` | Built — RTSP worker control + live frame |
| `/armed-detection` | Built — knife/weapon worker |
| `/violence-detection` | Built — violence worker |
| `/accident-testing` | Built — upload test UI |
| `/fire-test` | Built — fire test UI |
| `/knife-test` | Built — knife test UI |
| `/weapon-test` | Built — weapon test UI |
| `/violence-test` | Built — violence test UI |

> Note: `frontend/README.md` says only Dashboard + Fire are built — **this is outdated**. All the above pages exist and are implemented.

---

## 9. Detection Module Structure (per-module)

Each detection domain follows this identical pattern:

```
{module}_detection/
├── dataset.yaml                   # YOLO dataset config
├── prepare_dataset.py             # dataset prep script
├── train.py                       # training entry point
└── src/
    ├── config.py                  # MODEL_PATH, CONFIDENCE_THRESHOLD, CLASS_NAMES, etc.
    └── utils.py                   # parse_detections(), is_positive_detection(), draw_boxes()
```

`accident_detection` additionally has:
```
src/
├── database.py                    # Supabase accident schema helpers
└── live_stream.py                 # standalone RTSP accident stream
scripts/
├── train_*.sh
├── predict_image.py
├── predict_video.py
├── verify_dataset.py
└── supabase_helpers.py
```

Model weights are gitignored. On a fresh setup, each module's `config.py` tells you the expected weight filename/path.

---

## 10. Known Issues & Inconsistencies

1. **`vehicle_records` status mismatch:** The SQL file's comments say `INSIDE`/`EXITED` but `main.py` inserts `IN`/`OUT`. Verify your actual Supabase data and pick one convention — update both SQL and `main.py` to match.

2. **Accident pipeline extra tables:** `accident_detection/src/database.py` references `vehicles`, `accident_vehicles`, `detections_log` tables. There are no corresponding `setup_*.sql` files in the repo. These may need to be created manually in Supabase.

3. **Hardcoded RTSP credentials in `plate_pipeline.py`:** The default RTSP URL has credentials embedded in source. Must be moved to env before any production use.

4. **`FYP_Report.md` Appendix B schema** uses UUID-based DDL — the live Supabase scripts use `bigint IDENTITY`. Do not use the report appendix as schema reference; use the `.sql` files and `main.py`.

5. **No Docker Compose** in the repo. Deployment is manual: Python venv for backend, `npm` for frontend, Supabase cloud for DB.

6. **Model weights missing on fresh clone** — every `*_detection/src/config.py` specifies expected paths. You must provide `.pt`, `.onnx`, or `.engine` files out-of-band.

---

## 11. Report / Documentation Files

All in `Report/`:
- `FYP_Report.md` / `FYP_Report.docx` — full academic write-up (1900+ lines)
- `md_to_docx.py` — converts MD to DOCX (uses `python-docx`); run separately, not part of API
- Draw.io XML diagrams:
  - `Architecture_Backend.xml`
  - `Architecture_Frontend.xml`
  - `Architecture_HighLevel.xml`
  - `ClassDiagram_CoreDomain.xml`
  - `ER_Diagram_CitySentinel.xml`
  - `Flowchart_ThreatDetection.xml`
  - `SequenceDiagram_PersonEnrolment.xml`
  - `SequenceDiagram_RTSPRecognition.xml`
  - `UseCase_Citysentinel.xml`
  - `UseCase_FaceRecognition.xml`

All XML files use **45px bold headers** and **40px body text** — maintain this standard if editing.

`deployment_diagram.drawio` is in the root.

---

## 12. How to Run (Full Stack)

```bash
# 1. Clone & set up Python env
cd D:\hanan_fyp
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 2. Create .env with Supabase credentials + model paths (see Section 7)

# 3. Place model weights in paths matching each module's config.py

# 4. Start backend
uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload

# 5. Start frontend (separate terminal)
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

---

## 13. Current Development State

As of **April 2026**, the project is **complete for FYP submission**. The codebase is feature-complete:
- All six detection modules implemented (RTSP workers + test APIs)
- Full Next.js dashboard with all pages
- Supabase integration with in-memory fallback
- Training pipelines per module
- TensorRT export tooling
- Full academic report written and formatted

**What may still need attention:**
- Resolving the `vehicle_records` status value mismatch (Issue #1 above)
- Creating missing accident-pipeline Supabase tables (Issue #2 above)
- Removing hardcoded credentials from `plate_pipeline.py` (Issue #3 above)
- Keeping `frontend/README.md` up to date
