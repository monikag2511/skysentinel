from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from db import metadata
from main import create_app


def test_operator_journey(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'flight.db'}")
    metadata.create_all(engine)
    with TestClient(create_app(engine)) as client:
        watch = lambda: client.get("/api/watch").json()
        def run(action, **kw):
            r = client.post("/api/drones/0/commands", json={"action":action, **kw})
            assert r.is_success, r.text
        fleet = watch()["fleet"]
        assert len(fleet) == 3
        for action, kind in [("unknown","Unknown sender"), ("duplicate","Duplicate sequence"), ("integrity","Integrity failure")]:
            run(action)
            state = watch()
            assert state["fleet"][0]["seq"] == fleet[0]["seq"]
            assert state["history"][0]["kind"] == kind
        run("normal")
        trusted = watch()["fleet"][0]["trusted"]
        run("gps")
        state = watch()
        assert state["fleet"][0]["mode"] == "Attitude hold"
        assert state["fleet"][0]["trusted"] == trusted
        gps = [e for e in state["history"] if e["kind"] == "GPS deviation"]
        assert len(gps) == 1
        run("ack", incident=gps[0]["id"])
        run("home")
        assert watch()["fleet"][0]["mode"] == "At base"
        run("resume")
        run("rate")
        assert watch()["history"][0]["kind"] == "Rate limit"
        assert client.post("/api/drones/0/commands",json={"action":"home"}).status_code == 409
        assert client.post("/api/drones/99/commands",json={"action":"normal"}).status_code == 404
        metrics = client.get("/api/evaluation").json()
        assert metrics["train"] == 1600 and metrics["test"] == 400
        assert sum(map(sum,metrics["confusion_matrix"])) == 400
        last = watch()
    with TestClient(create_app(engine)) as restarted:
        assert restarted.get("/api/watch").json() == last
