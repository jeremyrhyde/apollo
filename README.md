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
make open                # http://localhost:8001/
make test
```

Copy `.env.example` to `.env` to override settings (port, log level, paths).

## Development

```bash
make run-dev              # API with reload on :8001, Vite dev server on :5173/
```

`make test` runs the Python suite (pytest) and, if `frontend/node_modules`
exists, the frontend suite (vitest); run `make build` first to get both.

## Configuration

Three YAML files in `config/` — `apollo.yaml` (timezone, colors, preference
defaults), `exercises.yaml` (the exercise catalog) and `selfcare.yaml` (the
self-care catalog) — committed to the repo, since they're the catalog, not
secrets. Edits take effect on restart. A validation error (unknown key,
undefined exercise group, malformed value) doesn't stop the server; it's
listed at `/health` and surfaced in the UI as a config-error notice, with
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
`frontend/dist` missing, so `/` 404s until you build and restart it.

### Updating

```bash
git pull && make build && make service-restart
```

### Using it

Open `http://<server>:8001/` on your phone and use Safari's Share sheet →
Add to Home Screen for an app-like icon and fullscreen launch.

### Kiosk display (Raspberry Pi)

After `make service-install` on the Pi:

```bash
make kiosk-install              # auto-detect desktop vs headless
make kiosk-install-headless     # Pi OS Lite / Ubuntu Server: minimal X + auto-login
```

Chromium opens fullscreen on `http://localhost:$PORT/`. Set
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
frontend/             Svelte 5 + Vite + TypeScript app, built to frontend/dist and served at /
deploy/               systemd unit, launchd plist, kiosk/ launcher, headless-X files
scripts/              install-server.sh, install-kiosk.sh
docs/                 dated specs and plans
```

## Using with Pantheon

Apollo is one of the modules of [Pantheon](https://github.com/jeremyrhyde/pantheon),
which runs it alongside the other modules behind one address. Nothing here
changes for that: Apollo always listens on **port 8001**, serves its UI at
`/`, its API under `/api/` and `/health` at the root.

| | Standalone | Inside Pantheon |
|---|---|---|
| UI | `http://<host>:8001/` | `http://<main-pi>:8000/apollo/` |
| Service | `make service-install` | installed by Pantheon's `make service-install-all` |
| Kiosk | `make kiosk-install` | Pantheon's `make kiosk-install MODULE=apollo SERVER=<main-pi>` |

Inside Pantheon, Apollo is the workout and self-care routine: edge displays
(e.g. a bathroom Pi) open `/apollo/` directly from the main Pi, with no
Apollo checkout or Node on the edge device.

Upgrading an existing install: `:8000/ui/` is now `:8001/`. Remove any
`PORT=8000` or `APOLLO_UI_URL=…/ui/` lines from `.env`, then
`git pull && make build service-restart`.
