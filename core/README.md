# core/

The app framework — the part every sibling project shares, independent of
Apollo's domain.

Present now:

- `api.py` — `create_app()`, one router per area under `/api`, `/health`, static UI at `/`
  mount, domain errors mapped to HTTP statuses.
- `container.py` — `Services`, the object graph `main.build_services()` builds
  once and the routes read from `app.state`.
- `events.py` — `EventBus`, synchronous publish/subscribe: handlers run inline,
  a failing handler is logged and never affects the publisher.
- `state.py` — `Database`, the one stdlib sqlite3 connection behind an RLock,
  with transactions and forward-only SQL migrations in `migrations/`.

Expected as Apollo grows (see `hermes/core/` and `hestia/core/` for working
versions to adapt):

- `websocket.py` — `WebSocketManager`, relays bus events to the browser.
