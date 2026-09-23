# Apollo — notes for Claude

## Status

Skeleton only. Requirements are not written yet; the first job is working
them out with the user and recording them in `docs/` before writing code.

## Siblings

Apollo follows the layout of `../hermes` and `../hestia` (same author, same
stack). When a piece is needed, look there first for a working version to
adapt:

- `hermes/core/{events,websocket,state}.py` — event bus, WebSocket relay,
  aiosqlite store with forward-only migrations (`services/migrations/`).
- `hermes/config.py` — richly documented `Settings`, the model to follow.
- `hestia/web/` — the fuller UI: tokens, PWA icons, kiosk.
- `hestia/scripts/`, `hestia/deploy/` — origin of this repo's service and
  kiosk installers.

## Conventions

- Python ≥3.11, managed with `uv`. `make build` / `make test` / `make run`.
- Every setting is a field on `config.Settings` and a commented line in
  `.env.example`. Never read `os.environ` at a call site.
- A hand-edited YAML config gets a committed `<name>.yaml.example`; the real
  file is gitignored.
- API: one `_build_<area>_router()` per area in `core/api.py`; shared objects
  live on `app.state`, set up in `main.py`'s lifespan.
- Web UI: no build step. Alpine.js from the CDN; all colors, radii, spacing,
  type sizes, and durations are tokens in `web/style.css` `:root`.
- Design docs: `docs/YYYY-MM-DD-<topic>-spec.md`, then `-plan.md`.
