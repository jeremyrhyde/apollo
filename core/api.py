"""HTTP surface: everything under /api, the built UI at /ui.

One `_build_<area>_router()` per area. Domain errors map to their status with
the message as `detail`. Values cross the API in display units (Settings:
lb/kg, mi/km; durations in seconds); conversion happens here, at the edge,
so services stay in SI.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.container import Services
from schemas.calendar import CalendarDay, LastDone
from schemas.selfcare import DueItem, LogSelfcareIn, SelfcareSessionOut, UpdateSelfcareIn
from schemas.workouts import (
    AddExerciseIn,
    ExerciseOut,
    FinishOut,
    SetOut,
    SetPatch,
    StartWorkoutIn,
    WorkoutOut,
    WorkoutSummary,
)
from services import preferences
from services.errors import AppError, Invalid
from services.units import UnitPrefs, from_storage, to_storage

RangeKey = Literal["1W", "1M", "1Y"]


def _svc(request: Request) -> Services:
    return request.app.state.services  # type: ignore[no-any-return]


def _units(s: Services) -> UnitPrefs:
    return preferences.unit_prefs(s.db, s.catalog.apollo.settings_defaults)


# ------------------------------------------------------------------ unit edge


def _set_view(item: SetOut, prefs: UnitPrefs) -> SetOut:
    return item.model_copy(
        update={
            "weight": from_storage("weight", item.weight, prefs),
            "distance": from_storage("distance", item.distance, prefs),
        }
    )


def _exercise_view(ex: ExerciseOut, prefs: UnitPrefs) -> ExerciseOut:
    return ex.model_copy(update={"sets": [_set_view(x, prefs) for x in ex.sets]})


def _workout_view(w: WorkoutOut, prefs: UnitPrefs) -> WorkoutOut:
    return w.model_copy(update={"exercises": [_exercise_view(e, prefs) for e in w.exercises]})


def _patch_to_si(patch: SetPatch, prefs: UnitPrefs) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field, value in patch.model_dump(exclude_unset=True).items():
        if field == "done":
            out[field] = value
            continue
        try:
            out[field] = to_storage(field, value, prefs)
        except ValueError as exc:
            raise Invalid(str(exc)) from exc
    return out


# ------------------------------------------------------------------ routers


def _build_meta_router() -> APIRouter:
    router = APIRouter(tags=["meta"])

    @router.get("/health")
    def health(request: Request) -> dict[str, Any]:
        s = _svc(request)
        errors = list(s.catalog.errors)
        return {"status": "degraded" if errors else "ok", "config_errors": errors}

    @router.get("/today")
    def today(request: Request) -> dict[str, str]:
        return {"today": _svc(request).clock.today().isoformat()}

    @router.get("/catalog")
    def catalog(request: Request) -> dict[str, Any]:
        c = _svc(request).catalog
        return {
            "metric_types": {k: list(v.fields) for k, v in c.exercises.metric_types.items()},
            "muscle_groups": list(c.exercises.muscle_groups),
            "exercises_by_group": {
                group: [
                    {"key": e.key, "name": e.name, "type": e.type, "groups": e.muscle_groups}
                    for e in exercises
                ]
                for group, exercises in c.exercises_by_group().items()
            },
            "selfcare": [
                {
                    "key": cat.key,
                    "name": cat.name,
                    "types": [{"key": t.key, "name": t.name, "every_days": t.every_days} for t in cat.types],
                }
                for cat in c.selfcare.categories
            ],
            "colors": c.apollo.colors.model_dump(),
        }

    return router


class SettingIn(BaseModel):
    value: str


def _build_settings_router() -> APIRouter:
    router = APIRouter(prefix="/settings", tags=["settings"])

    @router.get("")
    def get_settings(request: Request) -> dict[str, str]:
        s = _svc(request)
        return preferences.get_all(s.db, s.catalog.apollo.settings_defaults)

    @router.put("/{key}", status_code=status.HTTP_204_NO_CONTENT)
    def put_setting(key: str, body: SettingIn, request: Request) -> Response:
        s = _svc(request)
        preferences.set_pref(s.db, key, body.value, s.clock.now_iso())
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


def _build_workouts_router() -> APIRouter:
    router = APIRouter(tags=["workouts"])

    @router.post("/workouts", status_code=status.HTTP_201_CREATED)
    def start(body: StartWorkoutIn, request: Request) -> WorkoutOut:
        s = _svc(request)
        return _workout_view(s.workouts.start(body.planned_exercises), _units(s))

    @router.get("/workouts/open")
    def get_open(request: Request) -> WorkoutOut | None:
        s = _svc(request)
        w = s.workouts.get_open()
        return _workout_view(w, _units(s)) if w else None

    @router.get("/workouts")
    def history(request: Request, range: RangeKey = "1M") -> list[WorkoutSummary]:
        return _svc(request).workouts.history(range)

    @router.get("/workouts/{workout_id}")
    def get_workout(workout_id: int, request: Request) -> WorkoutOut:
        s = _svc(request)
        return _workout_view(s.workouts.get(workout_id), _units(s))

    @router.post("/workouts/{workout_id}/exercises", status_code=status.HTTP_201_CREATED)
    def add_exercise(workout_id: int, body: AddExerciseIn, request: Request) -> ExerciseOut:
        s = _svc(request)
        return _exercise_view(s.workouts.add_exercise(workout_id, body.exercise_key), _units(s))

    @router.delete("/workouts/{workout_id}/exercises/{we_id}", status_code=status.HTTP_204_NO_CONTENT)
    def remove_exercise(workout_id: int, we_id: int, request: Request) -> Response:
        _svc(request).workouts.remove_exercise(workout_id, we_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/workouts/{workout_id}/exercises/{we_id}/sets", status_code=status.HTTP_201_CREATED)
    def add_set(workout_id: int, we_id: int, request: Request) -> SetOut:
        s = _svc(request)
        return _set_view(s.workouts.add_set(workout_id, we_id), _units(s))

    @router.patch("/sets/{set_id}")
    def update_set(set_id: int, body: SetPatch, request: Request) -> SetOut:
        s = _svc(request)
        prefs = _units(s)
        return _set_view(s.workouts.update_set(set_id, _patch_to_si(body, prefs)), prefs)

    @router.delete("/sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_set(set_id: int, request: Request) -> Response:
        _svc(request).workouts.delete_set(set_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/workouts/{workout_id}/finish")
    def finish(workout_id: int, request: Request, end_at_last_activity: bool = False) -> FinishOut:
        s = _svc(request)
        w = s.workouts.finish(workout_id, end_at_last_activity)
        return FinishOut(workout=_workout_view(w, _units(s)) if w else None, deleted=w is None)

    @router.post("/workouts/{workout_id}/reopen")
    def reopen(workout_id: int, request: Request) -> WorkoutOut:
        s = _svc(request)
        return _workout_view(s.workouts.reopen(workout_id), _units(s))

    @router.delete("/workouts/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_workout(workout_id: int, request: Request) -> Response:
        _svc(request).workouts.delete(workout_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


def _build_selfcare_router() -> APIRouter:
    router = APIRouter(prefix="/selfcare", tags=["selfcare"])

    @router.post("/sessions", status_code=status.HTTP_201_CREATED)
    def log(body: LogSelfcareIn, request: Request) -> SelfcareSessionOut:
        return _svc(request).selfcare.log(body.category, body.types, body.date, body.notes)

    @router.get("/sessions")
    def history(request: Request, range: RangeKey = "1M", category: str | None = None) -> list[SelfcareSessionOut]:
        return _svc(request).selfcare.history(range, category)

    @router.get("/sessions/{session_id}")
    def get_session(session_id: int, request: Request) -> SelfcareSessionOut:
        return _svc(request).selfcare.get(session_id)

    @router.patch("/sessions/{session_id}")
    def update(session_id: int, body: UpdateSelfcareIn, request: Request) -> SelfcareSessionOut:
        return _svc(request).selfcare.update(session_id, body.model_dump(exclude_unset=True))

    @router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete(session_id: int, request: Request) -> Response:
        _svc(request).selfcare.delete(session_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/due")
    def due(request: Request) -> list[DueItem]:
        return _svc(request).selfcare.due_list()

    return router


def _build_calendar_router() -> APIRouter:
    router = APIRouter(prefix="/calendar", tags=["calendar"])

    @router.get("")
    def entries(
        request: Request,
        from_: date = Query(alias="from"),
        to: date = Query(),
        kinds: str = "workout,selfcare",
    ) -> list[CalendarDay]:
        wanted = {k.strip() for k in kinds.split(",") if k.strip()}
        return _svc(request).calendar.entries(from_, to, wanted)

    @router.get("/last-done")
    def last_done(request: Request) -> LastDone:
        return _svc(request).calendar.last_done()

    return router


# ------------------------------------------------------------------ app


class _UIFiles(StaticFiles):
    """The built UI. Vite's hashed files under assets/ never change, so they
    cache forever; everything else (index.html, the manifest) is revalidated
    on every load so a new build is picked up."""

    def file_response(self, full_path: Any, stat_result: Any, scope: Any, status_code: int = 200) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        relative = Path(full_path).resolve().relative_to(Path(self.directory).resolve())
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable" if relative.parts[0] == "assets" else "no-cache"
        )
        return response


def create_app(services: Services, *, lifespan: Any = None, mount_static: bool = True) -> FastAPI:
    app = FastAPI(title="Apollo", lifespan=lifespan)
    app.state.services = services

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": str(exc)})

    api = APIRouter(prefix="/api")
    for build in (
        _build_meta_router,
        _build_settings_router,
        _build_workouts_router,
        _build_selfcare_router,
        _build_calendar_router,
    ):
        api.include_router(build())
    app.include_router(api)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/ui/")

    web_dir = Path(services.settings.WEB_DIR)
    if mount_static and web_dir.is_dir():
        app.mount("/ui", _UIFiles(directory=web_dir, html=True), name="ui")

    return app
