"""Initial flight watch schema."""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None


def upgrade():
    op.create_table("drones", sa.Column("id", sa.Integer, primary_key=True, autoincrement=False),
                    sa.Column("name", sa.String, nullable=False), sa.Column("mode", sa.String, nullable=False),
                    sa.Column("seq", sa.Integer, nullable=False), sa.Column("streak", sa.Integer, nullable=False),
                    sa.Column("trusted", sa.JSON, nullable=False))
    op.create_table("telemetry", sa.Column("id", sa.Integer, primary_key=True),
                    sa.Column("drone", sa.Integer, sa.ForeignKey("drones.id"), nullable=False),
                    sa.Column("seq", sa.Integer, nullable=False), sa.Column("time", sa.String, nullable=False),
                    sa.Column("reading", sa.JSON, nullable=False), sa.Column("expected", sa.JSON, nullable=False),
                    sa.Column("score", sa.Float, nullable=False), sa.UniqueConstraint("drone", "seq"))
    op.create_table("events", sa.Column("id", sa.Integer, primary_key=True),
                    sa.Column("drone", sa.Integer, sa.ForeignKey("drones.id"), nullable=False),
                    sa.Column("time", sa.String, nullable=False), sa.Column("kind", sa.String, nullable=False),
                    sa.Column("severity", sa.String, nullable=False), sa.Column("detail", sa.String, nullable=False),
                    sa.Column("status", sa.String, nullable=False), sa.Column("score", sa.Float),
                    sa.Column("incident", sa.Integer, sa.ForeignKey("events.id")))


def downgrade():
    for name in ("events", "telemetry", "drones"):
        op.drop_table(name)
