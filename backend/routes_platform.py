from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from db import alerts, deviations, drones, events, network_packets, recoveries, samples
from service import get_thresholds


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
            recent_net_threat and recent_net_threat["auth_status"] in ("Unknown Device", "Integrity Failed", "Blocked", "MITM Suspected")
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
                    if any(a["attack_type"] in ("GPS Spoofing", "Flight Path Deviation") and a["status"] == "Active" for a in all_alerts)
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

    return router
