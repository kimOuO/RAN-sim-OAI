# RAN Digital Twin Implementation Summary

## Overview
Successfully implemented a complete RAN simulation platform with three integrated components:
- **RAN-sim Backend** (Ray Tracing + E2 Computation)
- **Omniverse Backend** (3D Visualization + Data Storage)
- **React Frontend** (Scene Configuration + Trajectory Drawing + Real-time Monitoring + Playback)

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    RAN-sim Frontend  :3002                   │
│  [ScenePage] → [DrawPage] → [SimPage] → [PlaybackPage]       │
└────────────────┬─────────────────────────────────────────────┘
                 │ HTTP API Calls (JSON)
        ┌────────▼────────────────────────────────────┐
        │      RAN-sim Backend  :8000                  │
        │  (Django + Sionna + AsyncIO Loop)            │
        │                                              │
        │  New Endpoints:                              │
        │  • SceneGateway/init → Omniverse            │
        │  • SimLoop/setup     → Configure UEs        │
        │  • SimLoop/start     → Launch loop          │
        │  • SimLoop/stop      → Halt + notify        │
        │  • SimLoop/status    → Get state            │
        │                                              │
        │  Internal Loop (500ms):                      │
        │  1. Advance UE positions                     │
        │  2. Compute E2 metrics (Sionna)             │
        │  3. Push to Omniverse (async HTTP)          │
        └──────┬───────────────────────────────────────┘
               │
               ▼
        ┌──────────────────────────────────────────┐
        │     Omniverse Backend  :8001              │
        │  (Django + PostgreSQL + WebSocket)        │
        │                                           │
        │  New Endpoints:                           │
        │  • SimSession/create → Session init      │
        │  • SimSession/end    → Session close     │
        │  • Playback/list     → Sessions list     │
        │  • Playback/read     → Replay frames     │
        │                                           │
        │  New DB Models:                           │
        │  • SimulationSession (with session_uuid) │
        │  • PositionHistory + session_uuid        │
        │  • SignalHistory + session_uuid          │
        └──────┬──────────────────────────────────┘
               │
               ├──▶ Kit :8080 (3D Engine)
               └──▶ PostgreSQL (Data Storage)
