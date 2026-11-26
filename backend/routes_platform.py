from collections import Counter
from datetime import datetime
from time import monotonic
from typing import Literal, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from db import (
    alerts,
    audit_logs,
    deviations,
    drones,
    events,
    network_packets,
    recoveries,
    samples,
    system_settings,
    trusted_devices,
)
from model import position, reading, trained
from reports import build_csv_report, build_pdf_report
from service import create_alert, get_thresholds, log, now, record_audit


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


class SimulationRequest(BaseModel):
    drone_id: int
    attack_type: Literal[
        "gps_spoofing",
        "unauthorized_device",
        "packet_injection",
        "replay_attack",
        "suspicious_traffic",
        "abnormal_location",
        "comm_interruption",
    ]


class RecoveryActionRequest(BaseModel):
    action: Literal["Return to Home", "Attitude Hold", "Manual Override", "Emergency Motor Disarm", "Resume Patrol"]
    recovery_id: Optional[int] = None
    reason: Optional[str] = None


class ThresholdSettings(BaseModel):
    deviation_threshold_m: float = Field(150.0, ge=10.0, le=5000.0)
    spoof_score_threshold: float = Field(0.5, ge=0.1, le=0.99)
    speed_threshold_kmh: float = Field(45.0, ge=10.0, le=300.0)
    accel_threshold_ms2: float = Field(3.5, ge=0.5, le=50.0)
    rate_limit_per_sec: int = Field(8, ge=1, le=100)
    low_battery_pct: float = Field(25.0, ge=5.0, le=90.0)


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

    def _compute_drone_health(c, d, thresholds, latest_sample=None, recent_net_threat=None, preloaded=False):
        if not preloaded:
            latest_sample = (
                c.execute(select(samples).where(samples.c.drone == d.id).order_by(samples.c.seq.desc()).limit(1))
                .mappings()
                .first()
            )
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
        latest = latest_sample
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

    def _bulk_health(c, all_drones, thresholds):
        latest_by_drone = {}
        for s in c.execute(select(samples).order_by(samples.c.seq.desc()).limit(250)).mappings():
            if s["drone"] not in latest_by_drone:
                latest_by_drone[s["drone"]] = s
        threat_by_drone = {}
        for p in c.execute(
            select(network_packets)
            .where(network_packets.c.threat_type.is_not(None))
            .order_by(network_packets.c.id.desc())
            .limit(100)
        ).mappings():
            if p["drone_id"] is not None and p["drone_id"] not in threat_by_drone:
                threat_by_drone[p["drone_id"]] = p
        return [
            _compute_drone_health(
                c,
                d,
                thresholds,
                latest_sample=latest_by_drone.get(d.id),
                recent_net_threat=threat_by_drone.get(d.id),
                preloaded=True,
            )
            for d in all_drones
        ]

    @router.get("/dashboard")
    def dashboard():
        with engine.connect() as c:
            thresholds = get_thresholds(c)
            all_drones = c.execute(select(drones).order_by(drones.c.id)).mappings().all()
            drone_map = {d.id: d for d in all_drones}
            health_rows = _bulk_health(c, all_drones, thresholds)

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
        with engine.connect() as c:
            thresholds = get_thresholds(c)
            rows = c.execute(select(drones).order_by(drones.c.id)).mappings().all()
            health = _bulk_health(c, rows, thresholds)
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
        with engine.connect() as c:
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
        with engine.connect() as c:
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
        with engine.connect() as c:
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

    @router.post("/simulations/run")
    def run_simulation(payload: SimulationRequest):
        with lock, engine.begin() as c:
            d = c.execute(select(drones).where(drones.c.id == payload.drone_id).with_for_update()).mappings().first()
            if not d:
                raise HTTPException(404, "Drone not found")
            steps = []
            atk = payload.attack_type
            watch.ensure_key(d.id)

            if atk == "gps_spoofing":
                if d.mode != "Patrol":
                    c.execute(drones.update().where(drones.c.id == d.id).values(mode="Patrol", streak=0))
                for _ in range(2):
                    watch.advance(c, d.id, "gps", simulated=True)
                steps = [
                    "1. Generated 2 simulated spoofed GPS frames with velocity/signal anomalies.",
                    "2. Random Forest + IMU corridor analyzer flagged GPS Spoofing.",
                    "3. Drone status transitioned to Attitude hold / GPS Spoofed.",
                    "4. Critical/High security alert generated & flight deviation logged.",
                    "5. Autonomous Recovery recommended Return to Home.",
                ]
            elif atk == "abnormal_location":
                if d.mode != "Patrol":
                    c.execute(drones.update().where(drones.c.id == d.id).values(mode="Patrol", streak=0))
                import random
                seq = d.seq + 1
                exp = position(d.id, seq, base_lat=d.base_lat, base_lon=d.base_lon, route_config=d.route_config)
                row = reading(d.id, seq, True, random.Random(9000 + seq), base_lat=d.base_lat, base_lon=d.base_lon, route_config=d.route_config)
                row["latitude"] = round(exp[0] + 0.0045, 6)
                row["longitude"] = round(exp[1] + 0.0045, 6)
                nonce, data = watch.seal(d.id, seq, row)
                watch.receive(c, d, d.id, seq, (nonce, data), simulated=True)
                # Second frame to trigger hold & recovery
                d2 = c.execute(select(drones).where(drones.c.id == d.id)).mappings().one()
                seq2 = d2.seq + 1
                row2 = dict(row)
                row2["latitude"] = round(exp[0] + 0.0048, 6)
                nonce2, data2 = watch.seal(d.id, seq2, row2)
                watch.receive(c, d2, d.id, seq2, (nonce2, data2), simulated=True)
                steps = [
                    "1. Injected sudden 500m+ coordinate jump outside planned corridor.",
                    "2. Path deviation detector measured jump > threshold and flagged anomaly.",
                    "3. Map warning markers & affected red segment highlighted.",
                    "4. Security alert and deviation history recorded.",
                    "5. Autonomous Recovery queued Return to Home.",
                ]
            elif atk == "unauthorized_device":
                watch.advance(c, d.id, "unknown", simulated=True)
                steps = [
                    "1. Simulated telemetry frame from unregistered node UNKNOWN-NODE-FF.",
                    "2. Sender authentication rejected frame before updating flight state.",
                    "3. Packet logged in Network Monitor as Unauthorized Access.",
                    "4. High-severity alert & security log recorded.",
                ]
            elif atk == "packet_injection":
                watch.advance(c, d.id, "integrity", simulated=True)
                steps = [
                    "1. Injected modified ciphertext violating AES-256-GCM authentication tag.",
                    "2. Cryptographic verifier dropped tampered payload (Integrity Failed).",
                    "3. Packet Injection indicator logged in Network Traffic Monitor.",
                    "4. High-severity security alert raised.",
                ]
            elif atk == "replay_attack":
                watch.advance(c, d.id, "duplicate", simulated=True)
                steps = [
                    "1. Replayed previously accepted telemetry sequence number.",
                    "2. Anti-replay sequence check rejected stale frame.",
                    "3. Replay Attack indicator stored in Network Monitor & Security Logs.",
                    "4. Medium-severity alert raised.",
                ]
            elif atk == "suspicious_traffic":
                burst_t = monotonic()
                for _ in range(9):
                    reason = watch.advance(c, d.id, "normal", arrived=burst_t, simulated=True)
                    if reason:
                        break
                c.execute(
                    network_packets.insert().values(
                        drone_id=d.id,
                        time=now(),
                        direction="Inbound",
                        src_addr="198.51.100.77",
                        dst_addr="10.42.0.1:8443",
                        device_uid="MITM-PROXY-SIM",
                        packet_size=1420,
                        protocol="RAW/TCP",
                        encrypted=False,
                        auth_status="MITM Suspected",
                        threat_type="MITM Suspected",
                        simulated=True,
                        detail="Simulated ARP/TLS downgrade probe & high-rate packet flood detected.",
                    )
                )
                ev_id = log(c, d.id, "MITM & Traffic Burst", "Simulated suspicious network flood and MITM probe detected.", "Critical", "Open", category="Network", simulated=True)
                al_id = create_alert(
                    c,
                    d.id,
                    "MITM Suspected",
                    "Critical",
                    f"[SIMULATED] Suspicious traffic burst and MITM probe targeting {d.name}.",
                    confidence=96.0,
                    simulated=True,
                    source_event_id=ev_id,
                )
                c.execute(
                    recoveries.insert().values(
                        drone_id=d.id,
                        alert_id=al_id,
                        recommended_action="Attitude Hold",
                        recommendation_reason="Suspicious network flood / MITM indicator detected on control link.",
                        selected_action=None,
                        status="Recommended",
                        initiated_by="Autonomous Advisor",
                        simulated=True,
                        created_at=now(),
                        completed_at=None,
                        detail="Hold position while isolating suspicious network node.",
                    )
                )
                steps = [
                    "1. Simulated 9x packet flood + unencrypted MITM proxy probe.",
                    "2. Rate limiter and deep packet inspection classified MITM Suspected.",
                    "3. Critical alert and network threat telemetry recorded.",
                    "4. Autonomous Recovery recommended Attitude Hold.",
                ]
            elif atk == "comm_interruption":
                c.execute(
                    drones.update()
                    .where(drones.c.id == d.id)
                    .values(comm_status="Disconnected", gps_status="Degraded", mode="Attitude hold")
                )
                c.execute(
                    network_packets.insert().values(
                        drone_id=d.id,
                        time=now(),
                        direction="Inbound",
                        src_addr=f"10.42.1.{10 + d.id}",
                        dst_addr="10.42.0.1:8443",
                        device_uid=f"UAV-LINK-{d.id + 1:03d}",
                        packet_size=0,
                        protocol="LINK-TIMEOUT",
                        encrypted=False,
                        auth_status="Integrity Failed",
                        threat_type="Communication Interruption",
                        simulated=True,
                        detail="Simulated RF link heartbeat timeout (>5000ms).",
                    )
                )
                ev_id = log(c, d.id, "Communication interruption", "Simulated control-link loss; fail-safe hold engaged.", "Critical", "Open", category="Network", simulated=True)
                al_id = create_alert(
                    c,
                    d.id,
                    "Communication Interruption",
                    "Critical",
                    f"[SIMULATED] Control-link heartbeat lost for {d.name}.",
                    confidence=99.0,
                    simulated=True,
                    source_event_id=ev_id,
                )
                c.execute(
                    recoveries.insert().values(
                        drone_id=d.id,
                        alert_id=al_id,
                        recommended_action="Return to Home",
                        recommendation_reason="Simulated link interruption triggered autonomous RTH fail-safe.",
                        selected_action=None,
                        status="Recommended",
                        initiated_by="Autonomous Advisor",
                        simulated=True,
                        created_at=now(),
                        completed_at=None,
                        detail="Awaiting operator recovery decision.",
                    )
                )
                steps = [
                    "1. Simulated control-link RF timeout for selected aircraft.",
                    "2. Communication status updated to Disconnected; flight mode set to Attitude hold.",
                    "3. Critical alert and link-loss incident stored in Security Logs.",
                    "4. Autonomous Recovery recommended Return to Home.",
                ]

            record_audit(c, "operator", "SIMULATE_ATTACK", d.code, f"Simulated {atk} on {d.name}")
            return {"ok": True, "simulated": True, "attack_type": atk, "drone_id": d.id, "steps": steps}

    @router.get("/alerts")
    def list_alerts(
        q: str = Query("", max_length=100),
        severity: Optional[str] = None,
        attack_type: Optional[str] = None,
        status: Optional[str] = None,
    ):
        with engine.connect() as c:
            all_drones = {d.id: d for d in c.execute(select(drones)).mappings()}
            query = select(alerts).order_by(alerts.c.id.desc()).limit(200)
            if severity:
                query = query.where(alerts.c.severity == severity)
            if attack_type:
                query = query.where(alerts.c.attack_type == attack_type)
            if status:
                query = query.where(alerts.c.status == status)
            rows = c.execute(query).mappings().all()
            items = []
            needle = q.strip().lower()
            for r in rows:
                d_name = all_drones[r["drone_id"]].name if r["drone_id"] in all_drones else "Fleet"
                d_code = all_drones[r["drone_id"]].code if r["drone_id"] in all_drones else "SYS"
                if needle and not (
                    needle in r["alert_code"].lower()
                    or needle in r["attack_type"].lower()
                    or needle in r["description"].lower()
                    or needle in d_name.lower()
                ):
                    continue
                items.append({**r, "drone_name": d_name, "drone_code": d_code})
            attack_types = sorted({r["attack_type"] for r in c.execute(select(alerts.c.attack_type)).mappings()})
            return {"items": items, "attack_types": attack_types}

    @router.post("/alerts/{alert_id}/acknowledge")
    def ack_alert(alert_id: int):
        with lock, engine.begin() as c:
            al = c.execute(select(alerts).where(alerts.c.id == alert_id)).mappings().first()
            if not al:
                raise HTTPException(404, "Alert not found")
            c.execute(alerts.update().where(alerts.c.id == alert_id).values(status="Acknowledged"))
            if al["source_event_id"]:
                c.execute(events.update().where(events.c.id == al["source_event_id"]).values(status="Acknowledged"))
            record_audit(c, "operator", "ACK_ALERT", al["alert_code"], f"Acknowledged {al['attack_type']}")
            return {"ok": True}

    @router.post("/alerts/{alert_id}/resolve")
    def resolve_alert(alert_id: int):
        with lock, engine.begin() as c:
            al = c.execute(select(alerts).where(alerts.c.id == alert_id)).mappings().first()
            if not al:
                raise HTTPException(404, "Alert not found")
            c.execute(alerts.update().where(alerts.c.id == alert_id).values(status="Resolved"))
            if al["source_event_id"]:
                c.execute(events.update().where(events.c.id == al["source_event_id"]).values(status="Resolved"))
            record_audit(c, "operator", "RESOLVE_ALERT", al["alert_code"], f"Resolved {al['attack_type']}")
            return {"ok": True}

    @router.get("/recoveries")
    def list_recoveries():
        with engine.connect() as c:
            all_drones = {d.id: d for d in c.execute(select(drones)).mappings()}
            rows = c.execute(select(recoveries).order_by(recoveries.c.id.desc()).limit(100)).mappings().all()
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

    @router.post("/drones/{device}/recover")
    def execute_recovery(device: int, payload: RecoveryActionRequest):
        with lock, engine.begin() as c:
            d = c.execute(select(drones).where(drones.c.id == device).with_for_update()).mappings().first()
            if not d:
                raise HTTPException(404, "Drone not found")
            action = payload.action
            ts = now()
            home_pos = list(position(device, 0, base_lat=d.base_lat, base_lon=d.base_lon, route_config=d.route_config))

            if action == "Return to Home":
                new_mode, new_gps, new_comm, new_sensor = "At base", "Connected", "Encrypted", "Nominal"
                new_trusted = home_pos
                detail = "Simulated autonomous Return to Home completed; aircraft landed at safe base coordinates."
            elif action == "Attitude Hold":
                new_mode, new_gps, new_comm, new_sensor = "Attitude hold", d.gps_status, "Encrypted", d.sensor_status
                new_trusted = d.trusted
                detail = "Simulated Attitude Hold engaged using inertial sensors; ignoring untrusted GPS fixes."
            elif action == "Manual Override":
                new_mode, new_gps, new_comm, new_sensor = "Manual override", "Degraded", "Encrypted", "Nominal"
                new_trusted = d.trusted
                detail = "Operator assumed simulated manual RC/GCS flight control override."
            elif action == "Emergency Motor Disarm":
                new_mode, new_gps, new_comm, new_sensor = "Disarmed", d.gps_status, d.comm_status, d.sensor_status
                new_trusted = d.trusted
                detail = "Simulated emergency motor disarm executed (hardware safety simulation only)."
            else:  # Resume Patrol
                new_mode, new_gps, new_comm, new_sensor = "Patrol", "Connected", "Encrypted", "Nominal"
                new_trusted = d.trusted
                detail = "Simulated patrol resumed from safe recovery state."

            c.execute(
                drones.update()
                .where(drones.c.id == device)
                .values(
                    mode=new_mode,
                    gps_status=new_gps,
                    comm_status=new_comm,
                    sensor_status=new_sensor,
                    trusted=new_trusted,
                    streak=0 if action in ("Return to Home", "Resume Patrol") else d.streak,
                )
            )
            if action in ("Return to Home", "Resume Patrol", "Emergency Motor Disarm"):
                c.execute(
                    alerts.update()
                    .where(alerts.c.drone_id == device, alerts.c.status != "Resolved")
                    .values(status="Resolved")
                )
                c.execute(
                    events.update()
                    .where(events.c.drone == device, events.c.status == "Open")
                    .values(status="Resolved")
                )

            if payload.recovery_id:
                c.execute(
                    recoveries.update()
                    .where(recoveries.c.id == payload.recovery_id)
                    .values(
                        selected_action=action,
                        status="Successful",
                        initiated_by="Operator",
                        completed_at=ts,
                        detail=detail,
                    )
                )
                rec_id = payload.recovery_id
            else:
                rec_id = (
                    c.execute(
                        recoveries.insert().values(
                            drone_id=device,
                            alert_id=None,
                            recommended_action=action,
                            recommendation_reason=payload.reason or f"Operator-initiated {action}.",
                            selected_action=action,
                            status="Successful",
                            initiated_by="Operator",
                            simulated=True,
                            created_at=ts,
                            completed_at=ts,
                            detail=detail,
                        )
                    ).inserted_primary_key[0]
                )

            log(c, device, f"Recovery: {action}", detail, "Info", "Recorded", category="Recovery", simulated=True)
            create_alert(
                c,
                device,
                "Recovery Initiated",
                "Low",
                f"[SIMULATED] {action} initiated for {d.name}: {detail}",
                confidence=100.0,
                simulated=True,
            )
            record_audit(c, "operator", "RECOVERY_ACTION", d.code, f"Executed simulated {action}")
            return {"ok": True, "recovery_id": rec_id, "action": action, "status": "Successful", "mode": new_mode}

    @router.get("/deviations")
    def list_deviations(drone_id: Optional[int] = None, severity: Optional[str] = None):
        with engine.connect() as c:
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

    def _in_date_range(ts: str, date_from: Optional[str], date_to: Optional[str]) -> bool:
        day = (ts or "")[:10]
        if date_from and day < date_from:
            return False
        if date_to and day > date_to:
            return False
        return True

    def _build_report_summary(c):
        thresholds = get_thresholds(c)
        all_drones = c.execute(select(drones).order_by(drones.c.id)).mappings().all()
        health_rows = _bulk_health(c, all_drones, thresholds)
        all_samples = c.execute(select(samples)).mappings().all()
        all_alerts = c.execute(select(alerts).order_by(alerts.c.id.desc())).mappings().all()
        all_packets = c.execute(select(network_packets)).mappings().all()
        all_devs = c.execute(select(deviations)).mappings().all()
        all_recs = c.execute(select(recoveries).order_by(recoveries.c.id.desc())).mappings().all()
        blocked_devs = c.execute(select(trusted_devices).where(trusted_devices.c.status == "Blocked")).mappings().all()
        ev = trained()[1]
        attack_counts = Counter(a["attack_type"] for a in all_alerts if a["attack_type"] != "Recovery Initiated")
        return {
            "overview": {
                "total_drones": len(all_drones),
                "active_drones": sum(1 for d in all_drones if d["is_active"] and d["mode"] != "At base"),
                "spoofed_drones": sum(1 for h in health_rows if h["security_status"] == "GPS Spoofed"),
            },
            "drones": health_rows,
            "gps_detection": {
                "normal_count": sum(1 for s in all_samples if s["classification"] == "Normal"),
                "spoofed_count": sum(1 for s in all_samples if s["classification"] == "GPS Spoofed"),
                "deviation_count": len(all_devs),
            },
            "network": {
                "total_packets": len(all_packets),
                "threat_packets": sum(1 for p in all_packets if p["threat_type"] is not None),
                "blocked_devices": len(blocked_devs),
            },
            "attack_stats": dict(attack_counts),
            "alerts": [dict(a) for a in all_alerts[:50]],
            "recoveries": [dict(r) for r in all_recs[:50]],
            "ml_performance": {
                "accuracy": ev["accuracy"],
                "precision": ev["metrics"]["1"]["precision"],
                "recall": ev["metrics"]["1"]["recall"],
                "f1": ev["metrics"]["1"]["f1-score"],
                "confusion_matrix": ev["confusion_matrix"],
                "train": ev["train"],
                "test": ev["test"],
            },
        }

    @router.get("/analytics")
    def analytics(
        drone_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ):
        with engine.connect() as c:
            all_drones = {d.id: d for d in c.execute(select(drones)).mappings()}
            all_alerts = [
                a
                for a in c.execute(select(alerts)).mappings()
                if (drone_id is None or a["drone_id"] == drone_id)
                and _in_date_range(a["created_at"], date_from, date_to)
                and a["attack_type"] != "Recovery Initiated"
            ]
            all_samples = [
                s
                for s in c.execute(select(samples)).mappings()
                if (drone_id is None or s["drone"] == drone_id)
                and _in_date_range(s["time"], date_from, date_to)
            ]
            all_recs = [
                r
                for r in c.execute(select(recoveries)).mappings()
                if (drone_id is None or r["drone_id"] == drone_id)
                and _in_date_range(r["created_at"], date_from, date_to)
            ]
            all_pkts = [
                p
                for p in c.execute(select(network_packets)).mappings()
                if (drone_id is None or p["drone_id"] == drone_id)
                and _in_date_range(p["time"], date_from, date_to)
            ]

            daily = Counter()
            weekly = Counter()
            monthly = Counter()
            for a in all_alerts:
                day = a["created_at"][:10]
                daily[day] += 1
                try:
                    dt = datetime.fromisoformat(a["created_at"].replace("Z", "+00:00"))
                    iso_year, iso_week, _ = dt.isocalendar()
                    weekly[f"{iso_year}-W{iso_week:02d}"] += 1
                    monthly[dt.strftime("%Y-%m")] += 1
                except ValueError:
                    pass

            by_type = Counter(a["attack_type"] for a in all_alerts)
            by_severity = Counter(a["severity"] for a in all_alerts)
            by_drone = Counter(
                all_drones[a["drone_id"]].name if a["drone_id"] in all_drones else "Fleet" for a in all_alerts
            )
            rec_stats = Counter((r["selected_action"] or r["recommended_action"]) for r in all_recs)

            return {
                "daily": [{"label": k, "count": v} for k, v in sorted(daily.items())],
                "weekly": [{"label": k, "count": v} for k, v in sorted(weekly.items())],
                "monthly": [{"label": k, "count": v} for k, v in sorted(monthly.items())],
                "gps_vs_normal": {
                    "Normal": sum(1 for s in all_samples if s["classification"] == "Normal"),
                    "GPS Spoofed": sum(1 for s in all_samples if s["classification"] == "GPS Spoofed"),
                },
                "attack_distribution": [{"label": k, "count": v} for k, v in by_type.most_common()],
                "severity_distribution": [
                    {"label": sev, "count": by_severity.get(sev, 0)}
                    for sev in ("Critical", "High", "Medium", "Low")
                ],
                "drone_attacks": [{"label": k, "count": v} for k, v in by_drone.most_common()],
                "recovery_actions": [{"label": k, "count": v} for k, v in rec_stats.most_common()],
                "network_traffic": {
                    "Inbound": sum(1 for p in all_pkts if p["direction"] == "Inbound"),
                    "Outbound": sum(1 for p in all_pkts if p["direction"] == "Outbound"),
                    "Threats": sum(1 for p in all_pkts if p["threat_type"] is not None),
                },
            }

    @router.get("/logs")
    def unified_logs(
        q: str = Query("", max_length=100),
        drone_id: Optional[int] = None,
        attack_type: Optional[str] = None,
        category: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ):
        with engine.connect() as c:
            all_drones = {d.id: d for d in c.execute(select(drones)).mappings()}
            rows = c.execute(select(events).order_by(events.c.id.desc()).limit(300)).mappings().all()
            needle = q.strip().lower()
            items = []
            for r in rows:
                if drone_id is not None and r["drone"] != drone_id:
                    continue
                if attack_type and r["kind"] != attack_type:
                    continue
                if category and r["category"] != category:
                    continue
                if not _in_date_range(r["time"], date_from, date_to):
                    continue
                d_name = all_drones[r["drone"]].name if r["drone"] in all_drones else f"Drone {r['drone']}"
                if needle and not (
                    needle in r["kind"].lower()
                    or needle in r["detail"].lower()
                    or needle in d_name.lower()
                    or needle in r["status"].lower()
                ):
                    continue
                items.append({**r, "drone_name": d_name})
            kinds = sorted({r["kind"] for r in rows})
            categories = sorted({r["category"] for r in rows})
            return {"items": items, "kinds": kinds, "categories": categories}

    @router.get("/reports/summary")
    def report_summary():
        with engine.connect() as c:
            return _build_report_summary(c)

    @router.get("/reports/export")
    def report_export(format: Literal["pdf", "csv"] = "pdf"):
        with engine.connect() as c:
            summary = _build_report_summary(c)
        if format == "csv":
            csv_data = build_csv_report(summary)
            return Response(
                content=csv_data,
                media_type="text/csv",
                headers={"Content-Disposition": 'attachment; filename="skysentinel-security-report.csv"'},
            )
        pdf_bytes = build_pdf_report(summary)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="skysentinel-security-report.pdf"'},
        )

    @router.get("/admin/settings")
    def get_admin_settings():
        with engine.connect() as c:
            return {"thresholds": get_thresholds(c)}

    @router.put("/admin/settings")
    def update_admin_settings(payload: ThresholdSettings):
        with lock, engine.begin() as c:
            vals = payload.model_dump()
            existing = c.execute(select(system_settings.c.key).where(system_settings.c.key == "thresholds")).scalar()
            if existing:
                c.execute(system_settings.update().where(system_settings.c.key == "thresholds").values(value=vals, updated_at=now()))
            else:
                c.execute(system_settings.insert().values(key="thresholds", value=vals, updated_at=now()))
            record_audit(c, "operator", "UPDATE_THRESHOLDS", "system_settings", f"Updated thresholds: {vals}")
            return {"thresholds": vals}

    @router.get("/admin/audit-logs")
    def get_audit_logs():
        with engine.connect() as c:
            rows = c.execute(select(audit_logs).order_by(audit_logs.c.id.desc()).limit(100)).mappings().all()
            return {"items": rows}

    return router
