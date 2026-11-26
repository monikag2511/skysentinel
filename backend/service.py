import json
import os
import random
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
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
from model import FEATURES, MODEL_TYPES, NAMES, haversine_m, position, reading, trained

DEFAULT_THRESHOLDS = {
    "deviation_threshold_m": 150.0,
    "spoof_score_threshold": 0.5,
    "speed_threshold_kmh": 45.0,
    "accel_threshold_ms2": 3.5,
    "rate_limit_per_sec": 8,
    "low_battery_pct": 25.0,
}


def now():
    return datetime.now(timezone.utc).isoformat()


def log(
    c,
    device,
    kind,
    detail,
    severity="Info",
    status="Recorded",
    score=None,
    incident=None,
    category="Telemetry",
    simulated=False,
):
    return (
        c.execute(
            events.insert().values(
                drone=device,
                time=now(),
                kind=kind,
                detail=detail,
                severity=severity,
                status=status,
                score=score,
                incident=incident,
                category=category,
                simulated=simulated,
            )
        ).inserted_primary_key[0]
    )


def get_thresholds(c) -> dict:
    row = c.execute(select(system_settings.c.value).where(system_settings.c.key == "thresholds")).scalar()
    merged = dict(DEFAULT_THRESHOLDS)
    if isinstance(row, dict):
        merged.update(row)
    return merged


def create_alert(
    c,
    drone_id,
    attack_type,
    severity,
    description,
    confidence=None,
    simulated=False,
    source_event_id=None,
    details=None,
):
    ts = now()
    row_id = (
        c.execute(
            alerts.insert().values(
                alert_code="ALT-PENDING",
                drone_id=drone_id,
                attack_type=attack_type,
                severity=severity,
                confidence=confidence,
                created_at=ts,
                description=description,
                status="Active",
                simulated=simulated,
                source_event_id=source_event_id,
                details=details,
            )
        ).inserted_primary_key[0]
    )
    code = f"ALT-{row_id:04d}"
    c.execute(alerts.update().where(alerts.c.id == row_id).values(alert_code=code))
    return row_id


def record_audit(c, actor: str, action: str, target: str, detail: str):
    c.execute(
        audit_logs.insert().values(
            time=now(),
            actor=actor,
            action=action,
            target=target,
            detail=detail,
        )
    )


