# Apollo

> Requirements TBD — this is the shared skeleton of the sibling projects
> (Hermes, Hestia, Pluto), ready for Apollo's design to be written into it.

A FastAPI server with a no-build web UI at `/ui`, built to run as a
background service on a Mac or a Raspberry Pi, with an optional fullscreen
kiosk display on the Pi.

## Quickstart

```bash
make setup build run     # install uv, sync deps, start the server
make open                # http://localhost:8000/ui/
make test
```

Copy `.env.example` to `.env` to override settings (port, log level, paths).

## Run it in the background

```bash
make service-install     # systemd user unit on Linux/Pi, launchd agent on macOS
make service-status
make service-logs
make service-restart     # after a git pull
make service-uninstall
```

The service runs `main.py` from the repo root, so it uses the same `.env` as
`make run`. On Linux it enables linger so it starts at boot with no login; on
macOS it starts at login.

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
Makefile              setup / build / run / test / service-* / kiosk-*
pyproject.toml        uv-managed deps (uv.lock committed)
config.py             Settings — every knob, read from env / .env
main.py               build_app() + lifespan; `python main.py` serves it
core/                 app framework: api, container, state (+ migrations/), events
schemas/              pydantic models
services/             Apollo's domain logic (metrics.py is a placeholder)
tests/                pytest (+ pytest-asyncio, asyncio_mode=auto)
config/               apollo.yaml, exercises.yaml, selfcare.yaml — the catalog
frontend/             Svelte 5 + Vite app, built to frontend/dist and served at /ui
deploy/               systemd unit, launchd plist, kiosk/ launcher, headless-X files
scripts/              install-server.sh, install-kiosk.sh
docs/                 dated specs and plans
```
