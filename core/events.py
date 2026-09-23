"""Minimal in-process event bus.

Services publish facts ("workout.finished", "selfcare.logged") after their
transaction commits. Future features (stats refresh, Claude check-ins,
reminders) subscribe here instead of being called from the loggers.
Subscribe to "*" to receive everything. A failing handler is logged and never
affects the publisher or other handlers.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

Handler = Callable[[str, dict[str, Any]], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, name: str, handler: Handler) -> None:
        self._subscribers[name].append(handler)

    def publish(self, name: str, payload: dict[str, Any]) -> None:
        for handler in [*self._subscribers[name], *self._subscribers["*"]]:
            try:
                handler(name, payload)
            except Exception:
                logger.exception("event handler failed for %s", name)
