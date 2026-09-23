from core.events import EventBus
from services.errors import AppError, Conflict, Invalid, NotFound


def test_error_statuses():
    assert (NotFound.status, Conflict.status, Invalid.status) == (404, 409, 422)
    assert issubclass(NotFound, AppError)


def test_publish_reaches_named_and_wildcard_subscribers():
    bus, seen = EventBus(), []
    bus.subscribe("workout.finished", lambda name, payload: seen.append(("named", name, payload)))
    bus.subscribe("*", lambda name, payload: seen.append(("any", name, payload)))
    bus.publish("workout.finished", {"id": 1})
    bus.publish("selfcare.logged", {"id": 2})
    assert seen == [
        ("named", "workout.finished", {"id": 1}),
        ("any", "workout.finished", {"id": 1}),
        ("any", "selfcare.logged", {"id": 2}),
    ]


def test_failing_handler_does_not_stop_others():
    bus, seen = EventBus(), []

    def boom(name, payload):
        raise RuntimeError("handler failed")

    bus.subscribe("x", boom)
    bus.subscribe("x", lambda name, payload: seen.append(payload))
    bus.publish("x", {"ok": True})
    assert seen == [{"ok": True}]