```

## Completed Implementation

### Phase 1: RAN-sim Backend (✅ Complete)

#### 1-A: SimLoop Service (sim_loop_service.py)
- **Core Logic**: Manages continuous simulation loop with 500ms ticks
- **Key Features**:
  - UE trajectory management (waypoints + speed interpolation)
  - Linear 3D interpolation between waypoints
  - AsyncIO-driven non-blocking loop
  - HTTP integration with Omniverse
  - Session state management

- **Methods**:
  - `setup(session_uuid, scene_id, ues)` - Configure UE trajectories
  - `start()` - Launch asyncio loop
  - `stop()` - Halt loop and notify Omniverse
  - `status()` - Return current state
  - `_tick()` - Main loop execution (called every 500ms)
  - `_advance_ue()` - Progress UE along trajectory
  - `_compute_position_at_distance()` - Calculate position via interpolation
  - `_post_to_omniverse_move()` - Send UE position updates
  - `_post_to_omniverse_ingest()` - Send signal data with session_uuid

#### 1-B: SceneGateway Actor (scene_gateway_actor.py)
- **Purpose**: Bridge between frontend and RAN-sim/Omniverse
- **Endpoint**: `POST /api/v0.1/RanpSim/Scene/SceneGateway/init`
- **Flow**:
  1. Receive scene config from frontend
  2. Initialize Sionna scene via ConfigManager
  3. Create SimSession in Omniverse
  4. Store session_uuid in SimLoopService
  5. Return session_uuid to frontend

#### 1-C: SimLoop Actors (sim_loop_actor.py)
- **Endpoints**:
  - `POST /api/v0.1/RanpSim/RanSignal/SimLoop/setup` - Configure UE trajectories
  - `POST /api/v0.1/RanpSim/RanSignal/SimLoop/start` - Start simulation
  - `POST /api/v0.1/RanpSim/RanSignal/SimLoop/stop` - Stop simulation
  - `POST /api/v0.1/RanpSim/RanSignal/SimLoop/status` - Query state

#### 1-D/E: Serializers, URLs, Environment
- **New Serializers**: SimLoopSetupRequestSerializer, SimLoopStartResponseSerializer, etc.
- **New URLs**: 5 new API endpoints added to api/urls.py
- **Environment**: OMNIVERSE_BACKEND_URL + SIM_LOOP_TICK_MS configured

### Phase 2: Omniverse Backend (✅ Complete)

#### 2-A: SimulationSession Model (simulation_session.py)
- **Fields**:
  - session_uuid (unique, indexed)
  - scene_id (indexed with created_at)
  - status (running/ended)
  - created_at / ended_at
  - metadata_json (gnb_count, ue_count, etc.)

#### 2-B: SimSessionController (sim_session_actor.py)
- **Endpoints**:
  - `POST /api/v0.1/RAN/SimSession/SimSessionController/create` - Create session
  - `POST /api/v0.1/RAN/SimSession/SimSessionController/end` - End session

#### 2-C: PlaybackController (playback_actor.py)
- **Endpoints**:
  - `POST /api/v0.1/RAN/SimSession/PlaybackController/list` - List all sessions
  - `POST /api/v0.1/RAN/SimSession/PlaybackController/read` - Replay frames for a session
- **Features**:
  - Merges PositionHistory + SignalHistory by timestamp
  - Returns ordered frames with UE status per frame

#### 2-D: DB Model Updates
- **PositionHistory**: Added `session_uuid` field + index
- **SignalHistory**: Added `session_uuid` field + index
- **IngestBusinessService**: Updated `ingest_signals()` to accept/store session_uuid

### Phase 3: RAN-sim Frontend (✅ Complete)

#### Technology Stack
- **Framework**: React 18 + Vite
- **Routing**: React Router v6
- **Charts**: Recharts (for signal visualization)
- **HTTP**: Axios
- **Port**: 3002 (dev), 3000 (prod)

#### Pages

**1. ScenePage (/) — Scene Selection**
- Displays scene_config.json metadata
- Shows building count, gNB count, UE count
- "Initialize Scene" button:
  - Calls SceneGateway/init
  - Stores session_uuid in localStorage
  - Navigates to DrawPage

**2. DrawPage (/draw) — Trajectory Editor**
- SVG canvas showing:
  - Buildings (gray boxes)
  - gNBs (colored triangles)
  - UE trajectories (drawn lines with waypoints)
- Features:
  - Click to add waypoints
  - Speed slider per UE
  - Clear trajectory button
  - Coordinate system: world_x = (canvas_x / width) * scene_width - offset
- "Setup & Continue" button:
  - Calls SimLoop/setup with UE trajectories
  - Navigates to SimPage

**3. SimPage (/sim) — Real-time Simulation Monitor**
- Left: Recharts line chart showing RSRP trends
- Right: VNC iframe (Kit 3D visualization)
- Bottom: Signal status table (UE name, RSRP, SINR)
- Controls:
  - Start Simulation (calls SimLoop/start)
  - Stop Simulation (calls SimLoop/stop → navigates to /playback)
- WebSocket listener:
  - Connects to ws://localhost:8001/api/v0.1/RAN/UE/live
  - Updates chart and table in real-time

**4. PlaybackPage (/playback) — Session Replay**
- Left: Session list (filtered by status)
  - Shows session_uuid, scene_id, created_at, duration
- Right: Playback viewer
  - Load session → calls Playback/read
  - Merges frames by timestamp
  - Play/pause controls
  - Timeline slider
  - Frame-by-frame data table (UE name, position, RSRP, SINR)

#### API Client (api.js)
```javascript
api.initScene(sceneConfig)      // POST /Scene/SceneGateway/init
api.setupUE(ueTrajectories)     // POST /SimLoop/setup
api.startSim()                  // POST /SimLoop/start
api.stopSim()                   // POST /SimLoop/stop
api.getStatus()                 // POST /SimLoop/status
```

#### Configuration (config.js)
- `API_BASE_URL` = http://localhost:8000 (or VITE_API_BASE_URL env)
- `OMNIVERSE_URL` = http://localhost:8001 (or VITE_OMNIVERSE_URL env)
- `VNC_URL` = http://localhost:6080/vnc.html (or VITE_VNC_URL env)
- `WS_URL` = ws://localhost:8001/api/v0.1/RAN/UE/live (or VITE_WS_URL env)

## Data Flow

### 1. Scene Initialization
```
Frontend → SceneGateway/init (scene config)
  └─→ RAN-sim: ConfigManager.push_scene() [Sionna rebuild]
      └─→ Omniverse: SimSession/create + SceneIngestor/create
          └─→ Return session_uuid
```

### 2. Trajectory Setup
```
Frontend → SimLoop/setup (UE trajectories)
  └─→ RAN-sim: Store waypoints + speed in SimLoopService
```

### 3. Simulation Execution
```
Frontend → SimLoop/start
  └─→ RAN-sim: Launch asyncio loop (every 500ms)
      Tick 1, 2, 3, ...
        ├─→ Advance UE positions (interpolation)
        ├─→ SionnaBusinessService.compute()
        ├─→ POST Omniverse/UE/UEController/move (per UE)
        └─→ POST Omniverse/Ingest/SignalIngestor/create (all signals + session_uuid)
            └─→ Omniverse: Store in SignalHistory + PositionHistory (both tagged with session_uuid)
```

### 4. Real-time Monitoring
```
Frontend: Subscribe WebSocket ws://localhost:8001/api/v0.1/RAN/UE/live
  ←─ Omniverse pushes {type: "ue_update", ues: [...]}
    └─→ Update chart + signal table
```

### 5. Playback
```
Frontend → Playback/list
  ←─ Return [{session_uuid, scene_id, created_at, ended_at, duration_ms}, ...]

Frontend → Playback/read (session_uuid)
  ←─ Omniverse: Query SignalHistory + PositionHistory where session_uuid = ?
      Merge by timestamp → {frames: [{ts, ues: [{name, x, y, z, rsrp_dbm, sinr_db}]}]}
    └─→ Frontend: Render timeline player
