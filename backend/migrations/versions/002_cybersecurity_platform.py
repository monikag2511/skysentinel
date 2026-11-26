"""Expand schema for SkySentinel cybersecurity platform."""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"


def upgrade():
    op.add_column("drones", sa.Column("code", sa.String, nullable=False, server_default="DRN-000"))
    op.add_column("drones", sa.Column("model_type", sa.String, nullable=False, server_default="Autonomous UAV"))
    op.add_column("drones", sa.Column("battery", sa.Float, nullable=False, server_default="94.0"))
    op.add_column("drones", sa.Column("altitude", sa.Float, nullable=False, server_default="120.0"))
    op.add_column("drones", sa.Column("gps_status", sa.String, nullable=False, server_default="Connected"))
    op.add_column("drones", sa.Column("comm_status", sa.String, nullable=False, server_default="Encrypted"))
    op.add_column("drones", sa.Column("sensor_status", sa.String, nullable=False, server_default="Nominal"))
    op.add_column("drones", sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()))
    op.add_column("drones", sa.Column("base_lat", sa.Float, nullable=False, server_default="13.046"))
    op.add_column("drones", sa.Column("base_lon", sa.Float, nullable=False, server_default="80.205"))
    op.add_column("drones", sa.Column("route_config", sa.JSON, nullable=True))
    op.add_column("drones", sa.Column("created_at", sa.String, nullable=False, server_default=""))

    op.add_column("telemetry", sa.Column("altitude", sa.Float, nullable=False, server_default="120.0"))
    op.add_column("telemetry", sa.Column("battery", sa.Float, nullable=False, server_default="94.0"))
    op.add_column("telemetry", sa.Column("classification", sa.String, nullable=False, server_default="Normal"))
    op.add_column("telemetry", sa.Column("confidence", sa.Float, nullable=False, server_default="0.0"))
    op.add_column("telemetry", sa.Column("severity", sa.String, nullable=False, server_default="Low"))
    op.add_column(
        "telemetry",
        sa.Column("reason", sa.String, nullable=False, server_default="Nominal telemetry within expected flight corridor."),
    )
    op.add_column("telemetry", sa.Column("deviation_m", sa.Float, nullable=False, server_default="0.0"))
    op.add_column("telemetry", sa.Column("simulated", sa.Boolean, nullable=False, server_default=sa.false()))

    op.add_column("events", sa.Column("category", sa.String, nullable=False, server_default="Telemetry"))
    op.add_column("events", sa.Column("simulated", sa.Boolean, nullable=False, server_default=sa.false()))

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("alert_code", sa.String, nullable=False),
        sa.Column("drone_id", sa.Integer, sa.ForeignKey("drones.id"), nullable=True),
        sa.Column("attack_type", sa.String, nullable=False),
        sa.Column("severity", sa.String, nullable=False),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("created_at", sa.String, nullable=False),
        sa.Column("description", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="Active"),
        sa.Column("simulated", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("source_event_id", sa.Integer, sa.ForeignKey("events.id"), nullable=True),
        sa.Column("details", sa.JSON, nullable=True),
    )
    op.create_table(
        "deviations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("drone_id", sa.Integer, sa.ForeignKey("drones.id"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("time", sa.String, nullable=False),
        sa.Column("expected_lat", sa.Float, nullable=False),
        sa.Column("expected_lon", sa.Float, nullable=False),
        sa.Column("detected_lat", sa.Float, nullable=False),
        sa.Column("detected_lon", sa.Float, nullable=False),
        sa.Column("distance_m", sa.Float, nullable=False),
        sa.Column("threshold_m", sa.Float, nullable=False),
        sa.Column("jump_m", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("severity", sa.String, nullable=False),
        sa.Column("simulated", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.String, nullable=False),
    )
    op.create_table(
        "network_packets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("drone_id", sa.Integer, sa.ForeignKey("drones.id"), nullable=True),
        sa.Column("time", sa.String, nullable=False),
        sa.Column("direction", sa.String, nullable=False),
        sa.Column("src_addr", sa.String, nullable=False),
        sa.Column("dst_addr", sa.String, nullable=False),
        sa.Column("device_uid", sa.String, nullable=False),
        sa.Column("packet_size", sa.Integer, nullable=False),
        sa.Column("protocol", sa.String, nullable=False, server_default="AES-256-GCM/UDP"),
        sa.Column("encrypted", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("auth_status", sa.String, nullable=False),
        sa.Column("threat_type", sa.String, nullable=True),
        sa.Column("simulated", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("detail", sa.String, nullable=False),
    )
    op.create_table(
        "trusted_devices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("device_uid", sa.String, nullable=False, unique=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("ip_address", sa.String, nullable=False),
        sa.Column("mac_address", sa.String, nullable=False),
        sa.Column("drone_id", sa.Integer, sa.ForeignKey("drones.id"), nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="Trusted"),
        sa.Column("last_seen", sa.String, nullable=False),
    )
    op.create_table(
        "recoveries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("drone_id", sa.Integer, sa.ForeignKey("drones.id"), nullable=False),
        sa.Column("alert_id", sa.Integer, sa.ForeignKey("alerts.id"), nullable=True),
        sa.Column("recommended_action", sa.String, nullable=False),
        sa.Column("recommendation_reason", sa.String, nullable=False),
        sa.Column("selected_action", sa.String, nullable=True),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("initiated_by", sa.String, nullable=False),
        sa.Column("simulated", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.String, nullable=False),
        sa.Column("completed_at", sa.String, nullable=True),
        sa.Column("detail", sa.String, nullable=False),
    )
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String, primary_key=True),
        sa.Column("value", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.String, nullable=False),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("time", sa.String, nullable=False),
        sa.Column("actor", sa.String, nullable=False),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("target", sa.String, nullable=False),
        sa.Column("detail", sa.String, nullable=False),
    )


def downgrade():
    for table in (
        "audit_logs",
        "system_settings",
        "recoveries",
        "trusted_devices",
        "network_packets",
        "deviations",
        "alerts",
    ):
        op.drop_table(table)
    op.drop_column("events", "simulated")
    op.drop_column("events", "category")
    for col in ("simulated", "deviation_m", "reason", "severity", "confidence", "classification", "battery", "altitude"):
        op.drop_column("telemetry", col)
    for col in (
        "created_at",
        "route_config",
        "base_lon",
        "base_lat",
        "is_active",
        "sensor_status",
        "comm_status",
        "gps_status",
        "altitude",
        "battery",
        "model_type",
        "code",
    ):
        op.drop_column("drones", col)
