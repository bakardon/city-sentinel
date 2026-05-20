# City Sentinel Frontend

Next.js 14 (App Router) dashboard for the City Sentinel surveillance backend (FastAPI @ `http://127.0.0.1:8010`).

## Requirements

- Node.js 20+ and npm (install from https://nodejs.org if not present).

## First-time setup

```powershell
cd frontend
npm install
```

## Run the dev server

```powershell
npm run dev
```

Open http://127.0.0.1:3000. The backend URL defaults to `http://127.0.0.1:8010` and can be changed in the sidebar footer (value is saved to `localStorage`).

## Production build

```powershell
npm run build
npm run start
```

## Tech stack

- Next.js 14 App Router + TypeScript + React 18
- Tailwind CSS v3 + shadcn/ui (components live in `components/ui/`)
- TanStack Query v5 (data fetching, polling)
- Zustand (client state: backend URL)
- lucide-react icons, sonner toasts

## Structure

```
app/              # routes (one folder per sidebar item)
components/
  ui/             # shadcn primitives
  layout/         # sidebar, shell
  common/         # shared widgets (webcam, rtsp, event cards)
  workers/        # generic worker status + frame preview + controls
  testing/        # generic image/video upload panels
lib/
  api.ts          # fetch wrapper, uses serverUrl store
  endpoints.ts    # centralized path list
  types.ts        # DTOs
  hooks/          # React Query hooks
  stores/         # Zustand stores
  utils.ts        # cn() helper
```

## Status (Phase 1)

Fully built: Dashboard, Fire Detection, Fire Test. Other sidebar items render a stub explaining they're coming in Phase 2 but still show in the nav.
