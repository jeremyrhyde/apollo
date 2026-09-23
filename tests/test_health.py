from fastapi.testclient import TestClient

from config import Settings
from main import build_app


def test_build_app_boots_on_a_fresh_db(tmp_path, config_dir, now):
    settings = Settings(DB_PATH=str(tmp_path / "t.db"), CONFIG_DIR=str(config_dir), WEB_DIR=str(tmp_path / "none"))
    with TestClient(build_app(settings, now_fn=now)) as client:
        assert client.get("/api/health").json()["status"] == "ok"


def test_importing_main_does_not_create_a_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import importlib

    import main

    importlib.reload(main)
    assert not (tmp_path / "apollo.db").exists()
