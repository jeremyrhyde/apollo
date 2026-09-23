# Apollo
#
# Common workflows wrapped as `make` targets. Run `make help` for the list.
# Most targets shell out to `uv` — `make setup` installs it when missing.

# Resolve `uv`: prefer one already on PATH, else the location the official
# installer drops it (~/.local/bin) on both Linux and macOS. Override with
# `make UV=/path/to/uv ...`.
UV ?= $(shell command -v uv 2>/dev/null || echo $(HOME)/.local/bin/uv)
PYTHON := $(UV) run python
PYTEST := $(UV) run pytest

# Host/port for run-dev and the live checks. `make run` and the background
# service read HOST/PORT from config.Settings (the environment / .env) instead.
HOST ?= 0.0.0.0
PORT ?= 8000
APOLLO_HOST ?= http://localhost:$(PORT)

.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

.PHONY: help
help:
	@echo "Apollo — make targets"
	@echo ""
	@echo "Pipeline (Linux + macOS):"
	@echo "  make setup            Ensure the uv toolchain is installed"
	@echo "  make build            Sync deps into .venv and byte-compile sources"
	@echo "  make run              Start the server in the foreground"
	@echo "  -> full bootstrap:    make setup build run"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Alias for build"
	@echo "  make lock             Re-lock dependencies (regenerate uv.lock)"
	@echo "  make clean            Remove caches, build artefacts, *.pyc"
	@echo "  make distclean        clean + remove .venv"
	@echo ""
	@echo "Run:"
	@echo "  make run-dev          Start with auto-reload (HOST/PORT overridable)"
	@echo "  make open             Open the web UI in a browser"
	@echo "  make health           curl /api/health on a running server"
	@echo ""
	@echo "Tests:"
	@echo "  make test             Run the pytest suite"
	@echo ""
	@echo "Background service (systemd on Linux/Pi, launchd on macOS):"
	@echo "  make service-install    Install + start the server at boot/login"
	@echo "  make service-uninstall  Stop and remove it"
	@echo "  make service-status     Show whether it is running"
	@echo "  make service-logs       Follow its logs"
	@echo "  make service-restart    Restart it (e.g. after a git pull)"
	@echo ""
	@echo "Kiosk display (Linux/Pi only; install the service first):"
	@echo "  make kiosk-install            Auto-detect desktop vs headless"
	@echo "  make kiosk-install-headless   Force headless (Pi OS Lite / Ubuntu Server)"
	@echo "  make kiosk-uninstall          Remove the kiosk unit"

# ---------------------------------------------------------------------------
# Setup / build
# ---------------------------------------------------------------------------

# setup — ensure the uv toolchain exists. Idempotent; uses the official
# installer only when uv is missing, preferring curl and falling back to wget.
.PHONY: setup
setup:
	@if [ -x "$(UV)" ] || command -v uv >/dev/null 2>&1; then \
		echo "uv already present: $$($(UV) --version 2>/dev/null || echo $(UV))"; \
	else \
		echo "Installing uv (Linux/macOS)..."; \
		if command -v curl >/dev/null 2>&1; then \
			curl -LsSf https://astral.sh/uv/install.sh | sh; \
		elif command -v wget >/dev/null 2>&1; then \
			wget -qO- https://astral.sh/uv/install.sh | sh; \
		else \
			echo "ERROR: need curl or wget to install uv. See https://docs.astral.sh/uv/"; \
			exit 1; \
		fi; \
		echo "uv installed to $(HOME)/.local/bin — ensure it is on your PATH."; \
	fi

# build — sync locked deps into .venv, then byte-compile the sources so a
# syntax error fails the build on any platform.
.PHONY: build
build:
	$(UV) sync
	$(UV) run python -m compileall -q core services schemas main.py config.py
	@echo "Build complete."

.PHONY: install
install: build

.PHONY: lock
lock:
	$(UV) lock

.PHONY: clean
clean:
	@find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name '*.egg-info' -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name '*.pyc' -delete 2>/dev/null || true
	@echo "Cleaned caches and build artefacts."

.PHONY: distclean
distclean: clean
	@rm -rf .venv
	@echo "Removed .venv. Run 'make build' to rebuild."

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

.PHONY: run
run:
	$(PYTHON) main.py

.PHONY: run-dev
run-dev:
	$(UV) run uvicorn main:build_app --factory --reload --host $(HOST) --port $(PORT)

.PHONY: open
open:
	@python3 -c "import webbrowser; webbrowser.open('$(APOLLO_HOST)/ui/')"

.PHONY: health
health:
	@curl -sS $(APOLLO_HOST)/api/health && echo ""

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

.PHONY: test
test:
	$(PYTEST) -v

# ---------------------------------------------------------------------------
# Background service — see scripts/install-server.sh
# ---------------------------------------------------------------------------

.PHONY: service-install
service-install:
	./scripts/install-server.sh

.PHONY: service-uninstall
service-uninstall:
	./scripts/install-server.sh --uninstall

.PHONY: service-status
service-status:
	./scripts/install-server.sh --status

.PHONY: service-logs
service-logs:
	./scripts/install-server.sh --logs

.PHONY: service-restart
service-restart:
	./scripts/install-server.sh --restart

# ---------------------------------------------------------------------------
# Kiosk — see scripts/install-kiosk.sh (Linux/Pi only)
# ---------------------------------------------------------------------------

.PHONY: kiosk-install
kiosk-install:
	./scripts/install-kiosk.sh

.PHONY: kiosk-install-headless
kiosk-install-headless:
	./scripts/install-kiosk.sh --headless

.PHONY: kiosk-uninstall
kiosk-uninstall:
	./scripts/install-kiosk.sh --uninstall
