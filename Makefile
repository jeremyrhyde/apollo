# Apollo
#
# Common workflows wrapped as `make` targets. Run `make help` for the list.
# Python targets shell out to `uv`; the UI needs Node 20+ (`make setup` checks).

UV ?= $(shell command -v uv 2>/dev/null || echo $(HOME)/.local/bin/uv)
PYTHON := $(UV) run python
PYTEST := $(UV) run pytest
NPM ?= npm
FRONTEND := frontend

# Host/port for run-dev and the live checks. `make run` and the background
# service read HOST/PORT from config.Settings (the environment / .env).
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
	@echo "  make setup            Ensure uv is installed and Node 20+ is present"
	@echo "  make build            Sync Python deps, build the UI into frontend/dist"
	@echo "  make run              Serve API + built UI in the foreground"
	@echo "  -> full bootstrap:    make setup build run"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Alias for build"
	@echo "  make lock             Re-lock Python dependencies (uv.lock)"
	@echo "  make clean            Remove caches, build artefacts, frontend/dist"
	@echo "  make distclean        clean + remove .venv and frontend/node_modules"
	@echo ""
	@echo "Run:"
	@echo "  make run-dev          API with reload on :$(PORT) + UI dev server on :5173/ui/"
	@echo "  make open             Open the web UI in a browser"
	@echo "  make health           curl /api/health on a running server"
	@echo ""
	@echo "Tests:"
	@echo "  make test             pytest, then vitest"
	@echo ""
	@echo "Background service (systemd on Linux/Pi, launchd on macOS):"
	@echo "  make service-install    Install + start the server at boot/login"
	@echo "  make service-uninstall  Stop and remove it"
	@echo "  make service-status     Show whether it is running"
	@echo "  make service-logs       Follow its logs"
	@echo "  make service-restart    Restart it (after git pull && make build)"
	@echo ""
	@echo "Kiosk display (Linux/Pi only; install the service first):"
	@echo "  make kiosk-install            Auto-detect desktop vs headless"
	@echo "  make kiosk-install-headless   Force headless (Pi OS Lite / Ubuntu Server)"
	@echo "  make kiosk-uninstall          Remove the kiosk unit"

# ---------------------------------------------------------------------------
# Setup / build
# ---------------------------------------------------------------------------

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
	@if command -v node >/dev/null 2>&1 && [ "$$(node -p 'process.versions.node.split(".")[0]')" -ge 20 ]; then \
		echo "node present: $$(node --version)"; \
	else \
		echo "ERROR: Node.js 20+ is required to build the UI."; \
		echo "  macOS:     brew install node"; \
		echo "  Pi/Debian: install Node 20+ from https://nodejs.org/en/download (NodeSource)"; \
		exit 1; \
	fi

.PHONY: build
build:
	$(UV) sync
	$(UV) run python -m compileall -q core services schemas main.py config.py
	cd $(FRONTEND) && $(NPM) ci && $(NPM) run build
	@echo "Build complete."

.PHONY: install
install: build

.PHONY: lock
lock:
	$(UV) lock

.PHONY: clean
clean:
	@find . -path ./$(FRONTEND)/node_modules -prune -o -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name '*.egg-info' -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -path ./$(FRONTEND)/node_modules -prune -o -type f -name '*.pyc' -delete 2>/dev/null || true
	@rm -rf $(FRONTEND)/dist
	@echo "Cleaned caches and build artefacts."

.PHONY: distclean
distclean: clean
	@rm -rf .venv $(FRONTEND)/node_modules
	@echo "Removed .venv and node_modules. Run 'make build' to rebuild."

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

.PHONY: run
run:
	$(PYTHON) main.py

.PHONY: run-dev
run-dev:
	@echo "API on :$(PORT) — UI dev server on http://localhost:5173/ui/"
	@trap 'kill 0' INT TERM EXIT; \
	(cd $(FRONTEND) && $(NPM) run dev -- --host) & \
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
	@if [ -d $(FRONTEND)/node_modules ]; then \
		cd $(FRONTEND) && $(NPM) test; \
	else \
		echo "Skipping vitest: $(FRONTEND)/node_modules not found. Run 'make build' first."; \
	fi

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
