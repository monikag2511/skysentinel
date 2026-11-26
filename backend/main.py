from contextlib import asynccontextmanager
from threading import RLock
from time import monotonic
from typing import Literal
from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from db import alerts, database, drones, events, network_packets, recoveries, samples
from model import position, trained
from routes_platform import build_platform_router
from service import FlightWatch, create_alert, log, now


class Command(BaseModel):
    action: Literal["normal", "gps", "unknown", "duplicate", "integrity", "rate", "ack", "home", "resume"]
    incident: int | None = None


def create_app(engine=None, *, docs=True):
    engine = engine or database()
    watch = FlightWatch()
    lock = RLock()

    @asynccontextmanager
    async def lifespan(app):
        with engine.begin() as c:
            watch.seed(c)
        yield
        engine.dispose()

    app = FastAPI(
        title="SkySentinel Cybersecurity Platform",
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )

    @app.get("/health/live")
    def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready():
        try:
            with engine.connect() as c:
                c.execute(select(drones.c.id).limit(1))
        except SQLAlchemyError:
            raise HTTPException(503, "Storage unavailable") from None
        return {"status": "ready"}

    @app.get("/api/archive")
    def archive(
        q: str = Query("", max_length=100),
        before: int | None = Query(None, gt=0),
        severity: Literal["Info", "Medium", "High"] | None = None,
        limit: int = Query(25, ge=1, le=100),
    ):
        query = select(events, drones.c.name.label("aircraft")).join(drones, drones.c.id == events.c.drone)
        if q.strip():
            query = query.where(
                or_(
                    *(
                        field.icontains(q.strip(), autoescape=True)
                        for field in (events.c.kind, events.c.detail, drones.c.name, events.c.status)
                    )
                )
            )
        if severity:
            query = query.where(events.c.severity == severity)
        if before:
            query = query.where(events.c.id < before)
        with engine.connect() as c:
            rows = c.execute(query.order_by(events.c.id.desc()).limit(limit + 1)).mappings().all()
        return {"items": rows[:limit], "next": rows[limit - 1].id if len(rows) > limit else None}

    @app.get("/api/watch")
    def snapshot(request: Request):
        with lock, engine.begin() as c:
            fleet = []
            for row in c.execute(select(drones).order_by(drones.c.id)).mappings():
                track = (
                    c.execute(select(samples).where(samples.c.drone == row.id).order_by(samples.c.seq.desc()).limit(32))
                    .mappings()
                    .all()
                )
                fleet.append(
                    {
                        **row,
                        "track": list(reversed(track)),
                        "route": [
                            position(
                                row.id,
                                n,
                                base_lat=row.base_lat,
                                base_lon=row.base_lon,
                                route_config=row.route_config,
                            )
                            for n in range(73)
                        ],
                    }
                )
            history = c.execute(select(events).order_by(events.c.id.desc()).limit(100)).mappings().all()
            return {"fleet": fleet, "history": history, "role": getattr(request.state, "role", "operator")}

    @app.get("/api/evaluation")
    def evaluation():
        return trained()[1]

    @app.post("/api/drones/{device}/commands")
    def command(device: int, cmd: Command):
        with lock, engine.begin() as c:
            d = c.execute(select(drones).where(drones.c.id == device).with_for_update()).mappings().first()
            if d is None:
                raise HTTPException(404, "Unknown aircraft")
            if cmd.action == "ack":
                incident = (
                    c.execute(select(events).where(events.c.id == cmd.incident, events.c.drone == device))
                    .mappings()
                    .first()
                )
                if not incident or incident.status != "Open":
                    raise HTTPException(409, "Select an open incident")
                c.execute(events.update().where(events.c.id == cmd.incident).values(status="Acknowledged"))
                c.execute(
                    alerts.update()
                    .where(alerts.c.source_event_id == cmd.incident, alerts.c.status == "Active")
                    .values(status="Acknowledged")
                )
                log(c, device, "Acknowledged", incident.kind, incident=incident.id, category="Alert")
            elif cmd.action == "home":
                if d.mode != "Attitude hold":
                    raise HTTPException(409, "Return requires an active hold")
                incident_id = c.scalar(
                    select(events.c.id)
                    .where(events.c.drone == device, events.c.kind == "GPS deviation")
                    .order_by(events.c.id.desc())
                    .limit(1)
                )
                home_pos = list(
                    position(device, 0, base_lat=d.base_lat, base_lon=d.base_lon, route_config=d.route_config)
                )
                c.execute(
                    drones.update()
                    .where(drones.c.id == device)
                    .values(mode="At base", trusted=home_pos, gps_status="Connected", sensor_status="Nominal")
                )
                if incident_id:
                    c.execute(events.update().where(events.c.id == incident_id).values(status="Resolved"))
                    c.execute(
                        alerts.update()
                        .where(alerts.c.source_event_id == incident_id)
                        .values(status="Resolved")
                    )
                log(c, device, "Returned to base", "Simulated return complete.", incident=incident_id, category="Recovery")
                c.execute(
                    recoveries.insert().values(
                        drone_id=device,
                        alert_id=None,
                        recommended_action="Return to Home",
                        recommendation_reason="Operator initiated Return to Home from Attitude hold.",
                        selected_action="Return to Home",
                        status="Successful",
                        initiated_by="Operator",
                        simulated=True,
                        created_at=now(),
                        completed_at=now(),
                        detail="Simulated return to base completed safely.",
                    )
                )
                create_alert(
                    c,
                    device,
                    "Recovery Initiated",
                    "Low",
                    f"{d.name} executed Return to Home recovery.",
                    confidence=100.0,
                    simulated=True,
                )
            elif cmd.action == "resume":
                if d.mode != "At base":
                    raise HTTPException(409, "Resume patrol from base")
                c.execute(
                    drones.update()
                    .where(drones.c.id == device)
                    .values(mode="Patrol", streak=0, gps_status="Connected", comm_status="Encrypted", sensor_status="Nominal")
                )
                log(c, device, "Patrol resumed", "Simulator released from base.", category="Recovery")
            else:
                if d.mode != "Patrol" and cmd.action in ("normal", "gps", "rate"):
                    raise HTTPException(409, "Complete recovery before continuing patrol")
                attempts = {"gps": 2, "rate": 9}.get(cmd.action, 1)
                burst_time = monotonic() if cmd.action == "rate" else None
                for _ in range(attempts):
                    reason = watch.advance(c, device, "normal" if cmd.action == "rate" else cmd.action, burst_time)
                    if reason:
                        break
            c.execute(
                network_packets.insert().values(
                    drone_id=device,
                    time=now(),
                    direction="Outbound",
                    src_addr="10.42.0.1:8443",
                    dst_addr=f"10.42.1.{10 + device}:9000",
                    device_uid="GCS-CTRL-01",
                    packet_size=96,
                    protocol="AES-256-GCM/UDP",
                    encrypted=True,
                    auth_status="Authenticated",
                    threat_type=None,
                    simulated=False,
                    detail=f"Encrypted control command '{cmd.action}' dispatched to {d.name}.",
                )
            )
            return {"ok": True}

    app.include_router(build_platform_router(engine, lock, watch))
    return app