class FlightWatch:
    def __init__(self):
        self.keys = {i: AESGCM(AESGCM.generate_key(bit_length=256)) for i in range(3)}
        self.arrivals = defaultdict(deque)

    def ensure_key(self, device_id: int):
        if device_id not in self.keys:
            self.keys[device_id] = AESGCM(AESGCM.generate_key(bit_length=256))

    def seed(self, c):
        if not c.execute(select(system_settings.c.key).where(system_settings.c.key == "thresholds")).scalar():
            c.execute(
                system_settings.insert().values(
                    key="thresholds",
                    value=dict(DEFAULT_THRESHOLDS),
                    updated_at=now(),
                )
            )
        if not c.execute(select(trusted_devices.c.id).where(trusted_devices.c.device_uid == "GCS-CTRL-01")).scalar():
            c.execute(
                trusted_devices.insert().values(
                    device_uid="GCS-CTRL-01",
                    name="Ground Control Station Primary",
                    ip_address="10.42.0.1",
                    mac_address="00:1A:7D:DA:71:01",
                    drone_id=None,
                    status="Trusted",
                    last_seen=now(),
                )
            )
        for i, name in enumerate(NAMES):
            self.ensure_key(i)
            if not c.scalar(select(drones.c.name).where(drones.c.id == i)):
                base_lat = 13.046 + i * 0.001
                base_lon = 80.205 + i * 0.003
                code = f"DRN-{i + 1:03d}"
                c.execute(
                    drones.insert().values(
                        id=i,
                        name=name,
                        mode="Patrol",
                        seq=0,
                        streak=0,
                        trusted=list(position(i, 0, base_lat=base_lat, base_lon=base_lon)),
                        code=code,
                        model_type=MODEL_TYPES[i],
                        battery=96.0 - i * 3.0,
                        altitude=120.0 + i * 15.0,
                        gps_status="Connected",
                        comm_status="Encrypted",
                        sensor_status="Nominal",
                        is_active=True,
                        base_lat=base_lat,
                        base_lon=base_lon,
                        route_config=None,
                        created_at=now(),
                    )
                )
                c.execute(
                    trusted_devices.insert().values(
                        device_uid=f"UAV-LINK-{i + 1:03d}",
                        name=f"{name} Transceiver",
                        ip_address=f"10.42.1.{10 + i}",
                        mac_address=f"02:53:4B:00:0{i + 1}:11",
                        drone_id=i,
                        status="Trusted",
                        last_seen=now(),
                    )
                )
                self.advance(c, i)
                log(c, i, "Flight online", "Authenticated telemetry established.", category="System")

    def seal(self, device, seq, row):
        self.ensure_key(device)
        nonce = os.urandom(12)
        header = f"{device}/{seq}".encode()
        return nonce, self.keys[device].encrypt(nonce, json.dumps(row).encode(), header)

    def _record_packet(
        self,
        c,
        drone_id,
        device_uid,
        packet_size,
        encrypted,
        auth_status,
        detail,
        threat_type=None,
        simulated=False,
        src_addr=None,
        direction="Inbound",
    ):
        src = src_addr or f"10.42.1.{10 + (drone_id or 90)}"
        c.execute(
            network_packets.insert().values(
                drone_id=drone_id,
                time=now(),
                direction=direction,
                src_addr=src,
                dst_addr="10.42.0.1:8443",
                device_uid=device_uid,
                packet_size=packet_size,
                protocol="AES-256-GCM/UDP" if encrypted else "RAW/UDP",
                encrypted=encrypted,
                auth_status=auth_status,
                threat_type=threat_type,
                simulated=simulated,
                detail=detail,
            )
        )

    def receive(self, c, drone, sender, seq, envelope, arrived=None, simulated=False):
        device = drone["id"]
        self.ensure_key(device)
        thresholds = get_thresholds(c)
        nonce, payload = envelope
        pkt_size = len(nonce) + len(payload) + 28
        sender_uid = f"UAV-LINK-{sender + 1:03d}" if sender >= 0 else "UNKNOWN-NODE-FF"

        # Check trusted device list for blocks
        dev_row = c.execute(
            select(trusted_devices).where(trusted_devices.c.device_uid == sender_uid)
        ).mappings().first()
        if dev_row and dev_row["status"] == "Blocked":
            self._record_packet(
                c,
                device,
                sender_uid,
                pkt_size,
                False,
                "Blocked",
                f"Traffic blocked from {sender_uid}.",
                threat_type="Unauthorized Device",
                simulated=simulated,
                src_addr=dev_row["ip_address"],
            )
            return "Blocked device"

        if sender != device or sender not in self.keys:
            self._record_packet(
                c,
                device,
                sender_uid,
                pkt_size,
                False,
                "Unknown Device",
                f"Rejected unauthenticated sender {sender_uid} targeting drone {device}.",
                threat_type="Unauthorized Access",
                simulated=simulated,
                src_addr="192.168.99.204",
            )
            return "Unknown sender"
        try:
            raw = self.keys[sender].decrypt(nonce, payload, f"{sender}/{seq}".encode())
        except InvalidTag:
            self._record_packet(
                c,
                device,
                sender_uid,
                pkt_size,
                True,
                "Integrity Failed",
                "AES-GCM authentication tag verification failed (tampered payload).",
                threat_type="Packet Injection",
                simulated=simulated,
            )
            return "Integrity failure"
        if seq <= drone["seq"]:
            self._record_packet(
                c,
                device,
                sender_uid,
                pkt_size,
                True,
                "Replay Detected",
                f"Duplicate sequence {seq} <= current {drone['seq']}.",
                threat_type="Replay Attack",
                simulated=simulated,
            )
            return "Duplicate sequence"
        times = self.arrivals[device]
        clock = time.monotonic() if arrived is None else arrived
        while times and times[0] <= clock - 1:
            times.popleft()
        if len(times) >= int(thresholds["rate_limit_per_sec"]):
            self._record_packet(
                c,
                device,
                sender_uid,
                pkt_size,
                True,
                "Rate Exceeded",
                "Packet burst exceeded per-second rate limit.",
                threat_type="Suspicious Traffic",
                simulated=simulated,
            )
            return "Rate limit"

        row = json.loads(raw)
        score = float(trained()[0].predict_proba([[row[f] for f in FEATURES]])[0, 1])
        expected = position(
            device,
            seq,
            base_lat=drone.get("base_lat"),
            base_lon=drone.get("base_lon"),
            route_config=drone.get("route_config"),
        )
        distance_m = haversine_m(expected[0], expected[1], row["latitude"], row["longitude"])
        prev_sample = (
            c.execute(samples.select().where(samples.c.drone == device).order_by(samples.c.seq.desc()).limit(1))
            .mappings()
            .first()
        )
        jump_m = (
            haversine_m(
                prev_sample["reading"]["latitude"],
                prev_sample["reading"]["longitude"],
                row["latitude"],
                row["longitude"],
            )
            if prev_sample
            else 0.0
        )

        reasons = []
        if score >= float(thresholds["spoof_score_threshold"]):
            reasons.append(f"ML classifier confidence {score * 100:.1f}% indicates GPS spoofing")
        if distance_m > float(thresholds["deviation_threshold_m"]):
            reasons.append(f"Route deviation {distance_m:.1f}m exceeds {thresholds['deviation_threshold_m']:.0f}m threshold")
        if row["speed"] > float(thresholds["speed_threshold_kmh"]):
            reasons.append(f"Abnormal velocity {row['speed']:.1f} km/h vs IMU corridor")
        if row["acceleration"] > float(thresholds["accel_threshold_ms2"]):
            reasons.append(f"IMU acceleration spike {row['acceleration']:.2f} m/s^2")
        if row["signal"] < 75.0:
            reasons.append(f"Suspicious GPS signal drop ({row['signal']:.1f}%)")
        if jump_m > max(float(thresholds["deviation_threshold_m"]) * 1.3, 200.0):
            reasons.append(f"Sudden GPS position jump of {jump_m:.1f}m")

        coord_delta = max(abs(row[f] - v) for f, v in zip(FEATURES, expected))
        suspect = score >= float(thresholds["spoof_score_threshold"]) or coord_delta > 0.0015 or distance_m > float(
            thresholds["deviation_threshold_m"]
        )
        classification = "GPS Spoofed" if suspect else "Normal"
        confidence = score if suspect else (1.0 - score)
        severity = (
            "Critical"
            if (suspect and (score >= 0.85 or distance_m >= 300.0))
            else "High"
            if suspect
            else "Low"
        )
        reason_text = "; ".join(reasons) if reasons else "Nominal telemetry matches IMU and planned corridor."

        streak = drone["streak"] + 1 if suspect else 0
        mode = drone["mode"]
        gps_status = "Spoofed" if (suspect and streak >= 2) else ("Degraded" if suspect else "Connected")
        sensor_status = "Irregular" if (row["acceleration"] > float(thresholds["accel_threshold_ms2"]) or suspect) else "Nominal"
        next_battery = max(5.0, float(drone.get("battery", 94.0)) - 0.15)
        next_altitude = round(float(drone.get("altitude", 120.0)) + (1.2 if suspect else 0.0), 1)

        if distance_m > float(thresholds["deviation_threshold_m"]) or jump_m > max(
            float(thresholds["deviation_threshold_m"]) * 1.3, 200.0
        ):
            c.execute(
                deviations.insert().values(
                    drone_id=device,
                    seq=seq,
                    time=now(),
                    expected_lat=expected[0],
                    expected_lon=expected[1],
                    detected_lat=row["latitude"],
                    detected_lon=row["longitude"],
                    distance_m=round(distance_m, 2),
                    threshold_m=float(thresholds["deviation_threshold_m"]),
                    jump_m=round(jump_m, 2),
                    severity=severity if suspect else "Medium",
                    simulated=simulated,
                    reason=reason_text,
                )
            )

        if streak >= 2 and mode == "Patrol":
            mode = "Attitude hold"
            incident = log(
                c,
                device,
                "GPS deviation",
                f"Two consecutive suspect fixes. {reason_text}",
                "High",
                "Open",
                score,
                category="GPS Spoofing",
                simulated=simulated,
            )
            log(
                c,
                device,
                "Attitude hold",
                "Simulator holds the last trusted fix.",
                incident=incident,
                category="Recovery",
                simulated=simulated,
            )
            alert_id = create_alert(
                c,
                device,
                "GPS Spoofing",
                "Critical" if score >= 0.85 else "High",
                f"{drone['name']} entered Attitude hold after consecutive spoofed GPS fixes ({reason_text}).",
                confidence=round(score * 100, 1),
                simulated=simulated,
                source_event_id=incident,
                details={"distance_m": round(distance_m, 1), "score": round(score, 4), "seq": seq},
            )
            c.execute(
                recoveries.insert().values(
                    drone_id=device,
                    alert_id=alert_id,
                    recommended_action="Return to Home",
                    recommendation_reason=f"Sustained GPS spoofing ({distance_m:.1f}m offset, {score * 100:.1f}% ML confidence). Autonomous RTH preserves trusted corridor.",
                    selected_action=None,
                    status="Recommended",
                    initiated_by="Autonomous Advisor",
                    simulated=True,
                    created_at=now(),
                    completed_at=None,
                    detail="Awaiting operator confirmation or autonomous execution.",
                )
            )

        self._record_packet(
            c,
            device,
            sender_uid,
            pkt_size,
            True,
            "Authenticated",
            f"AES-256-GCM telemetry seq {seq} verified ({classification}).",
            threat_type="GPS Spoofing" if suspect else None,
            simulated=simulated,
        )
        if dev_row:
            c.execute(trusted_devices.update().where(trusted_devices.c.id == dev_row["id"]).values(last_seen=now()))

        c.execute(
            samples.insert().values(
                drone=device,
                seq=seq,
                time=now(),
                reading=row,
                expected=list(expected),
                score=score,
                altitude=next_altitude,
                battery=round(next_battery, 2),
                classification=classification,
                confidence=round(confidence * 100, 2),
                severity=severity,
                reason=reason_text,
                deviation_m=round(distance_m, 2),
                simulated=simulated,
            )
        )
        c.execute(
            drones.update()
            .where(drones.c.id == device)
            .values(
                seq=seq,
                mode=mode,
                streak=streak,
                battery=round(next_battery, 2),
                altitude=next_altitude,
                gps_status=gps_status,
                comm_status="Encrypted",
                sensor_status=sensor_status,
                trusted=drone["trusted"] if suspect or mode != "Patrol" else [row["latitude"], row["longitude"]],
            )
        )
        times.append(clock)
        return None

    def advance(self, c, device, case="normal", arrived=None, simulated=False):
        drone = c.execute(select(drones).where(drones.c.id == device).with_for_update()).mappings().one()
        seq = drone["seq"] + (case != "duplicate")
        row = reading(
            device,
            seq,
            case == "gps",
            random.Random(device * 100000 + seq),
            base_lat=drone.get("base_lat"),
            base_lon=drone.get("base_lon"),
            route_config=drone.get("route_config"),
        )
        nonce, data = self.seal(device, seq, row)
        if case == "integrity":
            data = data[:-1] + bytes([data[-1] ^ 1])
        error = self.receive(
            c,
            drone,
            -1 if case == "unknown" else device,
            seq,
            (nonce, data),
            arrived,
            simulated=simulated,
        )
        if error:
            ev_id = log(
                c,
                device,
                error,
                "Message rejected before telemetry update.",
                "Medium",
                "Open",
                category="Network",
                simulated=simulated,
            )
            create_alert(
                c,
                device,
                error,
                "High" if error in ("Integrity failure", "Unknown sender", "Blocked device") else "Medium",
                f"{drone['name']}: {error} rejected before telemetry update.",
                confidence=95.0,
                simulated=simulated,
                source_event_id=ev_id,
                details={"seq": seq, "case": case},
            )
        return error
