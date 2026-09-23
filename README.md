# Apollo

A self-hosted, single-user personal tracker for workouts and skincare
self-care, shown on a calendar. Start a workout, add exercises from a
configured catalog, log sets prefilled from last time, finish it, and browse
past workouts; log a skincare session in a few taps and see what's overdue.
The calendar is the landing page. Used mostly from an iPhone in Safari on a
home network, no authentication — like Hermes and Hestia.

## Requirements

- Python ≥3.11, managed with `uv`
- Node ≥20 (to build the UI)

## Quickstart

```bash
make setup build run     # install uv, check Node, build the UI, start the server
make open                # http://localhost:8000/ui/
make test
```

Copy `.env.example` to `.env` to override settings (port, log level, paths).

## Development

```bash
make run-dev              # API with reload on :8000, Vite dev server on :5173/ui/
```

`make test` runs the Python suite (pytest) and, if `frontend/node_modules`
exists, the frontend suite (vitest); run `make build` first to get both.

## Configuration

Three YAML files in `config/` — `apollo.yaml` (timezone, colors, preference
defaults), `exercises.yaml` (the exercise catalog) and `selfcare.yaml` (the
self-care catalog) — committed to the repo, since they're the catalog, not
secrets. Edits take effect on restart. A validation error (unknown key,
undefined exercise group, malformed value) doesn't stop the server; it's
listed at `/api/health` and surfaced in the UI as a config-error notice, with
details on the Settings screen.

## Run it in the background

```bash
make build                # required first — service-install serves frontend/dist
make service-install      # systemd user unit on Linux/Pi, launchd agent on macOS
make service-status
make service-logs
make service-restart      # after a git pull
make service-uninstall
```

The service runs `main.py` from the repo root, so it uses the same `.env` as
`make run`. On Linux it enables linger so it starts at boot with no login; on
macOS it starts at login. Running `service-install` before `make build` leaves
`frontend/dist` missing, so `/ui/` 404s until you build and restart it.

### Updating

```bash
git pull && make build && make service-restart
```

### Using it

Open `http://<server>:8000/ui/` on your phone and use Safari's Share sheet →
Add to Home Screen for an app-like icon and fullscreen launch.

### Kiosk display (Raspberry Pi)

After `make service-install` on the Pi:

```bash
make kiosk-install              # auto-detect desktop vs headless
make kiosk-install-headless     # Pi OS Lite / Ubuntu Server: minimal X + auto-login
```

Chromium opens fullscreen on `http://localhost:$PORT/ui/`. Set
`SERVER_IP_ADDRESS` (or `APOLLO_UI_URL`) in `.env` to point the display at a
server elsewhere on the network.

## Layout

```
Makefile              setup / build / run / run-dev / test / service-* / kiosk-*
pyproject.toml        uv-managed deps (uv.lock committed)
config.py             Settings — every knob, read from env / .env
main.py               build_app() + lifespan; `python main.py` serves it
config/               apollo.yaml, exercises.yaml, selfcare.yaml — the catalog
core/                 app framework: api, container, state (+ migrations/), events
services/             Apollo's domain logic (workouts, selfcare, calendar, catalog, clock, units)
schemas/              pydantic models
tests/                pytest
frontend/             Svelte 5 + Vite + TypeScript app, built to frontend/dist and served at /ui
deploy/               systemd unit, launchd plist, kiosk/ launcher, headless-X files
scripts/              install-server.sh, install-kiosk.sh
docs/                 dated specs and plans
```
