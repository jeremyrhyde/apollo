# Apollo — notes for Claude

## Status

MVP implemented, per `docs/2026-09-22-mvp-spec.md` (plans in `docs/`).

## Siblings

Apollo follows the layout of `../hermes` and `../hestia` (same author, same
stack), with one deliberate difference: the frontend is Svelte, not Alpine
(see below). When a backend piece is needed, look at the siblings first for a
working version to adapt:

- `hermes/core/{events,websocket,state}.py` — event bus, WebSocket relay,
  migrations pattern (Apollo's DB is stdlib `sqlite3`, forward-only
  migrations in `core/migrations/`).
- `hermes/config.py` — richly documented `Settings`, the model to follow.
- `hestia/scripts/`, `hestia/deploy/` — origin of this repo's service and
  kiosk installers.

## Conventions

- Python ≥3.11, managed with `uv`. `make build` / `make test` / `make run`
  build and test both the Python backend and the frontend.
- Every setting is a field on `config.Settings` and a commented line in
  `.env.example`. Never read `os.environ` at a call site.
- A hand-edited YAML config gets a committed `<name>.yaml.example`; the real
  file is gitignored — except `config/*.yaml` (apollo, exercises, selfcare),
  which are committed outright: they're the catalog, not secrets or
  host-specific settings (spec §3).
- API: one `_build_<area>_router()` per area in `core/api.py`. Shared objects
  are a `Services` dataclass (`core/container.py`) built once by
  `main.build_services()` and put on `app.state.services` in `create_app()`;
  the lifespan only closes the DB on shutdown. API is served under `/api`.
- Web UI: Svelte 5 (runes only) + Vite + TypeScript in `frontend/`, built to
  `frontend/dist` and served at `/`. All fetches go through
  `frontend/src/lib/api.ts`. Pantheon contract: fetches use relative paths
  (no leading `/`; Vite `base: './'`); `/health` is at the root. Design
  tokens (colors, radii, spacing, type
  sizes, durations) live in `frontend/src/styles/tokens.css`; no hex values
  in components. Tap targets are at least `var(--tap-min)`; inputs are at
  least 16px to avoid iOS zoom-on-focus.
- Design docs: `docs/YYYY-MM-DD-<topic>-spec.md`, then `-plan.md`.
