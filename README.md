# SkySentinel

SkySentinel is an integrated drone cybersecurity monitoring and GPS spoofing detection platform built with React, TypeScript, Leaflet, FastAPI, scikit-learn, SQLAlchemy, Alembic, and PostgreSQL (Neon).

All flight trajectories, cyberattack scenarios, network threat packets, and recovery actions in this application are simulated for cybersecurity research, testing, and academic demonstration.

---

## Technology Stack

- **Frontend**: React 19, TypeScript, Vite, Leaflet
- **Backend**: FastAPI, Pydantic, Uvicorn, Cryptography (AES-256-GCM)
- **Machine Learning**: scikit-learn (`RandomForestClassifier` with flight-level holdout evaluation)
- **Database & Migrations**: PostgreSQL (Neon), SQLAlchemy 2.0, Alembic
- **Testing & CI**: pytest, Playwright, Docker, GitHub Actions

---

## Core Modules

1. **Security Dashboard & Flight Watch**
   - Live fleet metrics: total registered drones, active drones, normal drones, drones under GPS spoofing attacks, detected cyberattacks, active critical/high alerts, and overall network and GPS security status.
   - Real-time attack feed, latest drone telemetry stream, and interactive flight-watch controls.

2. **Drone Management**
   - Register new drones with unique IDs/codes (`DRN-001`, etc.), airframe models, battery, altitude, and base coordinates.
   - View, search, filter, edit, and decommission registered drones, and inspect battery, speed, altitude, coordinates, GPS connectivity, and communication status.

3. **Live GPS Tracking & Flight Path Deviation Detection**
   - Multi-drone simultaneous trajectory map comparing planned flight corridors against reported GPS coordinates.
   - Great-circle (Haversine) deviation calculation and sudden GPS jump detection against configurable thresholds, highlighting affected segments and warning markers on the map.

4. **Intelligent GPS Spoofing Detection & ML Analysis**
   - Combines a Random Forest classifier trained on six features (`latitude`, `longitude`, `speed`, `acceleration`, `gyroscope`, `signal`) with physical/IMU corridor checks.
   - Displays accuracy, precision, recall, F1-score, confusion matrix, feature importance weights, normal vs. spoofed prediction counts, and per-reading classification explanations.

5. **Secure Drone Communication & Network Traffic Monitoring**
   - Seals and authenticates telemetry frames using per-device AES-256-GCM encryption and associated authenticated data (`device/sequence`).
   - Monitors inbound and outbound packet logs (source/destination addresses, packet size, protocol, timestamps, authentication status).
   - Detects unknown senders, integrity failures (packet injection), replay attacks, rate bursts, and simulated man-in-the-middle probes, and supports blocking/trusting simulated devices.

6. **Attack Simulation Centre**
   - Controlled cyber-range simulations clearly tagged as simulated (`[SIMULATED]`):
     - GPS spoofing attack
     - Unauthorized device access
     - Packet injection attempt
     - Replay attack
     - Suspicious network traffic
     - Abnormal drone location changes
     - Communication interruption
   - Each simulation executes end-to-end detection, alert generation, dashboard updates, logging, and recovery recommendation.

7. **Autonomous Recovery System**
   - Recommends recovery actions with reasoning when threats occur and supports operator execution of:
     - Return to Home
     - Attitude Hold
     - Manual Override
     - Emergency Motor Disarm
     - Resume Patrol
   - Records recovery status, outcomes, alerts, and audit history.

8. **Real-Time Security Alert Centre**
   - Auto-refreshing alerts with `Alert ID`, `Drone ID`, attack type, severity (`Critical`, `High`, `Medium`, `Low`), confidence, timestamp, description, and status (`Active`, `Acknowledged`, `Resolved`).
   - Search, severity/attack-type filters, detail inspection, and optional Web Audio notifications for critical alerts.

9. **Multi-Drone & Health Monitoring**
   - Fleet-wide matrix monitoring battery, altitude, speed, GPS signal strength, network connectivity, sensor status, and flight status with automated health warnings and per-drone JSON security reports.

10. **Security Analytics, Logs, PDF/CSV Reports & Admin Management**
    - Interactive analytics charts for daily/weekly/monthly attack trends, attack/severity distributions, drone-wise stats, recovery counts, and network traffic, filterable by date and drone.
    - Unified searchable security logs and database archive with JSON export.
    - Executive report generation with downloadable **PDF** and **CSV** exports covering all seven operational and ML sections.
    - Admin management with login/logout, role enforcement (`operator`/`admin` vs. read-only `viewer`), configurable detection thresholds, and system audit logs.

