# SkySentinel

## Production deployment

The production entry point serves the compiled dashboard and API from one origin. The sign-in usernames are `viewer` (inspect and export records) and `operator` (also run scenarios and acknowledge incidents). Configure separate generated passwords in `SKY_VIEWER_PASSWORD` and `SKY_OPERATOR_PASSWORD`. Rotate either password in the deployment secret store and restart the service to revoke its previous value. These are two shared role accounts for a small team.

1. Configure the Neon URLs and both role passwords in the deployment secret store. Supply the direct migration URL only to the release job. For public access, terminate HTTPS at the hosting ingress and restrict the application port to that ingress. Browser sign-in uses HTTP Basic over TLS.
2. Build the image with `docker build -t skysentinel:release .`. The build uses the npm lockfile and pinned Python packages and excludes local credentials. Run `python -m alembic upgrade head` once as the release command with migration credentials.
3. Run the image with the configured environment. It serves port 8000 as a non-root user. Use one instance and one worker for the simulator’s in-memory device keys and counters. Configure the ingress to throttle sign-in attempts and set a request-body limit. Point the readiness check at `/health/ready` and liveness at `/health/live`.
4. Verify that anonymous requests to the dashboard receive 401, viewer commands receive 403, and a signed-in operator can complete the recovery demo. Confirm the Neon backup/restore policy and test a restore before opening the deployment to users.

For a local production preview, build the frontend, configure the four backend environment variables, then run this from `backend/`:

```powershell
..\.venv\Scripts\python -m uvicorn production:production_app --factory --host 127.0.0.1 --port 8010
```

The incident ledger includes a searchable archive across the database. Search by event, detail, status or aircraft and optionally filter severity. Each page has up to 25 records. Export downloads exactly the loaded results as JSON.

### Verify a release

The GitHub Actions workflow builds the image and runs a migrated, disposable PostgreSQL instance and Chromium browser tests. It uses CI-only credentials. To run the authenticated browser suite against a local preview, run the following from `frontend/`. The operator tests create simulated events in the configured database.

```powershell
$env:SKY_PRODUCTION_TEST = "1"
$env:FRONTEND_URL = "http://127.0.0.1:8010"
node --env-file=../backend/.env node_modules/@playwright/test/cli.js test
```

For rollback, retain the previous image digest. This release adds no database migrations. Redeploy the previous image if the readiness probe or recovery smoke test fails. For future schema changes, verify backward compatibility before rolling the application back.

A dark-theme drone cybersecurity command platform built with React, TypeScript, Leaflet, FastAPI, scikit-learn, and PostgreSQL (Neon). Modules include the Security Dashboard, Drone Management (CRUD), Live Multi-Drone GPS Tracking, Intelligent GPS Spoofing & ML Analysis, Flight Path Deviation Detection, Secure AES-256-GCM Communication & Network Traffic Monitoring, Attack Simulation Centre, Autonomous Recovery, Real-Time Security Alert Centre, Multi-Drone & Health Monitoring, Security Analytics, Security Logs, PDF/CSV Report Generation, and Admin Management.

## Start on Windows
From the repository root, create the virtual environment and install the backend once.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements.txt
```

Set DATABASE_URL in backend/.env using the pooled Neon connection string. Set MIGRATION_DATABASE_URL to the direct connection URI for the same database. The example file contains the variable names. Both connections require TLS.

In a PowerShell terminal, start the API from the repository root.

```powershell
cd backend
..\.venv\Scripts\python -m alembic upgrade head
..\.venv\Scripts\python -m uvicorn main:create_app --factory --host 127.0.0.1 --port 8000
```

In a second terminal, start the console.

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open http://127.0.0.1:5173. The local Vite server proxies /api to FastAPI. Use one API worker for this simulator. Device encryption keys and burst counters are per-process. Persistent sequence numbers and incident history live in PostgreSQL.

## Demonstration
1. Select an aircraft and run Normal flight. Start continuous patrol to advance the selected flight every 3.5 seconds while the dashboard is open. Pause it before switching scenarios.
2. Run Duplicate sequence, Unknown sender or Integrity failure. Find the rejection in the ledger and acknowledge it. The last trusted fix stays in place.
3. Run GPS deviation. Inspect the reported position, model score and hold event. Select Return to base, then Resume patrol. Refresh to inspect the persisted incident.
4. Select View test results for model metrics. Execute python model.py from the backend directory for the complete confusion matrix and per-class report.

A trace shows up to 32 readings per drone. The ledger displays the latest 100 events. Data is synthetic and recovery actions update the simulator. The network module exercises authenticated messages in memory. Wireshark can inspect local browser/API HTTP exchanges on a loopback capture or the TLS connection to Neon; those are application links, not radio traffic.

## Checks
Run the following from the repository root. The API test uses a disposable database. The browser test requires the two running servers and Microsoft Edge and creates demonstration events in the configured database.

```powershell
.\.venv\Scripts\python -m pytest backend
cd frontend
npm.cmd run build
npx.cmd playwright test
```
