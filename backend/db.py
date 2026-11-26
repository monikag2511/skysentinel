from pathlib import Path
import os
from dotenv import load_dotenv
from sqlalchemy import (Column, Integer, String, Float, JSON, ForeignKey, MetaData,
                        Table, UniqueConstraint, create_engine)

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")
metadata = MetaData()
drones = Table("drones", metadata, Column("id", Integer, primary_key=True, autoincrement=False),
               Column("name", String, nullable=False), Column("mode", String, nullable=False),
               Column("seq", Integer, nullable=False), Column("streak", Integer, nullable=False),
               Column("trusted", JSON, nullable=False))
samples = Table("telemetry", metadata, Column("id", Integer, primary_key=True),
                Column("drone", ForeignKey("drones.id"), nullable=False),
                Column("seq", Integer, nullable=False), Column("time", String, nullable=False),
                Column("reading", JSON, nullable=False), Column("expected", JSON, nullable=False),
                Column("score", Float, nullable=False), UniqueConstraint("drone", "seq"))
events = Table("events", metadata, Column("id", Integer, primary_key=True),
               Column("drone", ForeignKey("drones.id"), nullable=False),
               Column("time", String, nullable=False), Column("kind", String, nullable=False),
               Column("severity", String, nullable=False), Column("detail", String, nullable=False),
               Column("status", String, nullable=False), Column("score", Float),
               Column("incident", ForeignKey("events.id")))


def database(migrations=False):
    url = (os.getenv("MIGRATION_DATABASE_URL") if migrations else None) or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("Set DATABASE_URL in backend/.env (see .env.example).")
    if url.startswith(("postgres://", "postgresql://")):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    options = {"connect_timeout": 8} if url.startswith("postgresql") else {}
    return create_engine(url, pool_pre_ping=True, hide_parameters=True, connect_args=options)
