import pytest


def start(client, planned=None):
    r = client.post("/api/workouts", json={"planned_exercises": planned or []})
    assert r.status_code == 201, r.text
    return r.json()


def test_health_and_today(client):
    assert client.get("/health").json() == {"status": "ok", "config_errors": []}
    assert client.get("/api/today").json() == {"today": "2026-09-22"}


def test_catalog_shape(client):
    c = client.get("/api/catalog").json()
    assert c["metric_types"]["distance_time"] == ["distance", "duration"]
    assert c["muscle_groups"][0] == "chest"
    assert c["exercises_by_group"]["glutes"] == [
        {
            "key": "squat",
            "name": "Back Squat",
            "type": "weight_reps",
            "groups": ["legs", "glutes"],
            "muscles": {"primary": ["quadriceps", "hamstring", "calves", "gluteal"], "secondary": []},
        }
    ]
    assert c["selfcare"][0]["types"][0] == {"key": "am_routine", "name": "AM routine", "every_days": 1}
    assert c["colors"] == {"workout": "#4ade80", "selfcare": "#60a5fa"}


def test_settings_get_and_put(client):
    assert client.get("/api/settings").json()["weight_unit"] == "lb"
    assert client.put("/api/settings/weight_unit", json={"value": "kg"}).status_code == 204
    assert client.get("/api/settings").json()["weight_unit"] == "kg"
    r = client.put("/api/settings/weight_unit", json={"value": "stone"})
    assert r.status_code == 422 and "must be one of" in r.json()["detail"]


def test_workout_flow_with_unit_conversion(client):
    w = start(client, ["bench_press"])
    assert client.post("/api/workouts", json={}).status_code == 409
    ex = w["exercises"][0]
    set_id = ex["sets"][0]["id"]
    r = client.patch(f"/api/sets/{set_id}", json={"weight": 135, "reps": 8, "done": True})
    assert r.status_code == 200
    assert r.json() | {"id": 0} == {"id": 0, "position": 1, "done": True, "weight": 135.0, "reps": 8,
                                    "distance": None, "duration": None}
    client.put("/api/settings/weight_unit", json={"value": "kg"})
    open_w = client.get("/api/workouts/open").json()
    assert open_w["exercises"][0]["sets"][0]["weight"] == pytest.approx(61.23, abs=0.01)
    client.put("/api/settings/weight_unit", json={"value": "lb"})
    fin = client.post(f"/api/workouts/{w['id']}/finish").json()
    assert fin["deleted"] is False and fin["workout"]["ended_at"] is not None
    assert client.get("/api/workouts/open").json() is None
    history = client.get("/api/workouts?range=1W").json()
    assert [h["id"] for h in history] == [w["id"]] and history[0]["focus"] == ["chest"]


def test_workout_errors(client):
    w = start(client)
    r = client.post(f"/api/workouts/{w['id']}/exercises", json={"exercise_key": "plank"})
    assert r.status_code == 201
    set_id = r.json()["sets"][0]["id"]
    assert client.patch(f"/api/sets/{set_id}", json={"weight": 10}).status_code == 422
    assert client.patch(f"/api/sets/{set_id}", json={"reps": -1}).status_code == 422
    assert client.get("/api/workouts/999").status_code == 404
    assert client.get("/api/workouts?range=2W").status_code == 422
    # unknown planned exercises are rejected before the one-open check
    assert client.post("/api/workouts", json={"planned_exercises": ["nope"]}).status_code == 422
    assert client.post("/api/workouts", json={}).status_code == 409


def test_sets_add_delete_and_exercise_delete(client):
    w = start(client)
    ex = client.post(f"/api/workouts/{w['id']}/exercises", json={"exercise_key": "run"}).json()
    s2 = client.post(f"/api/workouts/{w['id']}/exercises/{ex['id']}/sets").json()
    client.patch(f"/api/sets/{s2['id']}", json={"distance": 3.1, "duration": 1800})
    got = client.get(f"/api/workouts/{w['id']}").json()["exercises"][0]["sets"][1]
    assert (got["distance"], got["duration"]) == (3.1, 1800)
    assert client.delete(f"/api/sets/{s2['id']}").status_code == 204
    assert client.delete(f"/api/workouts/{w['id']}/exercises/{ex['id']}").status_code == 204
    assert client.get(f"/api/workouts/{w['id']}").json()["exercises"] == []


def test_finish_empty_reopen_and_delete(client):
    w = start(client, ["plank"])
    assert client.post(f"/api/workouts/{w['id']}/finish").json() == {"workout": None, "deleted": True}
    w = start(client, ["pull_up"])
    sid = w["exercises"][0]["sets"][0]["id"]
    client.patch(f"/api/sets/{sid}", json={"reps": 10, "done": True})
    client.post(f"/api/workouts/{w['id']}/finish")
    assert client.patch(f"/api/sets/{sid}", json={"reps": 11}).status_code == 409
    reopened = client.post(f"/api/workouts/{w['id']}/reopen").json()
    assert reopened["ended_at"] is None and reopened["reopened"] is True
    assert client.get("/api/workouts/open").json()["reopened"] is True
    assert client.delete(f"/api/workouts/{w['id']}").status_code == 204