---

## Project Structure

```text
backend/
  db.py                  # SQLAlchemy Core schema (drones, telemetry, events, alerts, deviations, network_packets, trusted_devices, recoveries, system_settings, audit_logs)
  main.py                # FastAPI application factory, Flight Watch commands, auth session endpoints
  production.py          # Single-origin production entry point (HTTP Basic auth, security headers, static frontend)
  routes_platform.py     # Platform API routers (dashboard, drones CRUD, ML, deviations, network, simulations, alerts, recovery, analytics, logs, reports, admin)
  service.py             # AES-256-GCM telemetry verification, deviation/spoofing analysis, alert & audit helpers
  model.py               # Synthetic flight dataset generator and Random Forest training/evaluation
  reports.py             # PDF 1.4 and CSV security report generators
  migrations/            # Alembic configuration and schema revisions (001, 002)
  test_watch.py          # Core flight watch API tests
  test_production.py     # Production auth, archive, and health endpoint tests
  test_platform.py       # Platform integration tests (CRUD, ML, network, simulations, recovery, analytics, PDF/CSV, admin)
frontend/
  src/
    main.tsx             # Application shell, sidebar navigation, Flight Watch workspace
    Chart.tsx            # Interactive Leaflet trajectory & deviation map
    Archive.tsx          # Paginated database incident archive search
    types.ts             # Shared TypeScript interfaces
    style.css            # Dark cybersecurity UI theme and responsive layout
    pages/               # Modular pages for Dashboard, Tracking, Drones, ML, Deviations, Network, Simulation, Recovery, Alerts, Health, Analytics, Logs, Reports, Admin
  e2e.spec.ts            # End-to-end Playwright browser tests
  production.spec.ts     # Authenticated viewer/operator Playwright tests
Dockerfile               # Multi-stage Node + Python production container
```

---

## Environment Configuration

Copy `backend/.env.example` to `backend/.env` and configure:

- `DATABASE_URL`: Pooled PostgreSQL connection string (with TLS/SSL required for Neon).
- `MIGRATION_DATABASE_URL`: Direct PostgreSQL connection string for Alembic migrations.
- `SKY_OPERATOR_PASSWORD`: Password for the `operator` / `admin` role (at least 20 characters required in production mode).
- `SKY_VIEWER_PASSWORD`: Distinct password for the read-only `viewer` role (at least 20 characters required in production mode).

---

## Setup and Running on Windows

### 1. First-Time Setup

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements.txt

cd frontend
npm.cmd ci
cd ..
```

Apply database migrations:

```powershell
cd backend
..\.venv\Scripts\python -m alembic upgrade head
cd ..
```

### 2. Development Mode (Two Terminals)

Terminal 1 (FastAPI API on port `8000`):

```powershell
cd backend
..\.venv\Scripts\python -m uvicorn main:create_app --factory --host 127.0.0.1 --port 8000
```

Terminal 2 (React + Vite console on port `5173`, proxying `/api` to port `8000`):

```powershell
cd frontend
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. Use `--workers 1` (default) because per-device AES keys and burst-rate windows are held in process memory.

### 3. Production Preview (Single Origin)

Build the frontend and run the production FastAPI entry point:

```powershell
cd frontend
npm.cmd run build
cd ..\backend
..\.venv\Scripts\python -m uvicorn production:production_app --factory --host 127.0.0.1 --port 8010
```

Open `http://127.0.0.1:8010` and authenticate via HTTP Basic using `operator` or `viewer` credentials from `backend/.env`.

### 4. Docker Deployment

```powershell
docker build -t skysentinel:release .
```

Run migrations with `MIGRATION_DATABASE_URL` during release (`python -m alembic upgrade head`), then run the container on port `8000` behind a TLS reverse proxy with `/health/live` and `/health/ready` health probes.

---

## Verification and Testing

From the repository root:

```powershell
# Backend unit and integration tests (uses isolated temporary databases)
.\.venv\Scripts\python -m pytest backend

# Frontend TypeScript check and production build
cd frontend
npm.cmd run build

# End-to-end browser tests (requires running backend and frontend)
npx.cmd playwright test
```

To run the standalone Random Forest evaluation report from `backend/`:

```powershell
..\.venv\Scripts\python model.py
```