```

## Key Implementation Details

### UE Position Interpolation
- Linear 3D interpolation between consecutive waypoints
- `progress_in_segment` tracks position within current segment [0, 1)
- Total distance pre-calculated from waypoints
- Supports looping (modulo wrap-around)

### Session Management
- Each simulation batch gets a UUID (session_uuid)
- All data (signals, positions) tagged with session_uuid
- SimSession DB tracks start/end times
- Enables multi-session storage and selective replay

### AsyncIO Loop Design
- Non-blocking tick execution (500ms interval)
- Calls SionnaBusinessService.compute() synchronously (GPU-bound)
- HTTP requests to Omniverse run in thread pool via `loop.run_in_executor()`
- Loop continues even if individual requests fail

### Frontend Build
```bash
npm install
npm run dev      # Port 3002
npm run build    # Production build (dist/)
```

## Deployment Checklist

- [x] RAN-sim backend: Phase 1 complete (SimLoop, SceneGateway, SimLoop actors)
- [x] Omniverse backend: Phase 2 complete (SimSession model, PlaybackController)
- [x] Frontend: Phase 3 complete (4 pages, real-time WebSocket, playback)
- [ ] Create Django migrations for new DB models (PositionHistory, SignalHistory, SimulationSession)
- [ ] Run: `python manage.py makemigrations && python manage.py migrate`
- [ ] Configure environment variables (.env files)
- [ ] Deploy frontend with `npm run build` + serve dist/
- [ ] Start all services (RAN-sim, Omniverse, Kit)
- [ ] Verify connectivity (health checks)

## Testing Workflow

1. **Frontend**: Navigate to http://localhost:3002
2. **ScenePage**: Click "Initialize Scene" (creates session in Omniverse)
3. **DrawPage**: Select UE, click canvas to add waypoints, set speed
4. **SimPage**: Click "Start Simulation" (loop launches)
5. **Monitor**: Watch RSRP chart + VNC viewer
6. **Stop**: Click "Stop Simulation" (navigates to Playback)
7. **Playback**: Select session, play/pause timeline, inspect frames

## Files Changed/Created

### RAN-sim Backend
- `main/apps/ran_signal/services/business/sim_loop_service.py` (NEW)
- `main/apps/ran_signal/actors/scene_gateway_actor.py` (NEW)
- `main/apps/ran_signal/actors/sim_loop_actor.py` (NEW)
- `main/apps/ran_signal/serializers/config_serializers.py` (MODIFIED - added SceneGatewayInit*)
- `main/apps/ran_signal/serializers/sim_loop_serializers.py` (NEW)
- `main/apps/ran_signal/api/urls.py` (MODIFIED - added 5 new endpoints)
- `.env.sample` (MODIFIED - added OMNIVERSE_BACKEND_URL, SIM_LOOP_TICK_MS)

### Omniverse Backend
- `main/apps/ran/models/simulation_session.py` (NEW)
- `main/apps/ran/models/position_history.py` (MODIFIED - added session_uuid)
- `main/apps/ran/models/signal_history.py` (MODIFIED - added session_uuid)
- `main/apps/ran/models/__init__.py` (MODIFIED - added SimulationSession import)
- `main/apps/ran/actors/sim_session_actor.py` (NEW)
- `main/apps/ran/actors/playback_actor.py` (NEW)
- `main/apps/ran/api/urls.py` (MODIFIED - added 4 new endpoints)
- `main/apps/ran/serializers/ingest_serializers.py` (MODIFIED - added session_uuid handling)
- `main/apps/ran/services/business/ingest_operations.py` (MODIFIED - added session_uuid parameter)
- `main/apps/ran/actors/ingest_actor.py` (MODIFIED - pass session_uuid to ingest_signals)

### Frontend (NEW)
- `frontend/` (complete React+Vite application)
  - `src/App.jsx` (routing)
  - `src/config.js` (env config)
  - `src/api.js` (HTTP client)
  - `src/pages/ScenePage.jsx` + `.css`
  - `src/pages/DrawPage.jsx` + `.css`
  - `src/pages/SimPage.jsx` + `.css`
  - `src/pages/PlaybackPage.jsx` + `.css`
  - `src/scene_config.json` (copied from Omniverse)
  - `.env.example` (environment template)
  - `package.json` (dependencies)

## Known Limitations

1. **VNC Frame Rate**: Limited by Kit's WS push rate (typically 2-5 Hz)
2. **Chart Buffer**: PlaybackPage keeps last 100 points to prevent memory bloat
3. **Position History**: Optional in playback (merged from PositionHistory table, may be sparse)
4. **Error Recovery**: Non-blocking failures logged but simulation continues
5. **Multi-user**: Sessions are independent; no locking or collision detection

## Future Enhancements

- 3D visualization in frontend (Three.js/Babylon.js) instead of VNC
- Multi-session simultaneous playback
- Export playback to CSV/video
- Real-time KPI metrics (handover count, coverage %, throughput)
- User authentication + role-based access
- Database backups + archival for old sessions
