# core/

The app framework — the part every sibling project shares, independent of
Apollo's domain.

Present now:

- `api.py` — `create_app()`, routers, static `/ui` mount, `/api/health`.

Expected as Apollo grows (see `hermes/core/` and `hestia/core/` for working
versions to adapt):

- `events.py` — `EventBus`, async publish/subscribe between components.
- `websocket.py` — `WebSocketManager`, relays bus events to the browser.
- `state.py` — `StateStore`, the aiosqlite connection and every query, with
  forward-only SQL migrations.
