import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from db import metadata
from production import production_app


def test_production_access_archive_and_health(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'store.db'}")
    metadata.create_all(engine)
    (tmp_path / "index.html").write_text("Flight watch", encoding="utf-8")
    monkeypatch.delenv("SKY_OPERATOR_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="SKY_OPERATOR_PASSWORD"):
        production_app(engine, tmp_path)
    roles = {r: (r, r * 5) for r in ("viewer", "operator")}
    for role, (_, password) in roles.items():
        monkeypatch.setenv(f"SKY_{role.upper()}_PASSWORD", password)
    with TestClient(production_app(engine, tmp_path)) as client:
        assert client.get("/health/ready").is_success
        for path in ("/", "/api/archive", "/api/watch", "/api/evaluation"):
            assert client.get(path).status_code == 401
        assert client.get("/", auth=("operator", "incorrect")).status_code == 401
        assert client.get("/", auth=roles["viewer"]).text == "Flight watch"
        view = client.get("/api/watch", auth=roles["viewer"])
        assert view.json()["role"] == "viewer"
        assert view.headers["cache-control"] == "private, no-store"
        url = "/api/drones/0/commands"
        body = {"action":"duplicate"}
        header = {"X-Sky-Command":"1"}
        assert client.post(url, json=body, auth=roles["viewer"], headers=header).status_code == 403
        assert client.post(url, json=body, auth=roles["operator"]).status_code == 403
        assert client.post(url, json=body, auth=roles["operator"], headers=header).is_success
        def search(params):
            return client.get("/api/archive", params=params, auth=roles["viewer"]).json()
        assert search({"q":"alpha", "severity":"Medium"})["items"][0]["kind"] == "Duplicate sequence"
        assert search({"q":"%"})["items"] == []
        first = search({"limit":2})
        second = search({"limit":2,"before":first["next"]})
        assert len(first["items"]) == len(second["items"]) == 2
        assert first["items"][-1]["id"] > second["items"][0]["id"]
        assert second["next"] is None
