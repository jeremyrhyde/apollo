def test_status_shape(client):
    body = client.get("/api/status").json()
    assert body["state"] == "ok" and body["summary"] is None
    assert [s["label"] for s in body["stats"]] == ["Config errors", "Self-care due today", "Last workout"]
    assert body["stats"][0] == {"label": "Config errors", "value": 0, "kind": "count", "warn": False}
