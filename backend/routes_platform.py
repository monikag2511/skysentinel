from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from db import (
    alerts,
    deviations,
    drones,
    events,
    network_packets,
    recoveries,
    samples,
    trusted_devices,
)
from model import position, trained
from service import get_thresholds, log, now, record_audit


class DroneCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=64)
    code: Optional[str] = Field(None, min_length=2, max_length=32)
    model_type: str = Field("Autonomous UAV", min_length=2, max_length=64)
    battery: float = Field(96.0, ge=0.0, le=100.0)
    altitude: float = Field(120.0, ge=0.0, le=5000.0)
    base_lat: float = Field(13.048, ge=-90.0, le=90.0)
    base_lon: float = Field(80.209, ge=-180.0, le=180.0)
    is_active: bool = True
    route_config: Optional[list[list[float]]] = None


class TrustedDeviceCreate(BaseModel):
    device_uid: str = Field(..., min_length=3, max_length=48)
    name: str = Field(..., min_length=2, max_length=64)
    ip_address: str = Field(..., min_length=4, max_length=45)
    mac_address: str = Field("02:53:4B:00:99:01", min_length=6, max_length=32)
    drone_id: Optional[int] = None


class DroneUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=64)
    model_type: Optional[str] = Field(None, min_length=2, max_length=64)
    battery: Optional[float] = Field(None, ge=0.0, le=100.0)
    altitude: Optional[float] = Field(None, ge=0.0, le=5000.0)
    base_lat: Optional[float] = Field(None, ge=-90.0, le=90.0)
    base_lon: Optional[float] = Field(None, ge=-180.0, le=180.0)
    gps_status: Optional[str] = None
    comm_status: Optional[str] = None
    is_active: Optional[bool] = None
    route_config: Optional[list[list[float]]] = None


