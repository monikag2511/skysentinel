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


def test_drone_crud_and_deviations(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'crud.db'}")
    metadata.create_all(engine)
    with TestClient(create_app(engine)) as client:
        created = client.post(
            "/api/drones",
            json={
                "name": "Delta-Hawk",
                "code": "DRN-009",
                "model_type": "Hexacopter",
                "battery": 88.0,
                "altitude": 140.0,
                "base_lat": 13.05,
                "base_lon": 80.215,
            },
        )
        assert created.status_code == 201, created.text
        d_id = created.json()["id"]
        assert created.json()["code"] == "DRN-009"

        listed = client.get("/api/drones", params={"q": "Delta"}).json()["items"]
        assert len(listed) == 1 and listed[0]["id"] == d_id

        updated = client.put(f"/api/drones/{d_id}", json={"name": "Delta-Hawk-II", "battery": 77.5})
        assert updated.is_success and updated.json()["name"] == "Delta-Hawk-II"

        # Trigger GPS spoofing -> should record flight path deviation
        gps_cmd = client.post(f"/api/drones/{d_id}/commands", json={"action": "gps"})
        assert gps_cmd.is_success
        devs = client.get("/api/deviations", params={"drone_id": d_id}).json()["items"]
        assert len(devs) >= 1
        assert devs[0]["distance_m"] > 150.0

        deleted = client.delete(f"/api/drones/{d_id}")
        assert deleted.is_success
        assert client.get(f"/api/drones/{d_id}/report").status_code == 404
