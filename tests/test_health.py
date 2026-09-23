from fastapi.testclient import TestClient

from config import Settings
from main import build_app


def test_health_ok(tmp_path):
    client = TestClient(build_app(Settings(DB_PATH=str(tmp_path / "t.db"))))
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