def build_platform_router(engine, lock, watch):
    router = APIRouter(prefix="/api", tags=["platform"])

    def _compute_drone_health(c, d, thresholds):
        latest = (
            c.execute(select(samples).where(samples.c.drone == d.id).order_by(samples.c.seq.desc()).limit(1))
            .mappings()
            .first()
        )
        reading_data = latest["reading"] if latest else {}
        speed = float(reading_data.get("speed", 0.0))
        signal = float(reading_data.get("signal", 100.0))
        lat = float(reading_data.get("latitude", d.base_lat))
        lon = float(reading_data.get("longitude", d.base_lon))

        warnings = []
        if d.battery < float(thresholds["low_battery_pct"]):
            warnings.append(f"Low battery ({d.battery:.1f}% < {thresholds['low_battery_pct']:.0f}%)")
        if d.comm_status != "Encrypted":
            warnings.append(f"Communication warning: {d.comm_status}")
        if d.sensor_status != "Nominal":
            warnings.append(f"Sensor irregularity: {d.sensor_status}")
        if d.gps_status in ("Spoofed", "Degraded", "Lost"):
            warnings.append(f"GPS status {d.gps_status}")
        if speed > float(thresholds["speed_threshold_kmh"]):
            warnings.append(f"Abnormal flight speed ({speed:.1f} km/h)")
        if signal < 75.0:
            warnings.append(f"Weak GPS signal ({signal:.1f}%)")

        recent_net_threat = (
            c.execute(
                select(network_packets)
                .where(network_packets.c.drone_id == d.id, network_packets.c.threat_type.is_not(None))
                .order_by(network_packets.c.id.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )

        if not d.is_active:
            sec_status = "Offline"
        elif d.gps_status == "Spoofed" or d.mode == "Attitude hold":
            sec_status = "GPS Spoofed"
        elif d.comm_status != "Encrypted" or (
            recent_net_threat
            and recent_net_threat["auth_status"] in ("Unknown Device", "Integrity Failed", "Blocked", "MITM Suspected")
        ):
            sec_status = "Network Warning"
        elif warnings:
            sec_status = "Warning"
        else:
            sec_status = "Normal"

        return {
            "id": d.id,
            "code": d.code,
            "name": d.name,
            "model_type": d.model_type,
            "mode": d.mode,
            "is_active": d.is_active,
            "battery": round(float(d.battery), 1),
            "altitude": round(float(d.altitude), 1),
            "speed": round(speed, 1),
            "signal": round(signal, 1),
            "latitude": lat,
            "longitude": lon,
            "gps_status": d.gps_status,
            "comm_status": d.comm_status,
            "sensor_status": d.sensor_status,
            "flight_status": d.mode,
            "security_status": sec_status,
            "warnings": warnings,
            "last_seen": latest["time"] if latest else d.created_at,
        }

    @router.get("/dashboard")
    def dashboard():
        with lock, engine.connect() as c:
            thresholds = get_thresholds(c)
            all_drones = c.execute(select(drones).order_by(drones.c.id)).mappings().all()
            drone_map = {d.id: d for d in all_drones}
            health_rows = [_compute_drone_health(c, d, thresholds) for d in all_drones]

            all_alerts = c.execute(select(alerts).order_by(alerts.c.id.desc())).mappings().all()
            attack_alerts = [a for a in all_alerts if a["attack_type"] != "Recovery Initiated"]
            critical_alerts = [
                a for a in all_alerts if a["status"] != "Resolved" and a["severity"] in ("Critical", "High")
            ]
            active_net_alerts = [
                a
                for a in all_alerts
                if a["status"] == "Active"
                and a["attack_type"]
                in (
                    "Unknown sender",
                    "Integrity failure",
                    "Duplicate sequence",
                    "Rate limit",
                    "Blocked device",
                    "Unauthorized Access",
                    "Packet Injection",
                    "Replay Attack",
                    "Suspicious Traffic",
                    "MITM Suspected",
                    "Communication Interruption",
                )
            ]
            spoofed_count = sum(1 for h in health_rows if h["security_status"] == "GPS Spoofed")
            active_count = sum(1 for h in health_rows if h["is_active"] and h["mode"] != "At base")
            normal_count = sum(1 for h in health_rows if h["security_status"] == "Normal" and h["is_active"])

            net_status = (
                "Compromised"
                if any(a["severity"] == "Critical" for a in active_net_alerts)
                else ("Warning" if active_net_alerts else "Secure")
            )
            gps_status = (
                "Under Attack"
                if spoofed_count > 0
                else (
                    "Alert"
                    if any(
                        a["attack_type"] in ("GPS Spoofing", "Flight Path Deviation") and a["status"] == "Active"
                        for a in all_alerts
                    )
                    else "Protected"
                )
            )

            recent_attacks = [
                {
                    **a,
                    "drone_name": drone_map[a["drone_id"]].name if a["drone_id"] in drone_map else "Fleet",
                    "drone_code": drone_map[a["drone_id"]].code if a["drone_id"] in drone_map else "SYS",
                }
                for a in attack_alerts[:12]
            ]

            recent_events = c.execute(select(events).order_by(events.c.id.desc()).limit(15)).mappings().all()
            latest_activity = [
                {
                    **e,
                    "drone_name": drone_map[e["drone"]].name if e["drone"] in drone_map else f"Drone {e['drone']}",
                }
                for e in recent_events
            ]

            return {
                "stats": {
                    "total_registered": len(all_drones),
                    "active_drones": active_count,
                    "normal_drones": normal_count,
                    "spoofed_drones": spoofed_count,
                    "total_cyberattacks": len(attack_alerts),
                    "critical_alerts": len(critical_alerts),
                    "active_alerts": sum(1 for a in all_alerts if a["status"] == "Active"),
                    "network_security_status": net_status,
                    "gps_security_status": gps_status,
                },
                "recent_attacks": recent_attacks,
                "latest_activity": latest_activity,
                "drone_health": health_rows,
                "thresholds": thresholds,
            }

    @router.get("/drones")
    def list_drones(q: str = Query("", max_length=64), status: str = Query("")):
        with lock, engine.connect() as c:
            thresholds = get_thresholds(c)
            rows = c.execute(select(drones).order_by(drones.c.id)).mappings().all()
            health = [_compute_drone_health(c, d, thresholds) for d in rows]
            if q.strip():
                needle = q.strip().lower()
                health = [
                    h
                    for h in health
                    if needle in h["name"].lower()
                    or needle in h["code"].lower()
                    or needle in h["model_type"].lower()
                ]
            if status.strip():
                st = status.strip().lower()
                health = [
                    h
                    for h in health
                    if h["security_status"].lower() == st or h["mode"].lower() == st
                ]
            return {"items": health}

    @router.post("/drones", status_code=201)
    def register_drone(payload: DroneCreate):
        with lock, engine.begin() as c:
            max_id = c.scalar(select(func.max(drones.c.id)))
            new_id = 0 if max_id is None else int(max_id) + 1
            code = (payload.code or f"DRN-{new_id + 1:03d}").strip().upper()
            exists = c.scalar(select(drones.c.id).where(drones.c.code == code))
            if exists is not None:
                raise HTTPException(409, f"Drone code {code} already exists")
            start_pos = list(
                position(
                    new_id,
                    0,
                    base_lat=payload.base_lat,
                    base_lon=payload.base_lon,
                    route_config=payload.route_config,
                )
            )
            c.execute(
                drones.insert().values(
                    id=new_id,
                    name=payload.name.strip(),
                    mode="Patrol" if payload.is_active else "At base",
                    seq=0,
                    streak=0,
                    trusted=start_pos,
                    code=code,
                    model_type=payload.model_type.strip(),
                    battery=payload.battery,
                    altitude=payload.altitude,
                    gps_status="Connected",
                    comm_status="Encrypted",
                    sensor_status="Nominal",
                    is_active=payload.is_active,
                    base_lat=payload.base_lat,
                    base_lon=payload.base_lon,
                    route_config=payload.route_config,
                    created_at=now(),
                )
            )
            watch.ensure_key(new_id)
            c.execute(
                trusted_devices.insert().values(
                    device_uid=f"UAV-LINK-{new_id + 1:03d}",
                    name=f"{payload.name.strip()} Transceiver",
                    ip_address=f"10.42.1.{10 + new_id}",
                    mac_address=f"02:53:4B:00:{(new_id + 1):02X}:11",
                    drone_id=new_id,
                    status="Trusted",
                    last_seen=now(),
                )
            )
            watch.advance(c, new_id)
            log(c, new_id, "Drone registered", f"{payload.name.strip()} ({code}) commissioned.", category="System")
            record_audit(c, "operator", "REGISTER_DRONE", code, f"Registered {payload.name.strip()} (id={new_id})")
            thresholds = get_thresholds(c)
            row = c.execute(select(drones).where(drones.c.id == new_id)).mappings().one()
            return _compute_drone_health(c, row, thresholds)

    @router.put("/drones/{device}")
    def update_drone(device: int, payload: DroneUpdate):
        with lock, engine.begin() as c:
            existing = c.execute(select(drones).where(drones.c.id == device)).mappings().first()
            if not existing:
                raise HTTPException(404, "Drone not found")
            updates = {k: v for k, v in payload.model_dump().items() if v is not None}
            if updates:
                c.execute(drones.update().where(drones.c.id == device).values(**updates))
                log(c, device, "Drone updated", f"Configuration updated: {', '.join(updates.keys())}", category="System")
                record_audit(c, "operator", "UPDATE_DRONE", existing["code"], f"Updated fields: {', '.join(updates.keys())}")
            thresholds = get_thresholds(c)
            row = c.execute(select(drones).where(drones.c.id == device)).mappings().one()
            return _compute_drone_health(c, row, thresholds)

    @router.delete("/drones/{device}")
    def delete_drone(device: int):
        with lock, engine.begin() as c:
            existing = c.execute(select(drones).where(drones.c.id == device)).mappings().first()
            if not existing:
                raise HTTPException(404, "Drone not found")
            c.execute(recoveries.delete().where(recoveries.c.drone_id == device))
            c.execute(alerts.delete().where(alerts.c.drone_id == device))
            c.execute(deviations.delete().where(deviations.c.drone_id == device))
            c.execute(network_packets.delete().where(network_packets.c.drone_id == device))
            c.execute(trusted_devices.delete().where(trusted_devices.c.drone_id == device))
            c.execute(events.delete().where(events.c.drone == device))
            c.execute(samples.delete().where(samples.c.drone == device))
            c.execute(drones.delete().where(drones.c.id == device))
            watch.keys.pop(device, None)
            watch.arrivals.pop(device, None)
            record_audit(c, "operator", "DELETE_DRONE", existing["code"], f"Decommissioned {existing['name']}")
            return {"ok": True, "deleted_id": device}

    @router.get("/drones/{device}/report")
    def drone_report(device: int):
        with lock, engine.connect() as c:
            d = c.execute(select(drones).where(drones.c.id == device)).mappings().first()
            if not d:
                raise HTTPException(404, "Drone not found")
            thresholds = get_thresholds(c)
            health = _compute_drone_health(c, d, thresholds)
            telemetry = (
                c.execute(select(samples).where(samples.c.drone == device).order_by(samples.c.seq.desc()).limit(32))
                .mappings()
                .all()
            )
            drone_alerts = (
                c.execute(select(alerts).where(alerts.c.drone_id == device).order_by(alerts.c.id.desc()).limit(50))
                .mappings()
                .all()
            )
            drone_events = (
                c.execute(select(events).where(events.c.drone == device).order_by(events.c.id.desc()).limit(50))
                .mappings()
                .all()
            )
            drone_deviations = (
                c.execute(select(deviations).where(deviations.c.drone_id == device).order_by(deviations.c.id.desc()).limit(30))
                .mappings()
                .all()
            )
            drone_packets = (
                c.execute(
                    select(network_packets).where(network_packets.c.drone_id == device).order_by(network_packets.c.id.desc()).limit(30)
                )
                .mappings()
                .all()
            )
            drone_recoveries = (
                c.execute(select(recoveries).where(recoveries.c.drone_id == device).order_by(recoveries.c.id.desc()).limit(30))
                .mappings()
                .all()
            )
            return {
                "drone": health,
                "telemetry": telemetry,
                "alerts": drone_alerts,
                "events": drone_events,
                "deviations": drone_deviations,
                "packets": drone_packets,
                "recoveries": drone_recoveries,
            }

    @router.get("/ml/analysis")
    def ml_analysis(drone_id: Optional[int] = None, classification: Optional[str] = None):
        with lock, engine.connect() as c:
            all_drones = {d.id: d for d in c.execute(select(drones)).mappings()}
            all_rows = c.execute(select(samples).order_by(samples.c.id.desc()).limit(250)).mappings().all()
            normal_count = sum(1 for r in all_rows if r["classification"] == "Normal")
            spoofed_count = sum(1 for r in all_rows if r["classification"] == "GPS Spoofed")
            filtered = all_rows
            if drone_id is not None:
                filtered = [r for r in filtered if r["drone"] == drone_id]
            if classification:
                filtered = [r for r in filtered if r["classification"] == classification]

            eval_report = trained()[1]
            return {
                "evaluation": eval_report,
                "live_counts": {
                    "total": len(all_rows),
                    "normal": normal_count,
                    "spoofed": spoofed_count,
                },
                "predictions": [
                    {
                        **r,
                        "drone_name": all_drones[r["drone"]].name if r["drone"] in all_drones else f"Drone {r['drone']}",
                        "drone_code": all_drones[r["drone"]].code if r["drone"] in all_drones else "DRN",
                    }
                    for r in filtered[:80]
                ],
            }

    @router.get("/network/overview")
    def network_overview(direction: Optional[str] = None, threat_only: bool = False):
        with lock, engine.connect() as c:
            all_drones = {d.id: d for d in c.execute(select(drones)).mappings()}
            pkt_q = select(network_packets).order_by(network_packets.c.id.desc()).limit(120)
            if direction in ("Inbound", "Outbound"):
                pkt_q = pkt_q.where(network_packets.c.direction == direction)
            if threat_only:
                pkt_q = pkt_q.where(network_packets.c.threat_type.is_not(None))
            packets = c.execute(pkt_q).mappings().all()
            devices = c.execute(select(trusted_devices).order_by(trusted_devices.c.id)).mappings().all()
            all_pkts = c.execute(select(network_packets)).mappings().all()
            encrypted_count = sum(1 for p in all_pkts if p["encrypted"])
            auth_ok_count = sum(1 for p in all_pkts if p["auth_status"] == "Authenticated")
            threat_counts = {
                "packet_injection": sum(1 for p in all_pkts if p["threat_type"] == "Packet Injection"),
                "replay_attack": sum(1 for p in all_pkts if p["threat_type"] == "Replay Attack"),
                "mitm_suspected": sum(1 for p in all_pkts if p["threat_type"] == "MITM Suspected"),
                "unauthorized": sum(
                    1 for p in all_pkts if p["threat_type"] in ("Unauthorized Access", "Unauthorized Device")
                ),
                "rate_burst": sum(1 for p in all_pkts if p["threat_type"] == "Suspicious Traffic"),
            }
            return {
                "summary": {
                    "total_packets": len(all_pkts),
                    "encrypted_pct": round((encrypted_count / len(all_pkts)) * 100, 1) if all_pkts else 100.0,
                    "auth_integrity_pct": round((auth_ok_count / len(all_pkts)) * 100, 1) if all_pkts else 100.0,
                    "trusted_count": sum(1 for dv in devices if dv["status"] == "Trusted"),
                    "blocked_count": sum(1 for dv in devices if dv["status"] == "Blocked"),
                    "threat_counts": threat_counts,
                },
                "packets": [
                    {
                        **p,
                        "drone_name": all_drones[p["drone_id"]].name
                        if p["drone_id"] in all_drones
                        else "External / GCS",
                    }
                    for p in packets
                ],
                "devices": devices,
            }

    @router.post("/network/devices", status_code=201)
    def add_trusted_device(payload: TrustedDeviceCreate):
        with lock, engine.begin() as c:
            uid = payload.device_uid.strip().upper()
            exists = c.scalar(select(trusted_devices.c.id).where(trusted_devices.c.device_uid == uid))
            if exists is not None:
                raise HTTPException(409, f"Device {uid} already exists")
            row_id = (
                c.execute(
                    trusted_devices.insert().values(
                        device_uid=uid,
                        name=payload.name.strip(),
                        ip_address=payload.ip_address.strip(),
                        mac_address=payload.mac_address.strip(),
                        drone_id=payload.drone_id,
                        status="Trusted",
                        last_seen=now(),
                    )
                ).inserted_primary_key[0]
            )
            record_audit(c, "operator", "TRUST_DEVICE", uid, f"Added trusted device {payload.name.strip()}")
            return c.execute(select(trusted_devices).where(trusted_devices.c.id == row_id)).mappings().one()

    @router.post("/network/devices/{device_uid}/block")
    def block_device(device_uid: str):
        with lock, engine.begin() as c:
            uid = device_uid.strip()
            existing = c.execute(select(trusted_devices).where(trusted_devices.c.device_uid == uid)).mappings().first()
            if existing:
                c.execute(
                    trusted_devices.update()
                    .where(trusted_devices.c.device_uid == uid)
                    .values(status="Blocked", last_seen=now())
                )
                target_drone = existing["drone_id"]
            else:
                c.execute(
                    trusted_devices.insert().values(
                        device_uid=uid,
                        name=f"Blocked Node ({uid})",
                        ip_address="192.168.99.204",
                        mac_address="DE:AD:BE:EF:00:01",
                        drone_id=None,
                        status="Blocked",
                        last_seen=now(),
                    )
                )
                target_drone = None
            c.execute(
                network_packets.insert().values(
                    drone_id=target_drone,
                    time=now(),
                    direction="Inbound",
                    src_addr=existing["ip_address"] if existing else "192.168.99.204",
                    dst_addr="10.42.0.1:8443",
                    device_uid=uid,
                    packet_size=64,
                    protocol="ACL/DROP",
                    encrypted=False,
                    auth_status="Blocked",
                    threat_type="Unauthorized Device",
                    simulated=True,
                    detail=f"Administrator blocked device {uid} on network firewall.",
                )
            )
            if target_drone is not None:
                log(c, target_drone, "Device blocked", f"Blocked network node {uid}.", "Medium", "Recorded", category="Network", simulated=True)
            record_audit(c, "operator", "BLOCK_DEVICE", uid, f"Blocked simulated device {uid}")
            return {"ok": True, "device_uid": uid, "status": "Blocked"}

    @router.post("/network/devices/{device_uid}/trust")
    def trust_device(device_uid: str):
        with lock, engine.begin() as c:
            uid = device_uid.strip()
            existing = c.execute(select(trusted_devices).where(trusted_devices.c.device_uid == uid)).mappings().first()
            if not existing:
                raise HTTPException(404, "Device not found")
            c.execute(
                trusted_devices.update()
                .where(trusted_devices.c.device_uid == uid)
                .values(status="Trusted", last_seen=now())
            )
            record_audit(c, "operator", "TRUST_DEVICE", uid, f"Restored trust for {uid}")
            return {"ok": True, "device_uid": uid, "status": "Trusted"}

    @router.get("/deviations")
    def list_deviations(drone_id: Optional[int] = None, severity: Optional[str] = None):
        with lock, engine.connect() as c:
            all_drones = {d.id: d for d in c.execute(select(drones)).mappings()}
            q = select(deviations).order_by(deviations.c.id.desc()).limit(100)
            if drone_id is not None:
                q = q.where(deviations.c.drone_id == drone_id)
            if severity:
                q = q.where(deviations.c.severity == severity)
            rows = c.execute(q).mappings().all()
            return {
                "items": [
                    {
                        **r,
                        "drone_name": all_drones[r["drone_id"]].name if r["drone_id"] in all_drones else f"Drone {r['drone_id']}",
                        "drone_code": all_drones[r["drone_id"]].code if r["drone_id"] in all_drones else "DRN",
                    }
                    for r in rows
                ]
            }

    return router