def test_selfcare_flow(client):
    r = client.post("/api/selfcare/sessions", json={"category": "skincare", "types": ["am_routine"], "date": "2026-09-21"})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert client.get(f"/api/selfcare/sessions/{sid}").json()["local_date"] == "2026-09-21"
    p = client.patch(f"/api/selfcare/sessions/{sid}", json={"notes": "ok"})
    assert p.json()["notes"] == "ok"
    assert client.patch(f"/api/selfcare/sessions/{sid}", json={"date": None}).status_code == 422
    assert [s["id"] for s in client.get("/api/selfcare/sessions?range=1W").json()] == [sid]
    due = client.get("/api/selfcare/due").json()
    assert [(d["type_key"], d["status"]) for d in due][:2] == [("exfoliation", "never"), ("am_routine", "due")]
    bad = client.post("/api/selfcare/sessions", json={"category": "skincare", "types": []})
    assert bad.status_code == 422
    assert client.delete(f"/api/selfcare/sessions/{sid}").status_code == 204


def test_calendar_and_last_done(client):
    client.post("/api/selfcare/sessions", json={"category": "skincare", "types": ["am_routine"]})
    days = client.get("/api/calendar?from=2026-09-01&to=2026-09-30&kinds=workout,selfcare").json()
    assert days == [{"date": "2026-09-22", "entries": [
        {"kind": "selfcare", "id": 1, "title": "Skincare (Face)", "summary": "AM routine", "in_progress": False}]}]
    assert client.get("/api/calendar?from=2026-09-30&to=2026-09-01&kinds=workout").status_code == 422
    assert client.get("/api/calendar/last-done").json()["selfcare"] == "2026-09-22"


def test_ui_not_mounted_without_build(client):
    assert client.get("/").status_code == 404
    assert client.get("/ui/").status_code == 404


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("patch", "/api/sets/999", {"reps": 1}),
        ("delete", "/api/sets/999", None),
        ("get", "/api/selfcare/sessions/999", None),
        ("patch", "/api/selfcare/sessions/999", {"notes": "x"}),
        ("delete", "/api/selfcare/sessions/999", None),
        ("post", "/api/workouts/999/finish", None),
    ],
)
def test_unknown_ids_are_404(client, method, path, body):
    kwargs = {"json": body} if body is not None else {}
    r = client.request(method.upper(), path, **kwargs)
    assert r.status_code == 404 and r.json()["detail"]


def test_add_set_to_missing_exercise_is_404(client):
    w = start(client)
    assert client.post(f"/api/workouts/{w['id']}/exercises/999/sets").status_code == 404


def test_reopen_while_another_open_is_409(client):
    w = start(client, ["pull_up"])
    client.patch(f"/api/sets/{w['exercises'][0]['sets'][0]['id']}", json={"reps": 5, "done": True})
    assert client.post(f"/api/workouts/{w['id']}/finish").json()["deleted"] is False
    start(client)
    r = client.post(f"/api/workouts/{w['id']}/reopen")
    assert r.status_code == 409 and "in progress" in r.json()["detail"]


@pytest.mark.parametrize(
    "path, detail",
    [
        ("/api/settings/nope", "unknown setting"),
        ("/api/settings/distance_unit", "must be one of"),
    ],
)
def test_bad_setting_is_422(client, path, detail):
    r = client.put(path, json={"value": "furlong"})
    assert r.status_code == 422 and detail in r.json()["detail"]


@pytest.mark.parametrize("kinds", ["meals", "workout,meals", ","])
def test_bad_calendar_kinds_is_422(client, kinds):
    r = client.get(f"/api/calendar?from=2026-09-01&to=2026-09-30&kinds={kinds}")
    assert r.status_code == 422 and "kinds" in r.json()["detail"]


def test_unknown_selfcare_category_filter_is_422(client):
    r = client.get("/api/selfcare/sessions?category=nope")
    assert r.status_code == 422 and "unknown category" in r.json()["detail"]
    assert client.get("/api/selfcare/sessions?category=skincare").status_code == 200


def test_units_round_trip_kg_km_to_lb_mi(client):
    client.put("/api/settings/weight_unit", json={"value": "kg"})
    client.put("/api/settings/distance_unit", json={"value": "km"})
    w = start(client, ["bench_press", "run"])
    bench, run = (ex["sets"][0]["id"] for ex in w["exercises"])
    assert client.patch(f"/api/sets/{bench}", json={"weight": 100}).json()["weight"] == 100.0
    assert client.patch(f"/api/sets/{run}", json={"distance": 5}).json()["distance"] == 5.0
    client.put("/api/settings/weight_unit", json={"value": "lb"})
    client.put("/api/settings/distance_unit", json={"value": "mi"})
    sets = [ex["sets"][0] for ex in client.get(f"/api/workouts/{w['id']}").json()["exercises"]]
    assert sets[0]["weight"] == pytest.approx(220.46, abs=0.01)
    assert sets[1]["distance"] == pytest.approx(3.107, abs=0.001)


def test_ui_cache_headers(tmp_path, config_dir, now):
    from fastapi.testclient import TestClient

    from config import Settings
    from main import build_app

    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<!doctype html><title>Apollo</title>")
    (web / "manifest.webmanifest").write_text("{}")
    (web / "assets" / "x.js").write_text("console.log(1)")
    settings = Settings(DB_PATH=str(tmp_path / "ui.db"), CONFIG_DIR=str(config_dir), WEB_DIR=str(web))
    with TestClient(build_app(settings, now_fn=now)) as c:
        for path in ("/", "/index.html", "/manifest.webmanifest"):
            r = c.get(path)
            assert r.status_code == 200, path
            assert r.headers["cache-control"] == "no-cache", path
        assert c.get("/health").json()["status"] == "ok"  # not shadowed by the UI mount
        r = c.get("/assets/x.js")
        assert r.status_code == 200
        assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
