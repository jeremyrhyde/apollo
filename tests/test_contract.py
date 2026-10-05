"""Pantheon module contract: unique port, UI at `/`, API under `/api/`,
`/health` at the root, and only relative URLs in the UI — so the same build
works standalone (http://pi:8001/) and behind Pantheon's gateway
(http://pi:8000/apollo/). See pantheon/docs/module-contract.md."""

from __future__ import annotations

from config import Settings


def test_default_port_is_8001(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    assert Settings(_env_file=None).PORT == 8001

from main import build_app


def test_health_is_at_the_root_and_every_other_route_under_api(tmp_path, config_dir, now):
    settings = Settings(_env_file=None, DB_PATH=str(tmp_path / "t.db"),
                        CONFIG_DIR=str(config_dir), WEB_DIR=str(tmp_path / "none"))
    app = build_app(settings, now_fn=now)
    # openapi() rather than app.routes: newer FastAPI wraps included routers
    # lazily, so app.routes no longer lists their endpoints.
    paths = sorted(app.openapi()["paths"])
    assert "/health" in paths
    assert [p for p in paths if p != "/health" and not p.startswith("/api/")] == []
