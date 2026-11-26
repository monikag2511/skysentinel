from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from db import metadata
from main import create_app


def test_dashboard_and_drone_report(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'platform.db'}")
    metadata.create_all(engine)
    with TestClient(create_app(engine)) as client:
        dash = client.get("/api/dashboard")
        assert dash.is_success, dash.text
        body = dash.json()
        assert body["stats"]["total_registered"] == 3
        assert body["stats"]["active_drones"] == 3
        assert len(body["drone_health"]) == 3
        rep = client.get("/api/drones/0/report")
        assert rep.is_success, rep.text
        assert rep.json()["drone"]["name"] == "Alpha-Wing"
        assert len(rep.json()["telemetry"]) >= 1
