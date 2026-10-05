import dataclasses


def test_status_shape(client):
    body = client.get("/api/status").json()
    assert body["state"] == "ok" and body["summary"] is None
    assert [s["label"] for s in body["stats"]] == ["Config errors", "Self-care due today", "Last workout"]
    assert body["stats"][0] == {"label": "Config errors", "value": 0, "kind": "count", "warn": False}


def test_status_degraded_on_config_errors(client):
    svc = client.app.state.services
    svc.catalog = dataclasses.replace(svc.catalog, errors=("x.yaml: bad",))
    body = client.get("/api/status").json()
    assert body["state"] == "degraded"
    assert body["stats"][0] == {"label": "Config errors", "value": 1, "kind": "count", "warn": True}
