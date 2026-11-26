from pathlib import Path
import os
from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    JSON,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    false,
    true,
)

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")
metadata = MetaData()

drones = Table(
    "drones",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=False),
    Column("name", String, nullable=False),
    Column("mode", String, nullable=False),
    Column("seq", Integer, nullable=False),
    Column("streak", Integer, nullable=False),
    Column("trusted", JSON, nullable=False),
    Column("code", String, nullable=False, server_default="DRN-000"),
    Column("model_type", String, nullable=False, server_default="Autonomous UAV"),
    Column("battery", Float, nullable=False, server_default="94.0"),
    Column("altitude", Float, nullable=False, server_default="120.0"),
    Column("gps_status", String, nullable=False, server_default="Connected"),
    Column("comm_status", String, nullable=False, server_default="Encrypted"),
    Column("sensor_status", String, nullable=False, server_default="Nominal"),
    Column("is_active", Boolean, nullable=False, server_default=true()),
    Column("base_lat", Float, nullable=False, server_default="13.046"),
    Column("base_lon", Float, nullable=False, server_default="80.205"),
    Column("route_config", JSON, nullable=True),
    Column("created_at", String, nullable=False, server_default=""),
)

samples = Table(
    "telemetry",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("drone", ForeignKey("drones.id"), nullable=False),
    Column("seq", Integer, nullable=False),
    Column("time", String, nullable=False),
    Column("reading", JSON, nullable=False),
    Column("expected", JSON, nullable=False),
    Column("score", Float, nullable=False),
    Column("altitude", Float, nullable=False, server_default="120.0"),
    Column("battery", Float, nullable=False, server_default="94.0"),
    Column("classification", String, nullable=False, server_default="Normal"),
    Column("confidence", Float, nullable=False, server_default="0.0"),
    Column("severity", String, nullable=False, server_default="Low"),
    Column("reason", String, nullable=False, server_default="Nominal telemetry within expected flight corridor."),
    Column("deviation_m", Float, nullable=False, server_default="0.0"),
    Column("simulated", Boolean, nullable=False, server_default=false()),
    UniqueConstraint("drone", "seq"),
)

events = Table(
    "events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("drone", ForeignKey("drones.id"), nullable=False),
    Column("time", String, nullable=False),
    Column("kind", String, nullable=False),
    Column("severity", String, nullable=False),
    Column("detail", String, nullable=False),
    Column("status", String, nullable=False),
    Column("score", Float),
    Column("incident", ForeignKey("events.id")),
    Column("category", String, nullable=False, server_default="Telemetry"),
    Column("simulated", Boolean, nullable=False, server_default=false()),
)

alerts = Table(
    "alerts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("alert_code", String, nullable=False),
    Column("drone_id", ForeignKey("drones.id"), nullable=True),
    Column("attack_type", String, nullable=False),
    Column("severity", String, nullable=False),
    Column("confidence", Float, nullable=True),
    Column("created_at", String, nullable=False),
    Column("description", String, nullable=False),
    Column("status", String, nullable=False, server_default="Active"),
    Column("simulated", Boolean, nullable=False, server_default=false()),
    Column("source_event_id", ForeignKey("events.id"), nullable=True),
    Column("details", JSON, nullable=True),
)

deviations = Table(
    "deviations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("drone_id", ForeignKey("drones.id"), nullable=False),
    Column("seq", Integer, nullable=False),
    Column("time", String, nullable=False),
    Column("expected_lat", Float, nullable=False),
    Column("expected_lon", Float, nullable=False),
    Column("detected_lat", Float, nullable=False),
    Column("detected_lon", Float, nullable=False),
    Column("distance_m", Float, nullable=False),
    Column("threshold_m", Float, nullable=False),
    Column("jump_m", Float, nullable=False, server_default="0.0"),
    Column("severity", String, nullable=False),
    Column("simulated", Boolean, nullable=False, server_default=false()),
    Column("reason", String, nullable=False),
)

network_packets = Table(
    "network_packets",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("drone_id", ForeignKey("drones.id"), nullable=True),
    Column("time", String, nullable=False),
    Column("direction", String, nullable=False),
    Column("src_addr", String, nullable=False),
    Column("dst_addr", String, nullable=False),
    Column("device_uid", String, nullable=False),
    Column("packet_size", Integer, nullable=False),
    Column("protocol", String, nullable=False, server_default="AES-256-GCM/UDP"),
    Column("encrypted", Boolean, nullable=False, server_default=true()),
    Column("auth_status", String, nullable=False),
    Column("threat_type", String, nullable=True),
    Column("simulated", Boolean, nullable=False, server_default=false()),
    Column("detail", String, nullable=False),
)

trusted_devices = Table(
    "trusted_devices",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("device_uid", String, nullable=False, unique=True),
    Column("name", String, nullable=False),
    Column("ip_address", String, nullable=False),
    Column("mac_address", String, nullable=False),
    Column("drone_id", ForeignKey("drones.id"), nullable=True),
    Column("status", String, nullable=False, server_default="Trusted"),
    Column("last_seen", String, nullable=False),
)

recoveries = Table(
    "recoveries",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("drone_id", ForeignKey("drones.id"), nullable=False),
    Column("alert_id", ForeignKey("alerts.id"), nullable=True),
    Column("recommended_action", String, nullable=False),
    Column("recommendation_reason", String, nullable=False),
    Column("selected_action", String, nullable=True),
    Column("status", String, nullable=False),
    Column("initiated_by", String, nullable=False),
    Column("simulated", Boolean, nullable=False, server_default=true()),
    Column("created_at", String, nullable=False),
    Column("completed_at", String, nullable=True),
    Column("detail", String, nullable=False),
)

system_settings = Table(
    "system_settings",
    metadata,
    Column("key", String, primary_key=True),
    Column("value", JSON, nullable=False),
    Column("updated_at", String, nullable=False),
)

audit_logs = Table(
    "audit_logs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("time", String, nullable=False),
    Column("actor", String, nullable=False),
    Column("action", String, nullable=False),
    Column("target", String, nullable=False),
    Column("detail", String, nullable=False),
)


def database(migrations=False):
    url = (os.getenv("MIGRATION_DATABASE_URL") if migrations else None) or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("Set DATABASE_URL in backend/.env (see .env.example).")
    if url.startswith(("postgres://", "postgresql://")):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    options = {"connect_timeout": 8} if url.startswith("postgresql") else {}
    return create_engine(url, pool_pre_ping=True, hide_parameters=True, connect_args=options)
