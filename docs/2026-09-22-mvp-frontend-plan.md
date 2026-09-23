# Apollo MVP — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Apollo's phone-first Svelte UI — Calendar landing page, Workouts (hub, active logging, history, detail), Self-care (hub, log, history, detail) and Settings — served by FastAPI at `/ui/`.

**Architecture:** A Svelte 5 + Vite + TypeScript single-page app in `frontend/`, built to `frontend/dist/`. Hash routing (`#/workouts/42`) so Safari back, bookmarks and deep links work. Shared reactive state lives in small `.svelte.ts` modules (`app`, `router`, `toast`); pure logic (dates, formatting, routes) lives in `.ts` files with vitest tests. All computation stays in the backend; the UI renders what `/api` returns.

**Tech Stack:** Svelte 5 (runes), Vite, TypeScript, vitest, svelte-check. Node ≥ 20.

**Prerequisite:** the backend plan (`docs/2026-09-22-mvp-backend-plan.md`) is complete — `make test` passes and `/api/*` is live. Work on the same `feat/mvp` branch.

**Spec:** `docs/2026-09-22-mvp-spec.md` §7 (frontend) and §6 (API).

### Conventions for every task

- Svelte 5 runes only: `$props()`, `$state()`, `$derived()`, `$effect()`; event attributes (`onclick={…}`), not `on:click`.
- Components import shared state from `src/lib/*.svelte.ts`; never call `fetch` directly — use `src/lib/api.ts`.
- Design tokens only (`var(--…)`) for colors, radii, spacing, durations. No hex values in components.
- Every interactive element ≥ `var(--tap-min)` (44 px) tall; inputs ≥ 16 px font (no iOS zoom).
- Verification for UI tasks: `npm run check` (0 errors), `npm test`, `npm run build`, then the manual check listed in the task using `make run-dev` → `http://localhost:5173/ui/`.

### Task order

```
1 ─► 2 ─► 3 ─► 4 ─► 5 ─► 6 ─► 7
                         ├─► 8 ─► 9
                         ├─► 10
                         └─► 11 ─► 12
```
Tasks 7, 8, 10, 11 each own disjoint screen files and can run in parallel after 6; 9 needs 8's shared pieces.

### File map

| File | Responsibility | Task |
|---|---|---|
| `Makefile` | node check, npm build, dual dev server, vitest | 1 |
| `frontend/vite.config.ts`, `package.json` | base `/ui/`, `/api` proxy, vitest | 1 |
| `frontend/src/lib/types.ts` | API types (mirror `schemas/`) | 2 |
| `frontend/src/lib/dates.ts` (+test) | ISO-date math, calendar grids, labels | 2 |
| `frontend/src/lib/format.ts` (+test) | durations, relative days, due text | 2 |
| `frontend/src/lib/route.ts` (+test) | parse/build hash routes | 2 |
| `frontend/src/lib/api.ts` | typed fetch wrapper for every endpoint | 3 |
| `frontend/src/lib/app.svelte.ts` | catalog, settings, today, config errors | 3 |
| `frontend/src/lib/router.svelte.ts` | history-aware hash router + view transitions | 3 |
| `frontend/src/lib/toast.svelte.ts`, `motion.ts`, `recent.ts`, `entries.ts` | toasts, reduced motion, recent exercises, entry navigation | 3 |
| `frontend/src/styles/tokens.css`, `src/app.css`, `index.html`, `public/*` | tokens, global styles, shell, PWA | 4 |
| `frontend/src/App.svelte`, `components/{Icon,TabBar,BackBar,Toast}.svelte`, screen stubs | shell + routing | 4 |
| `components/{ConfirmSheet,RangeFilter,SessionCard}.svelte` | shared UI | 5 |
| `components/Calendar.svelte` | week / month / year heatmap / compact | 6 |
| `screens/calendar/*` | Calendar landing + day view | 7 |
| `screens/workouts/{WorkoutsHub,WorkoutHistory,WorkoutDetail}.svelte`, `components/SetRow.svelte` | workouts browse | 8 |
| `screens/workouts/ActiveWorkout.svelte`, `components/ExercisePicker.svelte` | logging | 9 |
| `screens/selfcare/*` | self-care | 10 |
| `screens/settings/SettingsScreen.svelte` | settings | 11 |
| — | end-to-end acceptance | 12 |

---

### Task 1: Scaffold the frontend and wire the build

**Files:**
- Create: `frontend/` (via create-vite), `frontend/vite.config.ts` (replace)
- Modify: `frontend/package.json` (test script), `Makefile` (replace)

- [ ] **Step 1: Check Node**

Run: `node --version`
Expected: `v20.x` or newer. If missing on macOS: `brew install node`.

- [ ] **Step 2: Scaffold**

```bash
cd ~/Development/apollo
npm create vite@latest frontend -- --template svelte-ts
```
If asked "Install with npm and start now?", answer **No**. Then:

```bash
cd frontend
npm install
npm install -D vitest
npm pkg set scripts.test="vitest run"
rm -rf src/lib/Counter.svelte src/assets public/vite.svg
```

- [ ] **Step 3: Replace `frontend/vite.config.ts`**

```ts
/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Served by FastAPI at /ui/; in dev, Vite serves the UI and forwards /api.
export default defineConfig({
  base: '/ui/',
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000' },
  },
  build: { outDir: 'dist', emptyOutDir: true },
  test: { include: ['src/**/*.test.ts'], environment: 'node' },
});
```

- [ ] **Step 4: Replace the `Makefile`**

```make
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
	@if [ -d $(FRONTEND)/node_modules ]; then cd $(FRONTEND) && $(NPM) test; fi

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
```

- [ ] **Step 5: Verify build and serving**

```bash
cd ~/Development/apollo
make build
ls frontend/dist/index.html
PORT=8777 uv run python main.py & sleep 2
curl -s -o /dev/null -w "%{http_code}\n" localhost:8777/ui/
kill %1
```
Expected: `make build` ends `Build complete.`; the `ls` prints the path; curl prints `200`.

- [ ] **Step 6: Commit**

```bash
git add Makefile frontend
git status --short | grep -E 'node_modules|dist/' && echo "STOP: build output staged" || echo "ok"
git commit -m "chore: scaffold Svelte frontend and wire it into make build"
```
Expected: `ok` (`frontend/node_modules` and `frontend/dist` are gitignored). `package-lock.json` must be in the commit — `npm ci` depends on it.

---

### Task 2: Types and pure helpers

**Files:**
- Create: `frontend/src/lib/types.ts`, `frontend/src/lib/dates.ts`, `frontend/src/lib/format.ts`, `frontend/src/lib/route.ts`
- Test: `frontend/src/lib/dates.test.ts`, `frontend/src/lib/format.test.ts`, `frontend/src/lib/route.test.ts`

- [ ] **Step 1: Create `frontend/src/lib/types.ts`**

```ts
// Mirrors the backend's schemas/ and core/api.py responses.
// Weights and distances arrive in the user's display units; durations in seconds.

export type FieldName = 'weight' | 'reps' | 'distance' | 'duration';
export type Kind = 'workout' | 'selfcare';
export type CalendarView = 'week' | 'month' | 'year';
export type Range = '1W' | '1M' | '1Y';
export type WeekStart = 'monday' | 'sunday';

export interface ExerciseDef { key: string; name: string; type: string; groups: string[] }
export interface SelfcareTypeDef { key: string; name: string; every_days: number | null }
export interface SelfcareCategoryDef { key: string; name: string; types: SelfcareTypeDef[] }

export interface Catalog {
  metric_types: Record<string, FieldName[]>;
  muscle_groups: string[];
  exercises_by_group: Record<string, ExerciseDef[]>;
  selfcare: SelfcareCategoryDef[];
  colors: Record<Kind, string>;
}

export interface Settings {
  calendar_view: CalendarView;
  week_start: WeekStart;
  weight_unit: 'lb' | 'kg';
  distance_unit: 'mi' | 'km';
  history_range: Range;
}

export interface Health { status: 'ok' | 'degraded'; config_errors: string[] }

export interface WorkoutSet {
  id: number;
  position: number;
  done: boolean;
  weight: number | null;
  reps: number | null;
  distance: number | null;
  duration: number | null;
}

export type SetPatch = Partial<Record<FieldName, number | null>> & { done?: boolean };

export interface WorkoutExercise {
  id: number;
  position: number;
  exercise_key: string;
  name: string;
  metric_type: string;
  fields: FieldName[];
  muscle_groups: string[];
  planned: boolean;
  notes: string | null;
  sets: WorkoutSet[];
}

export interface Workout {
  id: number;
  started_at: string;
  ended_at: string | null;
  local_date: string;
  notes: string | null;
  focus: string[];
  exercises: WorkoutExercise[];
  stale: boolean;
}

export interface WorkoutSummary {
  id: number;
  local_date: string;
  started_at: string;
  ended_at: string;
  duration_s: number;
  focus: string[];
  exercise_count: number;
  set_count: number;
}

export interface FinishResult { workout: Workout | null; deleted: boolean }

export interface SelfcareSession {
  id: number;
  category_key: string;
  category_name: string;
  local_date: string;
  performed_at: string;
  notes: string | null;
  types: { key: string; name: string }[];
}

export type DueStatus = 'never' | 'ok' | 'soon' | 'due' | 'overdue' | 'untracked';

export interface DueItem {
  category_key: string;
  type_key: string;
  type_name: string;
  every_days: number | null;
  last_done: string | null;
  next_due: string | null;
  days_since: number | null;
  days_over: number | null;
  ratio: number | null;
  status: DueStatus;
}

export interface CalendarEntry { kind: Kind; id: number; title: string; summary: string; in_progress: boolean }
export interface CalendarDay { date: string; entries: CalendarEntry[] }
export interface LastDone { workout: string | null; selfcare: string | null; types: Record<string, string> }
```

- [ ] **Step 2: Write the failing tests** — `frontend/src/lib/dates.test.ts`

```ts
import { describe, expect, it } from 'vitest';
import {
  addDays, addMonths, dayLabel, diffDays, longDate, monthGrid, monthLabel,
  rangeFor, shortDate, startOfWeek, weekdayIndex, weekdayLabels, yearRows,
} from './dates';

// 2026-09-22 is a Tuesday; 2026-09-01 a Tuesday; 2026-09-30 a Wednesday.
describe('dates', () => {
  it('does day arithmetic across months and years', () => {
    expect(addDays('2026-09-30', 1)).toBe('2026-10-01');
    expect(addDays('2026-01-01', -1)).toBe('2025-12-31');
    expect(diffDays('2026-09-22', '2026-09-20')).toBe(2);
  });

  it('knows the week start', () => {
    expect(weekdayIndex('2026-09-22', 'monday')).toBe(1);
    expect(weekdayIndex('2026-09-22', 'sunday')).toBe(2);
    expect(startOfWeek('2026-09-22', 'monday')).toBe('2026-09-21');
    expect(startOfWeek('2026-09-22', 'sunday')).toBe('2026-09-20');
    expect(weekdayLabels('sunday')[0]).toBe('Sun');
  });

  it('adds months from the first of the month', () => {
    expect(addMonths('2026-12-15', 1)).toBe('2027-01-01');
    expect(addMonths('2026-01-31', -1)).toBe('2025-12-01');
  });

  it('builds a month grid of whole weeks', () => {
    const g = monthGrid('2026-09-22', 'monday');
    expect(g.map((w) => w[0])).toEqual(['2026-08-31', '2026-09-07', '2026-09-14', '2026-09-21', '2026-09-28']);
    expect(g[4][6]).toBe('2026-10-04');
    expect(monthGrid('2026-09-22', 'sunday')[0][0]).toBe('2026-08-30');
  });

  it('builds 53 year rows, newest first', () => {
    const rows = yearRows('2026-09-22', 'monday');
    expect(rows).toHaveLength(53);
    expect(rows[0][0]).toBe('2026-09-21');
    expect(rows[52][0]).toBe('2025-09-22');
  });

  it('computes fetch ranges per view', () => {
    expect(rangeFor('week', '2026-09-22', 'monday')).toEqual({ from: '2026-09-21', to: '2026-09-27' });
    expect(rangeFor('month', '2026-09-22', 'monday')).toEqual({ from: '2026-08-31', to: '2026-10-04' });
    expect(rangeFor('year', '2026-09-22', 'monday')).toEqual({ from: '2025-09-22', to: '2026-09-27' });
  });

  it('formats labels', () => {
    expect(monthLabel('2026-09-22')).toBe('September 2026');
    expect(shortDate('2026-09-22')).toBe('Sep 22');
    expect(longDate('2026-09-22')).toBe('Tuesday, September 22');
    expect(dayLabel('2026-09-22')).toBe('Tue 22');
  });
});
```

`frontend/src/lib/format.test.ts`

```ts
import { describe, expect, it } from 'vitest';
import { dueText, formatDuration, formatMinutes, heatLevel, parseDuration, relativeDays, titleCase } from './format';
import type { DueItem } from './types';

const due = (over: Partial<DueItem>): DueItem => ({
  category_key: 'skincare', type_key: 'x', type_name: 'X', every_days: 7, last_done: null,
  next_due: null, days_since: null, days_over: null, ratio: null, status: 'ok', ...over,
});

describe('format', () => {
  it('formats durations', () => {
    expect(formatDuration(null)).toBe('');
    expect(formatDuration(59)).toBe('0:59');
    expect(formatDuration(90)).toBe('1:30');
    expect(formatDuration(3723)).toBe('1:02:03');
    expect(formatMinutes(2700)).toBe('45 min');
    expect(formatMinutes(5400)).toBe('1 h 30 min');
  });

  it('parses durations', () => {
    expect(parseDuration('1:30')).toBe(90);
    expect(parseDuration('1:02:03')).toBe(3723);
    expect(parseDuration('45')).toBe(45);
    expect(parseDuration('30', 'minutes')).toBe(1800);
    expect(parseDuration('')).toBeNull();
    expect(parseDuration('1:75')).toBeNull();
    expect(parseDuration('abc')).toBeNull();
  });

  it('describes relative days', () => {
    expect(relativeDays('2026-09-22', '2026-09-22')).toBe('today');
    expect(relativeDays('2026-09-21', '2026-09-22')).toBe('yesterday');
    expect(relativeDays('2026-09-19', '2026-09-22')).toBe('3 days ago');
    expect(relativeDays('2026-09-24', '2026-09-22')).toBe('in 2 days');
  });

  it('describes due items', () => {
    expect(dueText(due({ status: 'never' }))).toBe('never done');
    expect(dueText(due({ status: 'overdue', days_over: 1 }))).toBe('1 day overdue');
    expect(dueText(due({ status: 'overdue', days_over: 4 }))).toBe('4 days overdue');
    expect(dueText(due({ status: 'due', days_over: 0 }))).toBe('due today');
    expect(dueText(due({ status: 'soon', days_over: -1 }))).toBe('due tomorrow');
    expect(dueText(due({ status: 'ok', days_over: -5 }))).toBe('due in 5 days');
    expect(dueText(due({ status: 'untracked', days_since: 2 }))).toBe('last 2 days ago');
    expect(dueText(due({ status: 'untracked', days_since: null }))).toBe('not logged yet');
  });

  it('maps counts to heat levels and title-cases', () => {
    expect([0, 1, 2, 3, 9].map(heatLevel)).toEqual([0, 1, 2, 3, 3]);
    expect(titleCase('chest')).toBe('Chest');
  });
});
```

`frontend/src/lib/route.test.ts`

```ts
import { describe, expect, it } from 'vitest';
import { buildHash, parseHash } from './route';

describe('route', () => {
  it('defaults to the calendar', () => {
    expect(parseHash('')).toEqual({ path: ['calendar'], query: {} });
    expect(parseHash('#/')).toEqual({ path: ['calendar'], query: {} });
  });

  it('parses path and query', () => {
    expect(parseHash('#/workouts/42?edit=1')).toEqual({ path: ['workouts', '42'], query: { edit: '1' } });
    expect(parseHash('#/calendar/day/2026-09-22')).toEqual({ path: ['calendar', 'day', '2026-09-22'], query: {} });
  });

  it('builds hashes and drops empty values', () => {
    expect(buildHash(['calendar'], { view: 'month', kind: undefined, date: '' })).toBe('#/calendar?view=month');
    expect(buildHash(['workouts', 'active'])).toBe('#/workouts/active');
  });

  it('round-trips', () => {
    const hash = buildHash(['calendar'], { view: 'year', kind: 'workout' });
    expect(parseHash(hash)).toEqual({ path: ['calendar'], query: { view: 'year', kind: 'workout' } });
  });
});
```

- [ ] **Step 3: Run to verify failure**

Run: `cd frontend && npm test`
Expected: FAIL — cannot resolve `./dates`, `./format`, `./route`.

- [ ] **Step 4: Implement `frontend/src/lib/dates.ts`**

```ts
// ISO local dates ('YYYY-MM-DD') as plain strings. All arithmetic is done in
// UTC so the browser's own timezone can never shift a day — the server decides
// what "today" is (GET /api/today).

import type { CalendarView, WeekStart } from './types';

export type ISODate = string;

const DAY_MS = 86_400_000;
const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export function parseISO(d: ISODate): Date {
  const [y, m, day] = d.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, day));
}

export function toISO(d: Date): ISODate {
  return d.toISOString().slice(0, 10);
}

export function addDays(d: ISODate, n: number): ISODate {
  return toISO(new Date(parseISO(d).getTime() + n * DAY_MS));
}

export function diffDays(a: ISODate, b: ISODate): number {
  return Math.round((parseISO(a).getTime() - parseISO(b).getTime()) / DAY_MS);
}

/** Position of `d` in its week: 0 is the configured first day. */
export function weekdayIndex(d: ISODate, weekStart: WeekStart): number {
  const js = parseISO(d).getUTCDay(); // 0 = Sunday
  return weekStart === 'monday' ? (js + 6) % 7 : js;
}

export function startOfWeek(d: ISODate, weekStart: WeekStart): ISODate {
  return addDays(d, -weekdayIndex(d, weekStart));
}

export function startOfMonth(d: ISODate): ISODate {
  return `${d.slice(0, 8)}01`;
}

/** First day of the month `n` months from `d`'s month. */
export function addMonths(d: ISODate, n: number): ISODate {
  const x = parseISO(startOfMonth(d));
  x.setUTCMonth(x.getUTCMonth() + n);
  return toISO(x);
}

export function endOfMonth(d: ISODate): ISODate {
  return addDays(addMonths(d, 1), -1);
}

export function weekDays(anchor: ISODate, weekStart: WeekStart): ISODate[] {
  const start = startOfWeek(anchor, weekStart);
  return Array.from({ length: 7 }, (_, i) => addDays(start, i));
}

/** Whole weeks covering `anchor`'s month. */
export function monthGrid(anchor: ISODate, weekStart: WeekStart): ISODate[][] {
  const last = endOfMonth(anchor);
  const weeks: ISODate[][] = [];
  for (let s = startOfWeek(startOfMonth(anchor), weekStart); s <= last; s = addDays(s, 7)) {
    weeks.push(Array.from({ length: 7 }, (_, i) => addDays(s, i)));
  }
  return weeks;
}

/** `count` week rows, newest (the week containing `anchor`) first. */
export function yearRows(anchor: ISODate, weekStart: WeekStart, count = 53): ISODate[][] {
  const start = startOfWeek(anchor, weekStart);
  return Array.from({ length: count }, (_, r) => {
    const rowStart = addDays(start, -7 * r);
    return Array.from({ length: 7 }, (_, i) => addDays(rowStart, i));
  });
}

export function rangeFor(view: CalendarView, anchor: ISODate, weekStart: WeekStart): { from: ISODate; to: ISODate } {
  if (view === 'week') {
    const days = weekDays(anchor, weekStart);
    return { from: days[0], to: days[6] };
  }
  if (view === 'month') {
    const grid = monthGrid(anchor, weekStart);
    return { from: grid[0][0], to: grid[grid.length - 1][6] };
  }
  const rows = yearRows(anchor, weekStart);
  return { from: rows[rows.length - 1][0], to: rows[0][6] };
}

export function weekdayLabels(weekStart: WeekStart): string[] {
  return weekStart === 'monday' ? [...WEEKDAYS.slice(1), WEEKDAYS[0]] : [...WEEKDAYS];
}

function fmt(d: ISODate, options: Intl.DateTimeFormatOptions): string {
  return parseISO(d).toLocaleDateString('en-US', { timeZone: 'UTC', ...options });
}

export const monthLabel = (d: ISODate) => fmt(d, { month: 'long', year: 'numeric' });
export const monthShort = (d: ISODate) => fmt(d, { month: 'short' });
export const shortDate = (d: ISODate) => fmt(d, { month: 'short', day: 'numeric' });
export const longDate = (d: ISODate) => fmt(d, { weekday: 'long', month: 'long', day: 'numeric' });
export const dayLabel = (d: ISODate) => `${WEEKDAYS[parseISO(d).getUTCDay()]} ${Number(d.slice(8))}`;
```

- [ ] **Step 5: Implement `frontend/src/lib/format.ts`**

```ts
import { diffDays, type ISODate } from './dates';
import type { DueItem } from './types';

export function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`;
}

export function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Seconds → "m:ss" or "h:mm:ss"; null → "". */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '';
  const t = Math.max(0, Math.round(seconds));
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = String(t % 60).padStart(2, '0');
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`;
}

export function formatMinutes(seconds: number): string {
  const m = Math.round(seconds / 60);
  return m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`;
}

/**
 * "m:ss" / "h:mm:ss" → seconds. A bare number is seconds, or minutes when
 * `plain` is 'minutes' (runs are entered in minutes, planks in seconds).
 */
export function parseDuration(text: string, plain: 'seconds' | 'minutes' = 'seconds'): number | null {
  const t = text.trim();
  if (t === '') return null;
  if (/^\d+(\.\d+)?$/.test(t)) {
    const n = Number(t);
    return Math.round(plain === 'minutes' ? n * 60 : n);
  }
  const m = /^(?:(\d+):)?(\d{1,2}):(\d{2})$/.exec(t);
  if (!m) return null;
  const [, h, mm, ss] = m;
  if (Number(ss) > 59 || (h !== undefined && Number(mm) > 59)) return null;
  return Number(h ?? 0) * 3600 + Number(mm) * 60 + Number(ss);
}

function ago(days: number): string {
  if (days === 0) return 'today';
  if (days === 1) return 'yesterday';
  return `${days} days ago`;
}

export function relativeDays(date: ISODate, today: ISODate): string {
  const d = diffDays(today, date);
  if (d === -1) return 'tomorrow';
  return d >= 0 ? ago(d) : `in ${-d} days`;
}

export function dueText(item: DueItem): string {
  switch (item.status) {
    case 'never':
      return 'never done';
    case 'untracked':
      return item.days_since === null ? 'not logged yet' : `last ${ago(item.days_since)}`;
    case 'overdue':
      return `${plural(item.days_over ?? 0, 'day')} overdue`;
    case 'due':
      return 'due today';
    default: {
      const inDays = -(item.days_over ?? 0);
      return inDays === 1 ? 'due tomorrow' : `due in ${inDays} days`;
    }
  }
}

/** Sessions on a day → heatmap shade level 0–3. */
export function heatLevel(count: number): 0 | 1 | 2 | 3 {
  if (count <= 0) return 0;
  if (count === 1) return 1;
  if (count === 2) return 2;
  return 3;
}
```

- [ ] **Step 6: Implement `frontend/src/lib/route.ts`**

```ts
// Hash routes: '#/workouts/42?edit=1'. Everything after '#' stays in the
// browser; the server always serves the same index.html at /ui/.

export interface Route {
  path: string[];
  query: Record<string, string>;
}

export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#\/?/, '');
  const [p, q = ''] = raw.split('?');
  const path = p.split('/').filter(Boolean).map(decodeURIComponent);
  return { path: path.length ? path : ['calendar'], query: Object.fromEntries(new URLSearchParams(q)) };
}

export function buildHash(path: string[], query: Record<string, string | undefined> = {}): string {
  const pairs = Object.entries(query).filter((e): e is [string, string] => e[1] !== undefined && e[1] !== '');
  const qs = new URLSearchParams(pairs).toString();
  return `#/${path.map(encodeURIComponent).join('/')}${qs ? `?${qs}` : ''}`;
}
```

- [ ] **Step 7: Run tests**

Run: `cd frontend && npm test`
Expected: all tests in the three files pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib
git commit -m "feat(ui): API types and date/format/route helpers"
```

---

### Task 3: API client and shared state

**Files:**
- Create: `frontend/src/lib/api.ts`, `app.svelte.ts`, `router.svelte.ts`, `toast.svelte.ts`, `motion.ts`, `recent.ts`, `entries.ts` (all in `frontend/src/lib/`)

- [ ] **Step 1: `frontend/src/lib/api.ts`**

```ts
import type {
  CalendarDay, Catalog, DueItem, FinishResult, Health, Kind, LastDone, Range,
  SelfcareSession, SetPatch, Settings, Workout, WorkoutExercise, WorkoutSet, WorkoutSummary,
} from './types';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function detailOf(body: unknown): string | null {
  if (!body || typeof body !== 'object' || !('detail' in body)) return null;
  const detail = (body as { detail: unknown }).detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => (d as { msg?: string }).msg ?? String(d)).join('; ');
  return null;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 204) return undefined as T;
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, detailOf(data) ?? res.statusText);
  return data as T;
}

const q = (params: Record<string, string | undefined>) => {
  const pairs = Object.entries(params).filter((e): e is [string, string] => e[1] !== undefined);
  return pairs.length ? `?${new URLSearchParams(pairs)}` : '';
};

export const api = {
  health: () => request<Health>('GET', '/health'),
  today: () => request<{ today: string }>('GET', '/today'),
  catalog: () => request<Catalog>('GET', '/catalog'),
  settings: () => request<Settings>('GET', '/settings'),
  setSetting: (key: keyof Settings, value: string) => request<void>('PUT', `/settings/${key}`, { value }),

  startWorkout: (planned: string[] = []) => request<Workout>('POST', '/workouts', { planned_exercises: planned }),
  openWorkout: () => request<Workout | null>('GET', '/workouts/open'),
  workouts: (range: Range) => request<WorkoutSummary[]>('GET', `/workouts${q({ range })}`),
  workout: (id: number) => request<Workout>('GET', `/workouts/${id}`),
  addExercise: (id: number, key: string) =>
    request<WorkoutExercise>('POST', `/workouts/${id}/exercises`, { exercise_key: key }),
  removeExercise: (id: number, weId: number) => request<void>('DELETE', `/workouts/${id}/exercises/${weId}`),
  addSet: (id: number, weId: number) => request<WorkoutSet>('POST', `/workouts/${id}/exercises/${weId}/sets`),
  updateSet: (setId: number, patch: SetPatch) => request<WorkoutSet>('PATCH', `/sets/${setId}`, patch),
  deleteSet: (setId: number) => request<void>('DELETE', `/sets/${setId}`),
  finishWorkout: (id: number, atLastActivity = false) =>
    request<FinishResult>('POST', `/workouts/${id}/finish${q({ end_at_last_activity: atLastActivity ? 'true' : undefined })}`),
  reopenWorkout: (id: number) => request<Workout>('POST', `/workouts/${id}/reopen`),
  deleteWorkout: (id: number) => request<void>('DELETE', `/workouts/${id}`),

  logSelfcare: (body: { category: string; types: string[]; date?: string; notes?: string | null }) =>
    request<SelfcareSession>('POST', '/selfcare/sessions', body),
  selfcareSessions: (range: Range, category?: string) =>
    request<SelfcareSession[]>('GET', `/selfcare/sessions${q({ range, category })}`),
  selfcareSession: (id: number) => request<SelfcareSession>('GET', `/selfcare/sessions/${id}`),
  updateSelfcare: (id: number, body: { types?: string[]; date?: string; notes?: string | null }) =>
    request<SelfcareSession>('PATCH', `/selfcare/sessions/${id}`, body),
  deleteSelfcare: (id: number) => request<void>('DELETE', `/selfcare/sessions/${id}`),
  due: () => request<DueItem[]>('GET', '/selfcare/due'),

  calendar: (from: string, to: string, kinds: Kind[]) =>
    request<CalendarDay[]>('GET', `/calendar${q({ from, to, kinds: kinds.join(',') })}`),
  lastDone: () => request<LastDone>('GET', '/calendar/last-done'),
};
```

- [ ] **Step 2: `frontend/src/lib/toast.svelte.ts`**

```ts
export interface ToastItem { id: number; text: string; kind: 'info' | 'error' }

export const toasts: ToastItem[] = $state([]);
let nextId = 1;

export function toast(text: string, kind: 'info' | 'error' = 'info'): void {
  const id = nextId++;
  toasts.push({ id, text, kind });
  setTimeout(() => {
    const i = toasts.findIndex((t) => t.id === id);
    if (i >= 0) toasts.splice(i, 1);
  }, kind === 'error' ? 5000 : 2500);
}

export function toastError(error: unknown): void {
  toast(error instanceof Error ? error.message : String(error), 'error');
}
```

- [ ] **Step 3: `frontend/src/lib/app.svelte.ts`**

```ts
// App-wide state loaded once at boot: catalog (YAML), settings (DB), and the
// server's "today" (timezone + day-start hour applied).

import { api } from './api';
import type { Catalog, Kind, Settings } from './types';

interface AppState {
  ready: boolean;
  error: string | null;
  catalog: Catalog | null;
  settings: Settings | null;
  today: string;
  configErrors: string[];
}

export const app: AppState = $state({
  ready: false, error: null, catalog: null, settings: null, today: '', configErrors: [],
});

function applyColors(colors: Record<Kind, string>): void {
  const root = document.documentElement.style;
  root.setProperty('--color-workout', colors.workout);
  root.setProperty('--color-selfcare', colors.selfcare);
}

export async function loadApp(): Promise<void> {
  try {
    const [catalog, settings, today, health] = await Promise.all([
      api.catalog(), api.settings(), api.today(), api.health(),
    ]);
    app.catalog = catalog;
    app.settings = settings;
    app.today = today.today;
    app.configErrors = health.config_errors;
    applyColors(catalog.colors);
    app.ready = true;
  } catch (e) {
    app.error = `Could not reach the Apollo server (${(e as Error).message}).`;
  }
}

/** Called when the page becomes visible again — the day may have rolled over. */
export async function refreshToday(): Promise<void> {
  try {
    app.today = (await api.today()).today;
  } catch {
    /* offline; keep the old value */
  }
}

export async function updateSetting<K extends keyof Settings>(key: K, value: Settings[K]): Promise<void> {
  await api.setSetting(key, value);
  if (app.settings) app.settings[key] = value;
}
```

- [ ] **Step 4: `frontend/src/lib/motion.ts`**

```ts
/** Transition duration that collapses to 0 under prefers-reduced-motion. */
export function dur(ms: number): number {
  return typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : ms;
}
```

- [ ] **Step 5: `frontend/src/lib/router.svelte.ts`**

```ts
// History-aware hash router. Each navigation pushes a history entry carrying
// its index, so popstate can tell back from forward (for the slide direction).
// Screen changes run inside document.startViewTransition where supported
// (iOS 18+, Chromium) and just swap otherwise.

import { tick } from 'svelte';
import { buildHash, parseHash, type Route } from './route';

export const router: { route: Route } = $state({ route: parseHash(location.hash) });

let index = 0;

type ViewTransitionDoc = Document & { startViewTransition?: (cb: () => Promise<void>) => unknown };

function apply(route: Route, direction: 'forward' | 'back', animate: boolean): void {
  const doc = document as ViewTransitionDoc;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!animate || reduce || !doc.startViewTransition) {
    router.route = route;
    return;
  }
  document.documentElement.dataset.nav = direction;
  doc.startViewTransition(async () => {
    router.route = route;
    await tick();
  });
}

export function initRouter(): void {
  if (!location.hash) history.replaceState({ idx: 0 }, '', buildHash(['calendar']));
  else history.replaceState({ idx: 0 }, '');
  index = 0;
  router.route = parseHash(location.hash);
  addEventListener('popstate', (event: PopStateEvent) => {
    const idx = typeof event.state?.idx === 'number' ? (event.state.idx as number) : 0;
    const direction = idx < index ? 'back' : 'forward';
    index = idx;
    apply(parseHash(location.hash), direction, true);
  });
}

export function navigate(
  path: string[],
  query: Record<string, string | undefined> = {},
  opts: { replace?: boolean } = {},
): void {
  const hash = buildHash(path, query);
  if (opts.replace) {
    history.replaceState({ idx: index }, '', hash);
  } else {
    index += 1;
    history.pushState({ idx: index }, '', hash);
  }
  apply(parseHash(hash), 'forward', !opts.replace);
}

/** In-app back: browser history when there is some, else a sensible parent. */
export function goBack(fallback: string[]): void {
  if (index > 0) history.back();
  else navigate(fallback, {}, { replace: true });
}
```

- [ ] **Step 6: `frontend/src/lib/recent.ts`**

```ts
// Recently picked exercises, per device. A convenience only — failures are ignored.
const KEY = 'apollo.recentExercises';
const MAX = 6;

export function readRecent(): string[] {
  try {
    const raw = localStorage.getItem(KEY);
    const list: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list.filter((x): x is string => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

export function rememberRecent(key: string): void {
  try {
    const next = [key, ...readRecent().filter((k) => k !== key)].slice(0, MAX);
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable */
  }
}
```

- [ ] **Step 7: `frontend/src/lib/entries.ts`**

```ts
import { navigate } from './router.svelte';
import type { CalendarEntry } from './types';

/** Open the detail screen for a calendar entry. */
export function openEntry(entry: CalendarEntry): void {
  if (entry.kind === 'workout') {
    navigate(entry.in_progress ? ['workouts', 'active'] : ['workouts', String(entry.id)]);
  } else {
    navigate(['selfcare', String(entry.id)]);
  }
}
```

- [ ] **Step 8: Type-check and test**

Run: `cd frontend && npm run check && npm test`
Expected: `svelte-check found 0 errors`; tests pass.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib
git commit -m "feat(ui): API client, app state, router and toasts"
```

---

### Task 4: Styles, shell, navigation and screen stubs

**Files:**
- Create: `frontend/src/styles/tokens.css`, `frontend/public/manifest.webmanifest`, `frontend/public/icon.svg`
- Create: `frontend/src/components/{Icon,TabBar,BackBar,Toast}.svelte`
- Create: 11 screen stubs under `frontend/src/screens/`
- Replace: `frontend/index.html`, `frontend/src/main.ts`, `frontend/src/app.css`, `frontend/src/App.svelte`

- [ ] **Step 1: `frontend/src/styles/tokens.css`** — Hestia's token names, plus kind colors and a light palette.

```css
/* Design tokens. Every color, radius, spacing, duration and type size used by
 * a component is one of these. Names match Hestia's so the sibling projects
 * can share a palette. --color-workout / --color-selfcare are overwritten at
 * boot from config/apollo.yaml (GET /api/catalog). */

:root {
  color-scheme: dark;

  --color-bg: #0d1117;
  --color-surface: #161b22;
  --color-surface-2: #1f2630;
  --color-surface-3: #2a323d;
  --color-text: #e6edf3;
  --color-text-muted: #8b949e;
  --color-text-faint: #6e7681;
  --color-border: #30363d;
  --color-border-soft: #21262d;
  --color-accent: #4ade80;
  --color-accent-soft: #4ade8030;
  --color-accent-dim: #22c55e;
  --color-danger: #f87171;
  --color-warn: #fbbf24;
  --color-warn-soft: #fbbf2422;
  --color-workout: #4ade80;
  --color-selfcare: #60a5fa;
  --color-on-accent: #0d1117;

  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-xl: 22px;
  --radius-pill: 999px;

  --shadow-1: 0 1px 2px rgba(0, 0, 0, 0.25);
  --shadow-2: 0 4px 14px rgba(0, 0, 0, 0.35);

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 48px;

  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-md: 1rem;
  --text-lg: 1.25rem;
  --text-xl: 1.5rem;

  --transition: 180ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-fast: 120ms cubic-bezier(0.4, 0, 0.2, 1);
  --nav-duration: 220ms;

  --font-stack: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;

  --tap-min: 44px;
  --tabbar-h: 58px;
  --content-max: 640px;

  --safe-top: env(safe-area-inset-top, 0px);
  --safe-right: env(safe-area-inset-right, 0px);
  --safe-bottom: env(safe-area-inset-bottom, 0px);
  --safe-left: env(safe-area-inset-left, 0px);
}

@media (prefers-color-scheme: light) {
  :root {
    color-scheme: light;
    --color-bg: #f6f8fa;
    --color-surface: #ffffff;
    --color-surface-2: #eef1f4;
    --color-surface-3: #dde2e8;
    --color-text: #1f2328;
    --color-text-muted: #59636e;
    --color-text-faint: #818b98;
    --color-border: #d1d9e0;
    --color-border-soft: #e5eaef;
    --color-accent: #16a34a;
    --color-accent-soft: #16a34a22;
    --color-accent-dim: #15803d;
    --color-danger: #dc2626;
    --color-warn: #b45309;
    --color-warn-soft: #b4530922;
    --color-on-accent: #ffffff;
    --shadow-1: 0 1px 2px rgba(0, 0, 0, 0.08);
    --shadow-2: 0 4px 14px rgba(0, 0, 0, 0.12);
  }
}
```

- [ ] **Step 2: `frontend/src/app.css`** — global layout and shared component classes.

```css
*, *::before, *::after { box-sizing: border-box; }

html, body { margin: 0; background: var(--color-bg); }

body {
  color: var(--color-text);
  font-family: var(--font-stack);
  font-size: var(--text-md);
  -webkit-font-smoothing: antialiased;
  -webkit-tap-highlight-color: transparent;
}

h1 { font-size: var(--text-xl); margin: 0; }
h2 { font-size: var(--text-lg); margin: 0; }
p { margin: 0; }

button, input, select, textarea { font: inherit; color: inherit; }
input, select, textarea { font-size: max(16px, var(--text-md)); } /* no iOS zoom-on-focus */

/* ------------------------------------------------------------ layout */

.screen {
  max-width: var(--content-max);
  margin: 0 auto;
  padding: calc(var(--space-4) + var(--safe-top)) calc(var(--space-4) + var(--safe-right))
    calc(var(--tabbar-h) + var(--safe-bottom) + var(--space-8)) calc(var(--space-4) + var(--safe-left));
  display: grid;
  gap: var(--space-4);
  view-transition-name: screen;
}

@media (min-width: 900px) {
  .screen { padding-top: calc(var(--tabbar-h) + var(--space-6) + var(--safe-top)); padding-bottom: var(--space-10); }
}

.page-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
.center-state { display: grid; place-items: center; gap: var(--space-4); padding: var(--space-10) 0; text-align: center; }
.muted { color: var(--color-text-muted); }
.row { display: flex; gap: var(--space-2); flex-wrap: wrap; align-items: center; }
.stack { display: grid; gap: var(--space-3); }
.section-title { font-size: var(--text-sm); color: var(--color-text-muted); text-transform: uppercase; letter-spacing: 0.06em; margin: var(--space-2) 0 0; }

/* ------------------------------------------------------------ buttons */

.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: var(--space-2);
  min-height: var(--tap-min); padding: 0 var(--space-4);
  background: var(--color-surface-2); border: 1px solid var(--color-border);
  border-radius: var(--radius-md); cursor: pointer;
  transition: background var(--transition-fast), border-color var(--transition-fast), transform var(--transition-fast);
}
.btn:active:not(:disabled) { transform: scale(0.98); }
.btn:disabled { opacity: 0.5; cursor: default; }
.btn.primary { background: var(--color-accent); border-color: var(--color-accent); color: var(--color-on-accent); font-weight: 600; }
.btn.danger { background: none; border-color: var(--color-danger); color: var(--color-danger); }
.btn.big { min-height: 56px; font-size: var(--text-lg); width: 100%; border-radius: var(--radius-lg); }
.btn.block { width: 100%; }
.btn.small { min-height: 32px; padding: 0 var(--space-3); font-size: var(--text-sm); }

.icon-btn {
  display: inline-grid; place-items: center; min-width: var(--tap-min); min-height: var(--tap-min);
  background: none; border: 0; border-radius: var(--radius-md); color: var(--color-text-muted); cursor: pointer;
}
.icon-btn:active { background: var(--color-surface-2); }

/* ------------------------------------------------------------ surfaces */

.card {
  display: grid; gap: var(--space-3); padding: var(--space-4);
  background: var(--color-surface); border: 1px solid var(--color-border);
  border-radius: var(--radius-lg); box-shadow: var(--shadow-1); text-align: left; color: inherit;
}
button.card { cursor: pointer; width: 100%; }

.banner { padding: var(--space-3) var(--space-4); border-radius: var(--radius-lg); background: var(--color-accent-soft); border: 1px solid var(--color-accent); }
.banner.warn { background: var(--color-warn-soft); border-color: var(--color-warn); }

.chips { display: flex; flex-wrap: wrap; gap: var(--space-1); }
.chip {
  display: inline-flex; align-items: center; padding: 2px var(--space-2);
  border-radius: var(--radius-pill); background: var(--color-surface-2);
  font-size: var(--text-xs); color: var(--color-text-muted);
}

.dot { display: inline-block; width: 8px; height: 8px; border-radius: var(--radius-pill); background: var(--color-text-faint); }
.dot.workout { background: var(--color-workout); }
.dot.selfcare { background: var(--color-selfcare); }

.segmented { display: inline-flex; padding: 3px; gap: 2px; background: var(--color-surface-2); border-radius: var(--radius-md); }
.segmented button {
  min-height: 36px; padding: 0 var(--space-3); border: 0; border-radius: calc(var(--radius-md) - 3px);
  background: none; color: var(--color-text-muted); cursor: pointer; font-size: var(--text-sm);
}
.segmented button.on { background: var(--color-surface); color: var(--color-text); box-shadow: var(--shadow-1); }

.field { display: grid; gap: var(--space-1); }
.field > span { font-size: var(--text-sm); color: var(--color-text-muted); }
.input {
  min-height: var(--tap-min); padding: 0 var(--space-3);
  background: var(--color-surface-2); border: 1px solid var(--color-border); border-radius: var(--radius-md);
}
textarea.input { padding: var(--space-2) var(--space-3); min-height: 88px; resize: vertical; }

/* ------------------------------------------------------------ sheets */

.backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5); border: 0; z-index: 30; }
.sheet {
  position: fixed; left: 0; right: 0; bottom: 0; z-index: 31;
  max-height: 85vh; overflow: auto; margin: 0 auto; max-width: var(--content-max);
  padding: var(--space-4) calc(var(--space-4) + var(--safe-right)) calc(var(--space-4) + var(--safe-bottom)) calc(var(--space-4) + var(--safe-left));
  background: var(--color-surface); border-radius: var(--radius-xl) var(--radius-xl) 0 0;
  box-shadow: var(--shadow-2); display: grid; gap: var(--space-4);
}
.sheet-actions { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-2); }

/* ------------------------------------------------------------ view transitions */

::view-transition-old(screen),
::view-transition-new(screen) { animation-duration: var(--nav-duration); animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1); }
html[data-nav='forward']::view-transition-old(screen) { animation-name: slide-out-left; }
html[data-nav='forward']::view-transition-new(screen) { animation-name: slide-in-right; }
html[data-nav='back']::view-transition-old(screen) { animation-name: slide-out-right; }
html[data-nav='back']::view-transition-new(screen) { animation-name: slide-in-left; }

@keyframes slide-in-right { from { transform: translateX(30%); opacity: 0; } }
@keyframes slide-out-left { to { transform: translateX(-15%); opacity: 0; } }
@keyframes slide-in-left { from { transform: translateX(-30%); opacity: 0; } }
@keyframes slide-out-right { to { transform: translateX(15%); opacity: 0; } }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
  ::view-transition-group(*), ::view-transition-old(*), ::view-transition-new(*) { animation: none !important; }
}
```

- [ ] **Step 3: Replace `frontend/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
    <meta name="theme-color" content="#0d1117" />
    <meta name="apple-mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
    <meta name="apple-mobile-web-app-title" content="Apollo" />
    <link rel="icon" type="image/svg+xml" href="%BASE_URL%icon.svg" />
    <link rel="manifest" href="%BASE_URL%manifest.webmanifest" />
    <title>Apollo</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 4: `frontend/public/manifest.webmanifest` and `frontend/public/icon.svg`**

```json
{
  "name": "Apollo",
  "short_name": "Apollo",
  "description": "Workout and self-care tracking",
  "start_url": "/ui/",
  "scope": "/ui/",
  "display": "standalone",
  "orientation": "portrait",
  "background_color": "#0d1117",
  "theme_color": "#0d1117",
  "icons": [{ "src": "/ui/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any" }]
}
```

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#0d1117"/>
  <circle cx="32" cy="32" r="14" fill="none" stroke="#4ade80" stroke-width="4"/>
  <circle cx="32" cy="32" r="4" fill="#60a5fa"/>
</svg>
```

- [ ] **Step 5: Replace `frontend/src/main.ts`**

```ts
import { mount } from 'svelte';
import './styles/tokens.css';
import './app.css';
import App from './App.svelte';

const app = mount(App, { target: document.getElementById('app')! });

export default app;
```

- [ ] **Step 6: `frontend/src/components/Icon.svelte`**

```svelte
<script lang="ts">
  // Lucide-derived icons (https://lucide.dev, ISC license), inlined so they
  // work offline and inherit currentColor.
  const ICONS: Record<string, string> = {
    calendar: '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>',
    dumbbell: '<path d="M6.5 6.5v11"/><path d="M17.5 6.5v11"/><path d="M3 9v6"/><path d="M21 9v6"/><path d="M6.5 12h11"/>',
    sparkles: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 17v4"/><path d="M17 19h4"/>',
    sliders: '<path d="M4 21v-7"/><path d="M4 10V3"/><path d="M12 21v-9"/><path d="M12 8V3"/><path d="M20 21v-5"/><path d="M20 12V3"/><path d="M1 14h6"/><path d="M9 8h6"/><path d="M17 16h6"/>',
    'chevron-left': '<path d="m15 18-6-6 6-6"/>',
    'chevron-right': '<path d="m9 18 6-6-6-6"/>',
    plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
    minus: '<path d="M5 12h14"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    trash: '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
    play: '<polygon points="6 3 20 12 6 21 6 3"/>',
    stop: '<rect width="14" height="14" x="5" y="5" rx="2"/>',
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    chart: '<path d="M3 3v18h18"/><path d="M7 16v-4"/><path d="M12 16V8"/><path d="M17 16v-7"/>',
    more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  };

  let { name, size = 20 }: { name: string; size?: number } = $props();
</script>

<svg
  class="icon"
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="2"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true">{@html ICONS[name] ?? ''}</svg>

<style>
  .icon { flex: none; }
</style>
```

- [ ] **Step 7: `frontend/src/components/TabBar.svelte`**

```svelte
<script lang="ts">
  import Icon from './Icon.svelte';
  import { navigate } from '../lib/router.svelte';

  let { active }: { active: string } = $props();

  const TABS = [
    { key: 'calendar', label: 'Calendar', icon: 'calendar' },
    { key: 'workouts', label: 'Workouts', icon: 'dumbbell' },
    { key: 'selfcare', label: 'Self-care', icon: 'sparkles' },
    { key: 'settings', label: 'Settings', icon: 'sliders' },
  ];
</script>

<nav class="tabbar" aria-label="Sections">
  {#each TABS as tab (tab.key)}
    <button
      class:active={active === tab.key}
      aria-current={active === tab.key ? 'page' : undefined}
      onclick={() => navigate([tab.key])}>
      <Icon name={tab.icon} size={22} />
      <span>{tab.label}</span>
    </button>
  {/each}
</nav>

<style>
  .tabbar {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 20;
    display: flex; background: var(--color-surface);
    border-top: 1px solid var(--color-border);
    padding: 0 var(--safe-right) var(--safe-bottom) var(--safe-left);
    view-transition-name: tabbar;
  }
  button {
    flex: 1; min-height: var(--tabbar-h);
    display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;
    background: none; border: 0; color: var(--color-text-muted); font-size: var(--text-xs); cursor: pointer;
  }
  .active { color: var(--color-accent); }
  @media (min-width: 900px) {
    .tabbar {
      top: 0; bottom: auto; justify-content: center; border-top: 0;
      border-bottom: 1px solid var(--color-border); padding: var(--safe-top) 0 0;
    }
    button { flex: 0 0 150px; flex-direction: row; gap: var(--space-2); font-size: var(--text-sm); }
  }
</style>
```

- [ ] **Step 8: `frontend/src/components/BackBar.svelte`**

```svelte
<script lang="ts">
  import type { Snippet } from 'svelte';
  import Icon from './Icon.svelte';
  import { goBack } from '../lib/router.svelte';

  let { title, fallback, actions }: { title: string; fallback: string[]; actions?: Snippet } = $props();
</script>

<header class="backbar">
  <button class="icon-btn" onclick={() => goBack(fallback)} aria-label="Back">
    <Icon name="chevron-left" size={26} />
  </button>
  <h1>{title}</h1>
  <div class="actions">{@render actions?.()}</div>
</header>

<style>
  .backbar { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: var(--space-1); margin-left: calc(-1 * var(--space-3)); }
  h1 { font-size: var(--text-lg); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .actions { display: flex; }
</style>
```

- [ ] **Step 9: `frontend/src/components/Toast.svelte`**

```svelte
<script lang="ts">
  import { fly } from 'svelte/transition';
  import { dur } from '../lib/motion';
  import { toasts } from '../lib/toast.svelte';
</script>

<div class="toasts" aria-live="polite">
  {#each toasts as t (t.id)}
    <div class="toast {t.kind}" transition:fly={{ y: 16, duration: dur(180) }}>{t.text}</div>
  {/each}
</div>

<style>
  .toasts {
    position: fixed; left: 50%; transform: translateX(-50%); z-index: 40;
    bottom: calc(var(--tabbar-h) + var(--safe-bottom) + var(--space-3));
    display: grid; gap: var(--space-2); width: min(92vw, 420px); pointer-events: none;
  }
  .toast {
    padding: var(--space-3) var(--space-4); border-radius: var(--radius-md);
    background: var(--color-surface-3); box-shadow: var(--shadow-2); font-size: var(--text-sm);
  }
  .toast.error { background: var(--color-danger); color: var(--color-on-accent); }
</style>
```

- [ ] **Step 10: Create the 11 screen stubs** (each is replaced by a later task)

```bash
cd ~/Development/apollo/frontend/src
mkdir -p screens/calendar screens/workouts screens/selfcare screens/settings
for f in calendar/CalendarScreen calendar/DayScreen \
         workouts/WorkoutsHub workouts/ActiveWorkout workouts/WorkoutHistory workouts/WorkoutDetail \
         selfcare/SelfcareHub selfcare/SelfcareLog selfcare/SelfcareHistory selfcare/SelfcareDetail \
         settings/SettingsScreen; do
  name=$(basename "$f")
  cat > "screens/$f.svelte" <<EOF
<script lang="ts">
  // Stub — replaced by its screen task.
  let props: Record<string, unknown> = \$props();
</script>

<h1>$name</h1>
<pre class="muted">{JSON.stringify(props)}</pre>
EOF
done
ls screens/*/
```
Expected: 11 `.svelte` files listed.

- [ ] **Step 11: Replace `frontend/src/App.svelte`**

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import TabBar from './components/TabBar.svelte';
  import Toasts from './components/Toast.svelte';
  import { app, loadApp, refreshToday } from './lib/app.svelte';
  import { initRouter, router } from './lib/router.svelte';
  import CalendarScreen from './screens/calendar/CalendarScreen.svelte';
  import DayScreen from './screens/calendar/DayScreen.svelte';
  import ActiveWorkout from './screens/workouts/ActiveWorkout.svelte';
  import WorkoutDetail from './screens/workouts/WorkoutDetail.svelte';
  import WorkoutHistory from './screens/workouts/WorkoutHistory.svelte';
  import WorkoutsHub from './screens/workouts/WorkoutsHub.svelte';
  import SelfcareDetail from './screens/selfcare/SelfcareDetail.svelte';
  import SelfcareHistory from './screens/selfcare/SelfcareHistory.svelte';
  import SelfcareHub from './screens/selfcare/SelfcareHub.svelte';
  import SelfcareLog from './screens/selfcare/SelfcareLog.svelte';
  import SettingsScreen from './screens/settings/SettingsScreen.svelte';

  onMount(() => {
    initRouter();
    void loadApp();
    const onVisible = () => {
      if (document.visibilityState === 'visible') void refreshToday();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  });

  const path = $derived(router.route.path);
  const query = $derived(router.route.query);
  const tab = $derived(path[0] ?? 'calendar');
  const screenKey = $derived(path.join('/'));

  function numeric(segment: string | undefined): number | null {
    return segment !== undefined && /^\d+$/.test(segment) ? Number(segment) : null;
  }
</script>

<main class="screen">
  {#if !app.ready}
    <div class="center-state">
      {#if app.error}
        <p>{app.error}</p>
        <button class="btn" onclick={() => location.reload()}>Retry</button>
      {:else}
        <p class="muted">Loading…</p>
      {/if}
    </div>
  {:else}
    {#key screenKey}
      {#if tab === 'calendar' && path[1] === 'day' && path[2]}
        <DayScreen date={path[2]} kind={query.kind ?? 'all'} />
      {:else if tab === 'workouts' && path[1] === 'active'}
        <ActiveWorkout editing={query.edit === '1'} />
      {:else if tab === 'workouts' && path[1] === 'history'}
        <WorkoutHistory range={query.range} />
      {:else if tab === 'workouts' && numeric(path[1]) !== null}
        <WorkoutDetail id={numeric(path[1])!} />
      {:else if tab === 'workouts'}
        <WorkoutsHub />
      {:else if tab === 'selfcare' && path[1] === 'log'}
        <SelfcareLog id={numeric(path[2]) ?? undefined} initialDate={query.date} />
      {:else if tab === 'selfcare' && path[1] === 'history'}
        <SelfcareHistory range={query.range} />
      {:else if tab === 'selfcare' && numeric(path[1]) !== null}
        <SelfcareDetail id={numeric(path[1])!} />
      {:else if tab === 'selfcare'}
        <SelfcareHub />
      {:else if tab === 'settings'}
        <SettingsScreen />
      {:else}
        <CalendarScreen {query} />
      {/if}
    {/key}
  {/if}
</main>
<TabBar active={tab} />
<Toasts />
```

- [ ] **Step 12: Verify**

Run: `cd frontend && npm run check && npm test && npm run build`
Expected: 0 errors; tests pass; build succeeds.

Manual (`make run-dev`, open `http://localhost:5173/ui/`):
- The Calendar stub shows; the address bar reads `…/ui/#/calendar`.
- Tapping each tab switches the stub and the hash; Back returns to the previous tab.
- At a 390 px wide viewport (browser devtools, iPhone preset) the tab bar is at the bottom; above 900 px it moves to the top.

- [ ] **Step 13: Commit**

```bash
git add frontend
git commit -m "feat(ui): tokens, shell, tab bar, routing and screen stubs"
```

---

### Task 5: Shared components

**Files:**
- Create: `frontend/src/components/ConfirmSheet.svelte`, `RangeFilter.svelte`, `SessionCard.svelte`

- [ ] **Step 1: `ConfirmSheet.svelte`**

```svelte
<script lang="ts">
  import type { Snippet } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import { dur } from '../lib/motion';

  interface Props {
    title: string;
    confirmLabel: string;
    danger?: boolean;
    busy?: boolean;
    onconfirm: () => void;
    oncancel: () => void;
    children?: Snippet;
  }

  let { title, confirmLabel, danger = false, busy = false, onconfirm, oncancel, children }: Props = $props();
</script>

<button class="backdrop" aria-label="Close" onclick={oncancel} transition:fade={{ duration: dur(150) }}></button>
<div class="sheet" role="dialog" aria-modal="true" aria-label={title} transition:fly={{ y: 320, duration: dur(220) }}>
  <h2>{title}</h2>
  {@render children?.()}
  <div class="sheet-actions">
    <button class="btn" onclick={oncancel}>Cancel</button>
    <button class="btn {danger ? 'danger' : 'primary'}" disabled={busy} onclick={onconfirm}>{confirmLabel}</button>
  </div>
</div>
```

- [ ] **Step 2: `RangeFilter.svelte`**

```svelte
<script lang="ts">
  import type { Range } from '../lib/types';

  let { value, onchange }: { value: Range; onchange: (range: Range) => void } = $props();

  const RANGES: { key: Range; label: string }[] = [
    { key: '1W', label: '1 week' },
    { key: '1M', label: '1 month' },
    { key: '1Y', label: '1 year' },
  ];
</script>

<div class="segmented" role="radiogroup" aria-label="Time range">
  {#each RANGES as r (r.key)}
    <button role="radio" aria-checked={value === r.key} class:on={value === r.key} onclick={() => onchange(r.key)}>
      {r.label}
    </button>
  {/each}
</div>
```

- [ ] **Step 3: `SessionCard.svelte`**

```svelte
<script lang="ts">
  import Icon from './Icon.svelte';
  import type { Kind } from '../lib/types';

  interface Props {
    kind: Kind;
    title: string;
    subtitle?: string;
    meta?: string;
    chips?: string[];
    onclick: () => void;
  }

  let { kind, title, subtitle, meta, chips = [], onclick }: Props = $props();
</script>

<button class="session {kind}" {onclick}>
  <span class="bar" aria-hidden="true"></span>
  <span class="body">
    <span class="top">
      <strong>{title}</strong>
      {#if meta}<span class="meta">{meta}</span>{/if}
    </span>
    {#if subtitle}<span class="sub">{subtitle}</span>{/if}
    {#if chips.length}
      <span class="chips">{#each chips as c (c)}<span class="chip">{c}</span>{/each}</span>
    {/if}
  </span>
  <Icon name="chevron-right" />
</button>

<style>
  .session {
    display: grid; grid-template-columns: 4px 1fr auto; align-items: center; gap: var(--space-3);
    width: 100%; min-height: var(--tap-min); padding: var(--space-3) var(--space-3) var(--space-3) 0;
    background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md);
    text-align: left; cursor: pointer; color: var(--color-text-muted); overflow: hidden;
  }
  .bar { align-self: stretch; background: var(--color-text-faint); }
  .workout .bar { background: var(--color-workout); }
  .selfcare .bar { background: var(--color-selfcare); }
  .body { display: grid; gap: var(--space-1); min-width: 0; }
  .top { display: flex; justify-content: space-between; gap: var(--space-2); color: var(--color-text); }
  .meta, .sub { font-size: var(--text-sm); color: var(--color-text-muted); }
</style>
```

- [ ] **Step 4: Verify**

Run: `cd frontend && npm run check && npm run build`
Expected: 0 errors; build succeeds. (These are exercised by the screen tasks.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components
git commit -m "feat(ui): confirm sheet, range filter and session card"
```

---

### Task 6: Calendar component

**Files:**
- Create: `frontend/src/components/Calendar.svelte`

- [ ] **Step 1: Implement**

```svelte
<script lang="ts">
  // One calendar, four renderings (spec §7):
  //   week    — 7 day rows with entry titles (tap an entry → its detail)
  //   month   — grid with a coloured dot per entry (tap a day → day view)
  //   year    — vertical heatmap: 7 weekday columns × 53 week rows, newest on top;
  //             with two kinds each cell is split (left workout, right self-care)
  //   compact — the month grid, small and non-interactive (hub mini calendars)
  import { dayLabel, monthGrid, monthShort, weekDays, weekdayLabels, yearRows, type ISODate } from '../lib/dates';
  import { heatLevel } from '../lib/format';
  import type { CalendarEntry, CalendarView, Kind, WeekStart } from '../lib/types';

  interface Props {
    view: CalendarView;
    anchor: ISODate;
    weekStart: WeekStart;
    today: ISODate;
    days: Record<ISODate, CalendarEntry[]>;
    kinds: Kind[];
    compact?: boolean;
    onday?: (date: ISODate) => void;
    onentry?: (entry: CalendarEntry) => void;
  }

  let { view, anchor, weekStart, today, days, kinds, compact = false, onday, onentry }: Props = $props();

  const SHADE = [0, 40, 70, 100];
  const labels = $derived(weekdayLabels(weekStart));

  function entriesOn(d: ISODate): CalendarEntry[] {
    return (days[d] ?? []).filter((e) => kinds.includes(e.kind));
  }

  function shade(kind: Kind, count: number): string {
    const level = heatLevel(count);
    return level === 0
      ? 'var(--color-surface-2)'
      : `color-mix(in srgb, var(--color-${kind}) ${SHADE[level]}%, var(--color-surface-2))`;
  }

  function heatStyle(d: ISODate): string {
    const entries = entriesOn(d);
    const w = shade('workout', entries.filter((e) => e.kind === 'workout').length);
    const s = shade('selfcare', entries.filter((e) => e.kind === 'selfcare').length);
    if (kinds.length === 1) return `background: ${kinds[0] === 'workout' ? w : s}`;
    return `background: linear-gradient(90deg, ${w} 50%, ${s} 50%)`;
  }

  function monthMarker(row: ISODate[], i: number): string {
    const first = row.find((d) => d.endsWith('-01'));
    if (first) return monthShort(first);
    return i === 0 ? monthShort(row[0]) : '';
  }
</script>

{#if view === 'week'}
  <ol class="week">
    {#each weekDays(anchor, weekStart) as d (d)}
      <li class:today={d === today}>
        <button class="week-date" onclick={() => onday?.(d)}>{dayLabel(d)}</button>
        <div class="week-entries">
          {#each entriesOn(d) as e (`${e.kind}-${e.id}`)}
            <button class="week-entry" onclick={() => onentry?.(e)}>
              <span class="dot {e.kind}"></span>
              <span class="title">{e.title}</span>
              {#if !compact}<small>{e.summary}</small>{/if}
            </button>
          {:else}
            <span class="empty">—</span>
          {/each}
        </div>
      </li>
    {/each}
  </ol>
{:else if view === 'month'}
  <div class="month" class:compact>
    {#each labels as l (l)}<span class="dow">{compact ? l[0] : l}</span>{/each}
    {#each monthGrid(anchor, weekStart).flat() as d (d)}
      {@const entries = entriesOn(d)}
      <svelte:element
        this={compact ? 'div' : 'button'}
        class="cell"
        class:out={d.slice(0, 7) !== anchor.slice(0, 7)}
        class:today={d === today}
        aria-label={compact ? undefined : `${d}: ${entries.length} logged`}
        onclick={compact ? undefined : () => onday?.(d)}>
        <span class="num">{Number(d.slice(8))}</span>
        <span class="dots">
          {#each entries.slice(0, 3) as e (`${e.kind}-${e.id}`)}<span class="dot {e.kind}"></span>{/each}
          {#if entries.length > 3}<span class="more">+{entries.length - 3}</span>{/if}
        </span>
      </svelte:element>
    {/each}
  </div>
{:else}
  <div class="year">
    <span></span>
    {#each labels as l (l)}<span class="dow">{l[0]}</span>{/each}
    {#each yearRows(anchor, weekStart) as row, i (row[0])}
      <span class="mlabel">{monthMarker(row, i)}</span>
      {#each row as d (d)}
        {#if d > today}
          <span class="heat future"></span>
        {:else}
          <button class="heat" class:today={d === today} style={heatStyle(d)} aria-label={d} onclick={() => onday?.(d)}></button>
        {/if}
      {/each}
    {/each}
  </div>
{/if}

<style>
  /* week */
  .week { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-1); }
  .week li { display: grid; grid-template-columns: 64px 1fr; gap: var(--space-2); padding: var(--space-2) 0; border-bottom: 1px solid var(--color-border-soft); }
  .week li.today .week-date { color: var(--color-accent); font-weight: 600; }
  .week-date { background: none; border: 0; text-align: left; color: var(--color-text-muted); cursor: pointer; min-height: var(--tap-min); padding: 0; }
  .week-entries { display: grid; gap: var(--space-1); align-content: center; }
  .week-entry {
    display: grid; grid-template-columns: auto 1fr; column-gap: var(--space-2); align-items: center;
    background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-sm);
    padding: var(--space-2); text-align: left; cursor: pointer; min-height: var(--tap-min);
  }
  .week-entry small { grid-column: 2; color: var(--color-text-muted); font-size: var(--text-xs); }
  .empty { color: var(--color-text-faint); }

  /* month */
  .month { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
  .dow { text-align: center; font-size: var(--text-xs); color: var(--color-text-muted); padding-bottom: var(--space-1); }
  .cell {
    display: grid; grid-template-rows: auto 1fr; justify-items: center; gap: 2px;
    min-height: 52px; padding: var(--space-1) 0; background: var(--color-surface);
    border: 1px solid transparent; border-radius: var(--radius-sm); cursor: pointer; color: var(--color-text);
  }
  .cell.out { opacity: 0.35; }
  .cell.today { border-color: var(--color-accent); }
  .num { font-size: var(--text-sm); }
  .dots { display: flex; gap: 3px; align-items: center; flex-wrap: wrap; justify-content: center; }
  .more { font-size: 10px; color: var(--color-text-muted); }
  .compact { gap: 1px; }
  .compact .cell { min-height: 30px; cursor: inherit; }
  .compact .num { font-size: var(--text-xs); }
  .compact .dot { width: 5px; height: 5px; }

  /* year heatmap */
  .year { display: grid; grid-template-columns: 34px repeat(7, 1fr); gap: 3px; }
  .mlabel { font-size: var(--text-xs); color: var(--color-text-muted); align-self: center; }
  .heat { aspect-ratio: 1; border: 0; border-radius: 3px; padding: 0; cursor: pointer; min-height: 0; }
  .heat.future { background: none; outline: 1px dashed var(--color-border-soft); cursor: default; }
  .heat.today { outline: 2px solid var(--color-text); outline-offset: 1px; }
</style>
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npm run check && npm run build`
Expected: 0 errors. (Rendered and checked in Task 7.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Calendar.svelte
git commit -m "feat(ui): calendar component — week, month, year heatmap, compact"
```

---

### Task 7: Calendar screens

**Files:**
- Replace: `frontend/src/screens/calendar/CalendarScreen.svelte`, `frontend/src/screens/calendar/DayScreen.svelte`

- [ ] **Step 1: `CalendarScreen.svelte`**

```svelte
<script lang="ts">
  import Calendar from '../../components/Calendar.svelte';
  import Icon from '../../components/Icon.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { addDays, addMonths, monthLabel, rangeFor, shortDate } from '../../lib/dates';
  import { openEntry } from '../../lib/entries';
  import { relativeDays } from '../../lib/format';
  import { navigate } from '../../lib/router.svelte';
  import { toastError } from '../../lib/toast.svelte';
  import type { CalendarEntry, CalendarView, Kind, LastDone } from '../../lib/types';

  let { query }: { query: Record<string, string> } = $props();

  const VIEWS: CalendarView[] = ['week', 'month', 'year'];
  const KIND_OPTIONS = [
    { key: 'all', label: 'All' },
    { key: 'workout', label: 'Workouts' },
    { key: 'selfcare', label: 'Self-care' },
  ];

  const view: CalendarView = $derived(
    VIEWS.includes(query.view as CalendarView) ? (query.view as CalendarView) : app.settings!.calendar_view,
  );
  const anchor = $derived(query.date ?? app.today);
  const kind = $derived(query.kind === 'workout' || query.kind === 'selfcare' ? query.kind : 'all');
  const kinds: Kind[] = $derived(kind === 'all' ? ['workout', 'selfcare'] : [kind as Kind]);
  const weekStart = $derived(app.settings!.week_start);
  const range = $derived(rangeFor(view, anchor, weekStart));
  const title = $derived(view === 'month' ? monthLabel(anchor) : `${shortDate(range.from)} – ${shortDate(range.to)}`);

  let days: Record<string, CalendarEntry[]> = $state({});
  let lastDone: LastDone | null = $state(null);

  $effect(() => {
    const { from, to } = range;
    const wanted = kinds;
    let live = true;
    api
      .calendar(from, to, wanted)
      .then((result) => {
        if (live) days = Object.fromEntries(result.map((d) => [d.date, d.entries]));
      })
      .catch(toastError);
    return () => {
      live = false;
    };
  });

  $effect(() => {
    api.lastDone().then((r) => (lastDone = r)).catch(toastError);
  });

  function setQuery(patch: Record<string, string>): void {
    navigate(['calendar'], { view, date: anchor, kind, ...patch }, { replace: true });
  }

  function shift(direction: 1 | -1): void {
    const date =
      view === 'week' ? addDays(anchor, 7 * direction) : addMonths(anchor, (view === 'month' ? 1 : 12) * direction);
    setQuery({ date });
  }

  const since = (d: string | null | undefined) => (d ? relativeDays(d, app.today) : 'never');
</script>

<header class="page-head"><h1>Calendar</h1></header>

<div class="last-done">
  <span><span class="dot workout"></span> Workout · {since(lastDone?.workout)}</span>
  <span><span class="dot selfcare"></span> Skincare · {since(lastDone?.selfcare)}</span>
</div>

<div class="controls">
  <div class="segmented" role="group" aria-label="View">
    {#each VIEWS as v (v)}
      <button class:on={view === v} aria-pressed={view === v} onclick={() => setQuery({ view: v })}>
        {v[0].toUpperCase() + v.slice(1)}
      </button>
    {/each}
  </div>
  <div class="segmented" role="group" aria-label="Show">
    {#each KIND_OPTIONS as k (k.key)}
      <button class:on={kind === k.key} aria-pressed={kind === k.key} onclick={() => setQuery({ kind: k.key })}>
        {k.label}
      </button>
    {/each}
  </div>
</div>

<div class="nav-row">
  <button class="icon-btn" aria-label="Previous" onclick={() => shift(-1)}><Icon name="chevron-left" /></button>
  <strong>{title}</strong>
  <button class="icon-btn" aria-label="Next" onclick={() => shift(1)}><Icon name="chevron-right" /></button>
  {#if anchor !== app.today}
    <button class="btn small" onclick={() => setQuery({ date: app.today })}>Today</button>
  {/if}
</div>

<Calendar
  {view}
  {anchor}
  {weekStart}
  today={app.today}
  {days}
  {kinds}
  onday={(d) => navigate(['calendar', 'day', d], { kind })}
  onentry={openEntry} />

<style>
  .last-done { display: flex; flex-wrap: wrap; gap: var(--space-4); font-size: var(--text-sm); color: var(--color-text-muted); }
  .controls { display: flex; flex-wrap: wrap; gap: var(--space-2); }
  .nav-row { display: flex; align-items: center; gap: var(--space-2); }
  .nav-row strong { flex: 1; text-align: center; }
</style>
```

- [ ] **Step 2: `DayScreen.svelte`**

```svelte
<script lang="ts">
  import BackBar from '../../components/BackBar.svelte';
  import SessionCard from '../../components/SessionCard.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { longDate } from '../../lib/dates';
  import { openEntry } from '../../lib/entries';
  import { navigate } from '../../lib/router.svelte';
  import { toastError } from '../../lib/toast.svelte';
  import type { CalendarEntry, Kind } from '../../lib/types';

  let { date, kind }: { date: string; kind: string } = $props();

  const kinds: Kind[] = $derived(kind === 'workout' || kind === 'selfcare' ? [kind] : ['workout', 'selfcare']);
  let entries: CalendarEntry[] = $state([]);
  let loaded = $state(false);

  $effect(() => {
    api
      .calendar(date, date, kinds)
      .then((r) => {
        entries = r[0]?.entries ?? [];
        loaded = true;
      })
      .catch(toastError);
  });
</script>

<BackBar title={longDate(date)} fallback={['calendar']} />

{#if loaded && entries.length === 0}
  <p class="muted">Nothing logged on this day.</p>
{/if}

<div class="stack">
  {#each entries as e (`${e.kind}-${e.id}`)}
    <SessionCard
      kind={e.kind}
      title={e.title}
      subtitle={e.summary}
      meta={e.in_progress ? 'in progress' : undefined}
      onclick={() => openEntry(e)} />
  {/each}
</div>

{#if date <= app.today}
  <button class="btn block" onclick={() => navigate(['selfcare', 'log'], { date })}>Log skincare for this day</button>
{/if}
```

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run check && npm run build`
Expected: 0 errors.

Manual (`make run-dev`). Seed data first:
```bash
curl -s -X POST localhost:8000/api/selfcare/sessions -H 'Content-Type: application/json' -d '{"category":"skincare","types":["am_routine","retinoid"]}'
```
- Calendar shows the month with a blue dot on today; "Skincare · today" in the strip.
- Week view lists "Skincare (Face)" with "AM routine, Retinoid"; tapping it opens `#/selfcare/1` (stub).
- Year view: vertical grid, today outlined, today's cell half blue; future cells dashed.
- Filter "Workouts" hides the dot; prev/next and Today work; the choice survives a refresh (it is in the hash).
- Tap a day in month view → day screen; Back returns to the calendar with the same view.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/screens/calendar
git commit -m "feat(ui): calendar landing page and day view"
```

---

### Task 8: Workouts — hub, history, detail, and SetRow

**Files:**
- Create: `frontend/src/components/SetRow.svelte`
- Replace: `frontend/src/screens/workouts/WorkoutsHub.svelte`, `WorkoutHistory.svelte`, `WorkoutDetail.svelte`

- [ ] **Step 1: `SetRow.svelte`** — used read-only here and editable in Task 9.

```svelte
<script lang="ts">
  // One set. Inputs depend on the exercise's fields; values are display units
  // (weight lb/kg, distance mi/km) and seconds for duration. Changes are
  // reported through `onpatch` — the parent saves them.
  import Icon from './Icon.svelte';
  import { formatDuration, parseDuration } from '../lib/format';
  import type { FieldName, SetPatch, WorkoutSet } from '../lib/types';

  interface Props {
    set: WorkoutSet;
    index: number;
    fields: FieldName[];
    weightUnit: string;
    distanceUnit: string;
    readonly?: boolean;
    onpatch?: (patch: SetPatch) => void;
    ondelete?: () => void;
  }

  let { set, index, fields, weightUnit, distanceUnit, readonly = false, onpatch, ondelete }: Props = $props();

  const weightStep = $derived(weightUnit === 'kg' ? 2.5 : 5);
  const durationPlain = $derived(fields.includes('distance') ? 'minutes' : 'seconds');
  const canTime = $derived(fields.length === 1 && fields[0] === 'duration' && !readonly);

  let timerStart: number | null = $state(null);
  let now = $state(Date.now());

  $effect(() => {
    if (timerStart === null) return;
    const id = setInterval(() => (now = Date.now()), 250);
    return () => clearInterval(id);
  });

  function emit(patch: SetPatch): void {
    onpatch?.(patch);
  }

  function onNumber(field: 'weight' | 'reps' | 'distance', e: Event): void {
    const raw = (e.currentTarget as HTMLInputElement).value.trim();
    if (raw === '') return emit({ [field]: null } as SetPatch);
    const value = Number(raw);
    if (!Number.isFinite(value) || value < 0) {
      (e.currentTarget as HTMLInputElement).value = String(set[field] ?? '');
      return;
    }
    emit({ [field]: field === 'reps' ? Math.round(value) : value } as SetPatch);
  }

  function bump(field: 'weight' | 'reps', delta: number): void {
    const current = set[field] ?? 0;
    emit({ [field]: Math.max(0, Math.round((current + delta) * 100) / 100) } as SetPatch);
  }

  function onDuration(e: Event): void {
    const input = e.currentTarget as HTMLInputElement;
    const seconds = parseDuration(input.value, durationPlain);
    if (seconds === null && input.value.trim() !== '') {
      input.value = formatDuration(set.duration);
      return;
    }
    emit({ duration: seconds });
  }

  function toggleTimer(): void {
    if (timerStart === null) {
      timerStart = Date.now();
      now = timerStart;
    } else {
      const seconds = Math.round((Date.now() - timerStart) / 1000);
      timerStart = null;
      emit({ duration: seconds });
    }
  }

  const shownDuration = $derived(
    timerStart !== null ? formatDuration(Math.round((now - timerStart) / 1000)) : formatDuration(set.duration),
  );
</script>

<div class="set" class:done={set.done} class:readonly>
  <span class="num">{index + 1}</span>
  <div class="fields">
    {#each fields as f (f)}
      {#if f === 'weight' || f === 'reps'}
        <div class="stepper">
          {#if !readonly}
            <button class="step" aria-label={`Decrease ${f}`} onclick={() => bump(f, f === 'reps' ? -1 : -weightStep)}>
              <Icon name="minus" size={16} />
            </button>
          {/if}
          <label class="value">
            <input
              inputmode={f === 'reps' ? 'numeric' : 'decimal'}
              value={set[f] ?? ''}
              placeholder="0"
              {readonly}
              aria-label={f === 'weight' ? `Weight (${weightUnit})` : 'Reps'}
              onchange={(e) => onNumber(f, e)} />
            <span>{f === 'weight' ? weightUnit : 'reps'}</span>
          </label>
          {#if !readonly}
            <button class="step" aria-label={`Increase ${f}`} onclick={() => bump(f, f === 'reps' ? 1 : weightStep)}>
              <Icon name="plus" size={16} />
            </button>
          {/if}
        </div>
      {:else if f === 'distance'}
        <label class="value wide">
          <input
            inputmode="decimal"
            value={set.distance ?? ''}
            placeholder="0.0"
            {readonly}
            aria-label={`Distance (${distanceUnit})`}
            onchange={(e) => onNumber('distance', e)} />
          <span>{distanceUnit}</span>
        </label>
      {:else}
        <label class="value wide">
          <input
            value={shownDuration}
            placeholder={durationPlain === 'minutes' ? 'min or h:mm:ss' : 'sec or m:ss'}
            readonly={readonly || timerStart !== null}
            aria-label="Duration"
            onchange={onDuration} />
          {#if canTime}
            <button class="step" aria-label={timerStart === null ? 'Start timer' : 'Stop timer'} onclick={toggleTimer}>
              <Icon name={timerStart === null ? 'play' : 'stop'} size={16} />
            </button>
          {/if}
        </label>
      {/if}
    {/each}
  </div>
  {#if readonly}
    <span class="tick-static">{#if set.done}<Icon name="check" />{/if}</span>
  {:else}
    <button class="tick" class:on={set.done} aria-pressed={set.done} aria-label="Set done" onclick={() => emit({ done: !set.done })}>
      <Icon name="check" size={22} />
    </button>
    <button class="icon-btn del" aria-label="Delete set" onclick={() => ondelete?.()}><Icon name="x" size={18} /></button>
  {/if}
</div>

<style>
  .set { display: grid; grid-template-columns: 22px 1fr auto auto; align-items: center; gap: var(--space-2); }
  .set.readonly { grid-template-columns: 22px 1fr auto; }
  .num { color: var(--color-text-faint); font-size: var(--text-sm); text-align: center; }
  .fields { display: flex; flex-wrap: wrap; gap: var(--space-2); }
  .set:not(.done):not(.readonly) .value input { color: var(--color-text-muted); }
  .stepper, .value { display: inline-flex; align-items: center; gap: 2px; }
  .value {
    background: var(--color-surface-2); border-radius: var(--radius-sm); padding: 0 var(--space-2);
    min-height: var(--tap-min); border: 1px solid var(--color-border-soft);
  }
  .value input { width: 3.6em; border: 0; background: none; text-align: right; padding: 0; min-height: var(--tap-min); }
  .value.wide input { width: 6em; }
  .value span { font-size: var(--text-xs); color: var(--color-text-muted); }
  .step {
    display: grid; place-items: center; width: 36px; min-height: var(--tap-min);
    border: 0; background: none; color: var(--color-text-muted); cursor: pointer;
  }
  .tick {
    display: grid; place-items: center; width: var(--tap-min); height: var(--tap-min);
    border-radius: var(--radius-pill); border: 2px solid var(--color-border); background: none;
    color: var(--color-text-faint); cursor: pointer; transition: background var(--transition-fast), border-color var(--transition-fast);
  }
  .tick.on { background: var(--color-workout); border-color: var(--color-workout); color: var(--color-on-accent); animation: pop var(--transition); }
  .tick-static { color: var(--color-workout); }
  .del { min-width: 32px; }
  @keyframes pop { 50% { transform: scale(1.15); } }
</style>
```

- [ ] **Step 2: `WorkoutsHub.svelte`**

```svelte
<script lang="ts">
  import Calendar from '../../components/Calendar.svelte';
  import ConfirmSheet from '../../components/ConfirmSheet.svelte';
  import Icon from '../../components/Icon.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { longDate, monthLabel, rangeFor } from '../../lib/dates';
  import { formatDuration, plural } from '../../lib/format';
  import { navigate } from '../../lib/router.svelte';
  import { toast, toastError } from '../../lib/toast.svelte';
  import type { CalendarEntry, Workout } from '../../lib/types';

  let open: Workout | null = $state(null);
  let days: Record<string, CalendarEntry[]> = $state({});
  let busy = $state(false);
  let confirmDiscard = $state(false);
  let now = $state(Date.now());

  const range = $derived(rangeFor('month', app.today, app.settings!.week_start));

  $effect(() => {
    api.openWorkout().then((w) => (open = w)).catch(toastError);
  });

  $effect(() => {
    const { from, to } = range;
    api
      .calendar(from, to, ['workout'])
      .then((r) => (days = Object.fromEntries(r.map((d) => [d.date, d.entries]))))
      .catch(toastError);
  });

  $effect(() => {
    const id = setInterval(() => (now = Date.now()), 1000);
    return () => clearInterval(id);
  });

  async function start(): Promise<void> {
    busy = true;
    try {
      await api.startWorkout();
      navigate(['workouts', 'active']);
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }

  async function finishStale(): Promise<void> {
    if (!open) return;
    try {
      const result = await api.finishWorkout(open.id, true);
      toast(result.deleted ? 'Nothing was ticked — workout discarded' : 'Workout finished');
      open = null;
    } catch (e) {
      toastError(e);
    }
  }

  async function discard(): Promise<void> {
    if (!open) return;
    try {
      await api.deleteWorkout(open.id);
      toast('Workout discarded');
      open = null;
      confirmDiscard = false;
    } catch (e) {
      toastError(e);
    }
  }
</script>

<header class="page-head"><h1>Workouts</h1></header>

{#if open?.stale}
  <section class="banner warn stack">
    <p>A workout from {longDate(open.local_date)} is still open.</p>
    <div class="row">
      <button class="btn" onclick={finishStale}>Finish</button>
      <button class="btn danger" onclick={() => (confirmDiscard = true)}>Discard</button>
      <button class="btn" onclick={() => navigate(['workouts', 'active'])}>Keep going</button>
    </div>
  </section>
{:else if open}
  <button class="banner resume" onclick={() => navigate(['workouts', 'active'])}>
    <span><strong>In progress</strong> · {plural(open.exercises.length, 'exercise')} · {formatDuration(Math.round((now - Date.parse(open.started_at)) / 1000))}</span>
    <span class="row">Resume <Icon name="chevron-right" /></span>
  </button>
{:else}
  <button class="btn primary big" disabled={busy} onclick={start}><Icon name="plus" /> Start workout</button>
{/if}

<button class="card" onclick={() => navigate(['calendar'], { kind: 'workout', view: 'month' })}>
  <span class="row between"><strong>{monthLabel(app.today)}</strong><Icon name="chevron-right" /></span>
  <Calendar view="month" anchor={app.today} weekStart={app.settings!.week_start} today={app.today} {days} kinds={['workout']} compact />
</button>

<button class="btn block" onclick={() => navigate(['workouts', 'history'])}><Icon name="clock" /> Past workouts</button>

<section class="card stats">
  <span class="row"><Icon name="chart" /><strong>Stats</strong></span>
  <p class="muted">Coming soon — strength progress, distance totals and personal bests.</p>
</section>

{#if confirmDiscard}
  <ConfirmSheet title="Discard this workout?" confirmLabel="Discard" danger onconfirm={discard} oncancel={() => (confirmDiscard = false)}>
    <p class="muted">Everything logged in it will be deleted.</p>
  </ConfirmSheet>
{/if}

<style>
  .resume { display: flex; justify-content: space-between; align-items: center; width: 100%; min-height: 56px; cursor: pointer; color: var(--color-text); text-align: left; }
  .between { justify-content: space-between; }
  .stats { opacity: 0.7; }
</style>
```

- [ ] **Step 3: `WorkoutHistory.svelte`**

```svelte
<script lang="ts">
  import BackBar from '../../components/BackBar.svelte';
  import RangeFilter from '../../components/RangeFilter.svelte';
  import SessionCard from '../../components/SessionCard.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { longDate } from '../../lib/dates';
  import { formatMinutes, plural, titleCase } from '../../lib/format';
  import { navigate } from '../../lib/router.svelte';
  import { toastError } from '../../lib/toast.svelte';
  import type { Range, WorkoutSummary } from '../../lib/types';

  let { range }: { range?: string } = $props();

  const current: Range = $derived(
    range === '1W' || range === '1M' || range === '1Y' ? range : app.settings!.history_range,
  );
  let items: WorkoutSummary[] = $state([]);
  let loaded = $state(false);

  $effect(() => {
    const r = current;
    api
      .workouts(r)
      .then((list) => {
        items = list;
        loaded = true;
      })
      .catch(toastError);
  });
</script>

<BackBar title="Past workouts" fallback={['workouts']} />
<RangeFilter value={current} onchange={(r) => navigate(['workouts', 'history'], { range: r }, { replace: true })} />

{#if loaded && items.length === 0}
  <p class="muted">No workouts in this period.</p>
{/if}

<div class="stack">
  {#each items as w (w.id)}
    <SessionCard
      kind="workout"
      title={longDate(w.local_date)}
      subtitle={`${plural(w.exercise_count, 'exercise')} · ${plural(w.set_count, 'set')} · ${formatMinutes(w.duration_s)}`}
      chips={w.focus.map(titleCase)}
      onclick={() => navigate(['workouts', String(w.id)])} />
  {/each}
</div>
```

- [ ] **Step 4: `WorkoutDetail.svelte`**

```svelte
<script lang="ts">
  import BackBar from '../../components/BackBar.svelte';
  import ConfirmSheet from '../../components/ConfirmSheet.svelte';
  import SetRow from '../../components/SetRow.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { longDate } from '../../lib/dates';
  import { formatMinutes, titleCase } from '../../lib/format';
  import { navigate } from '../../lib/router.svelte';
  import { toast, toastError } from '../../lib/toast.svelte';
  import type { Workout } from '../../lib/types';

  let { id }: { id: number } = $props();

  let workout: Workout | null = $state(null);
  let confirmDelete = $state(false);
  let busy = $state(false);

  $effect(() => {
    api.workout(id).then((w) => (workout = w)).catch(toastError);
  });

  async function edit(): Promise<void> {
    busy = true;
    try {
      await api.reopenWorkout(id);
      navigate(['workouts', 'active'], { edit: '1' });
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }

  async function remove(): Promise<void> {
    busy = true;
    try {
      await api.deleteWorkout(id);
      toast('Workout deleted');
      navigate(['workouts', 'history'], {}, { replace: true });
    } catch (e) {
      toastError(e);
      busy = false;
    }
  }
</script>

<BackBar title={workout ? longDate(workout.local_date) : 'Workout'} fallback={['workouts', 'history']} />

{#if workout}
  <div class="row">
    {#each workout.focus as g (g)}<span class="chip">{titleCase(g)}</span>{/each}
    {#if workout.ended_at}
      <span class="muted">{formatMinutes((Date.parse(workout.ended_at) - Date.parse(workout.started_at)) / 1000)}</span>
    {:else}
      <span class="muted">in progress</span>
    {/if}
  </div>

  {#each workout.exercises as ex (ex.id)}
    <section class="card">
      <strong>{ex.name}</strong>
      {#each ex.sets as s, i (s.id)}
        <SetRow set={s} index={i} fields={ex.fields} weightUnit={app.settings!.weight_unit} distanceUnit={app.settings!.distance_unit} readonly />
      {/each}
    </section>
  {/each}

  {#if workout.notes}<p class="muted">{workout.notes}</p>{/if}

  <div class="actions">
    <button class="btn danger" disabled={busy} onclick={() => (confirmDelete = true)}>Delete</button>
    <button class="btn primary" disabled={busy || !workout.ended_at} onclick={edit}>Edit</button>
  </div>
{/if}

{#if confirmDelete}
  <ConfirmSheet title="Delete this workout?" confirmLabel="Delete" danger {busy} onconfirm={remove} oncancel={() => (confirmDelete = false)}>
    <p class="muted">This cannot be undone.</p>
  </ConfirmSheet>
{/if}

<style>
  .actions { display: grid; grid-template-columns: 1fr 2fr; gap: var(--space-2); margin-top: var(--space-4); }
</style>
```

- [ ] **Step 5: Verify**

Run: `cd frontend && npm run check && npm run build`
Expected: 0 errors.

Manual (`make run-dev`). Seed a finished workout:
```bash
W=$(curl -s -X POST localhost:8000/api/workouts -H 'Content-Type: application/json' -d '{"planned_exercises":["bench_press"]}')
S=$(echo "$W" | python3 -c 'import json,sys; print(json.load(sys.stdin)["exercises"][0]["sets"][0]["id"])')
ID=$(echo "$W" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
curl -s -X PATCH localhost:8000/api/sets/$S -H 'Content-Type: application/json' -d '{"weight":135,"reps":8,"done":true}' >/dev/null
curl -s -X POST localhost:8000/api/workouts/$ID/finish >/dev/null
```
- Workouts hub: Start workout button; mini calendar with a green dot today; tapping the mini calendar opens Calendar filtered to Workouts.
- Past workouts: one card with "Chest" chip; 1W / 1M / 1Y switch; tap → detail showing "135 lb × 8" read-only with a check.
- Detail → Delete asks for confirmation; Cancel keeps it.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/SetRow.svelte frontend/src/screens/workouts
git commit -m "feat(ui): workouts hub, history and detail"
```

---

### Task 9: Active workout and exercise picker

**Files:**
- Create: `frontend/src/components/ExercisePicker.svelte`
- Replace: `frontend/src/screens/workouts/ActiveWorkout.svelte`

- [ ] **Step 1: `ExercisePicker.svelte`**

```svelte
<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  import Icon from './Icon.svelte';
  import { titleCase } from '../lib/format';
  import { dur } from '../lib/motion';
  import { readRecent, rememberRecent } from '../lib/recent';
  import type { Catalog, ExerciseDef } from '../lib/types';

  interface Props { catalog: Catalog; onpick: (key: string) => void; onclose: () => void }

  let { catalog, onpick, onclose }: Props = $props();

  let search = $state('');

  const all: ExerciseDef[] = $derived.by(() => {
    const seen = new Map<string, ExerciseDef>();
    for (const list of Object.values(catalog.exercises_by_group)) for (const e of list) seen.set(e.key, e);
    return [...seen.values()];
  });
  const needle = $derived(search.trim().toLowerCase());
  const recent: ExerciseDef[] = $derived(
    needle ? [] : readRecent().map((k) => all.find((e) => e.key === k)).filter((e): e is ExerciseDef => !!e),
  );
  const groups = $derived(
    Object.entries(catalog.exercises_by_group)
      .map(([group, list]) => [group, list.filter((e) => !needle || e.name.toLowerCase().includes(needle))] as const)
      .filter(([, list]) => list.length > 0),
  );

  function pick(key: string): void {
    rememberRecent(key);
    onpick(key);
  }
</script>

<button class="backdrop" aria-label="Close" onclick={onclose} transition:fade={{ duration: dur(150) }}></button>
<div class="sheet picker" role="dialog" aria-modal="true" aria-label="Add exercise" transition:fly={{ y: 400, duration: dur(220) }}>
  <div class="head">
    <h2>Add exercise</h2>
    <button class="icon-btn" aria-label="Close" onclick={onclose}><Icon name="x" /></button>
  </div>
  <label class="search">
    <Icon name="search" size={18} />
    <input class="input" placeholder="Search exercises" bind:value={search} />
  </label>

  {#if recent.length}
    <p class="section-title">Recent</p>
    <div class="list">
      {#each recent as e (e.key)}<button class="item" onclick={() => pick(e.key)}>{e.name}</button>{/each}
    </div>
  {/if}

  {#each groups as [group, list] (group)}
    <p class="section-title">{titleCase(group)}</p>
    <div class="list">
      {#each list as e (e.key)}<button class="item" onclick={() => pick(e.key)}>{e.name}</button>{/each}
    </div>
  {:else}
    <p class="muted">No exercise matches “{search}”. Add it to config/exercises.yaml.</p>
  {/each}
</div>

<style>
  .picker { max-height: 88vh; }
  .head { display: flex; justify-content: space-between; align-items: center; }
  .search { display: flex; align-items: center; gap: var(--space-2); color: var(--color-text-muted); }
  .search .input { flex: 1; }
  .list { display: grid; gap: 1px; background: var(--color-border-soft); border-radius: var(--radius-md); overflow: hidden; }
  .item { min-height: var(--tap-min); padding: 0 var(--space-4); text-align: left; background: var(--color-surface-2); border: 0; cursor: pointer; }
  .item:active { background: var(--color-surface-3); }
</style>
```

- [ ] **Step 2: `ActiveWorkout.svelte`**

```svelte
<script lang="ts">
  import { fly } from 'svelte/transition';
  import BackBar from '../../components/BackBar.svelte';
  import ConfirmSheet from '../../components/ConfirmSheet.svelte';
  import ExercisePicker from '../../components/ExercisePicker.svelte';
  import Icon from '../../components/Icon.svelte';
  import SetRow from '../../components/SetRow.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { formatDuration, plural } from '../../lib/format';
  import { dur } from '../../lib/motion';
  import { navigate } from '../../lib/router.svelte';
  import { toast, toastError } from '../../lib/toast.svelte';
  import type { SetPatch, Workout, WorkoutExercise, WorkoutSet } from '../../lib/types';

  let { editing = false }: { editing?: boolean } = $props();

  let workout: Workout | null = $state(null);
  let loaded = $state(false);
  let picking = $state(false);
  let confirmFinish = $state(false);
  let confirmDiscard = $state(false);
  let busy = $state(false);
  let now = $state(Date.now());

  $effect(() => {
    api
      .openWorkout()
      .then((w) => {
        workout = w;
        loaded = true;
      })
      .catch((e) => {
        toastError(e);
        loaded = true;
      });
  });

  $effect(() => {
    const id = setInterval(() => (now = Date.now()), 1000);
    return () => clearInterval(id);
  });

  const elapsed = $derived(workout ? Math.max(0, Math.round((now - Date.parse(workout.started_at)) / 1000)) : 0);
  const allSets = $derived(workout ? workout.exercises.flatMap((e) => e.sets) : []);
  const doneCount = $derived(allSets.filter((s) => s.done).length);
  const undoneCount = $derived(allSets.length - doneCount);

  async function start(): Promise<void> {
    try {
      workout = await api.startWorkout();
    } catch (e) {
      toastError(e);
    }
  }

  async function addExercise(key: string): Promise<void> {
    picking = false;
    if (!workout) return;
    try {
      workout.exercises.push(await api.addExercise(workout.id, key));
    } catch (e) {
      toastError(e);
    }
  }

  async function removeExercise(ex: WorkoutExercise): Promise<void> {
    if (!workout) return;
    const i = workout.exercises.indexOf(ex);
    workout.exercises.splice(i, 1);
    try {
      await api.removeExercise(workout.id, ex.id);
    } catch (e) {
      workout.exercises.splice(i, 0, ex);
      toastError(e);
    }
  }

  async function addSet(ex: WorkoutExercise): Promise<void> {
    if (!workout) return;
    try {
      ex.sets.push(await api.addSet(workout.id, ex.id));
    } catch (e) {
      toastError(e);
    }
  }

  // Optimistic: show the change now, reconcile with the server's copy, roll back on error.
  async function patchSet(set: WorkoutSet, patch: SetPatch): Promise<void> {
    const before = $state.snapshot(set);
    Object.assign(set, patch);
    try {
      Object.assign(set, await api.updateSet(set.id, patch));
    } catch (e) {
      Object.assign(set, before);
      toastError(e);
    }
  }

  async function deleteSet(ex: WorkoutExercise, set: WorkoutSet): Promise<void> {
    const i = ex.sets.indexOf(set);
    ex.sets.splice(i, 1);
    try {
      await api.deleteSet(set.id);
    } catch (e) {
      ex.sets.splice(i, 0, set);
      toastError(e);
    }
  }

  async function finish(): Promise<void> {
    if (!workout) return;
    busy = true;
    try {
      const result = await api.finishWorkout(workout.id);
      confirmFinish = false;
      if (result.deleted || !result.workout) {
        toast('Nothing was ticked — workout discarded');
        navigate(['workouts'], {}, { replace: true });
      } else {
        toast(editing ? 'Workout saved' : 'Workout finished');
        navigate(['workouts', String(result.workout.id)], {}, { replace: true });
      }
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }

  async function discard(): Promise<void> {
    if (!workout) return;
    try {
      await api.deleteWorkout(workout.id);
      toast('Workout discarded');
      navigate(['workouts'], {}, { replace: true });
    } catch (e) {
      toastError(e);
    }
  }
</script>

<BackBar title={editing ? 'Edit workout' : 'Workout'} fallback={['workouts']}>
  {#snippet actions()}
    {#if workout && !editing}
      <button class="icon-btn" aria-label="Discard workout" onclick={() => (confirmDiscard = true)}><Icon name="trash" /></button>
    {/if}
  {/snippet}
</BackBar>

{#if loaded && !workout}
  <div class="center-state">
    <p class="muted">No workout in progress.</p>
    <button class="btn primary big" onclick={start}><Icon name="plus" /> Start workout</button>
  </div>
{:else if workout}
  <p class="elapsed" aria-live="off"><Icon name="clock" size={16} /> {formatDuration(elapsed)}</p>

  {#each workout.exercises as ex (ex.id)}
    <section class="card" in:fly={{ y: 12, duration: dur(180) }}>
      <div class="ex-head">
        <strong>{ex.name}</strong>
        <button class="icon-btn" aria-label={`Remove ${ex.name}`} onclick={() => removeExercise(ex)}><Icon name="x" size={18} /></button>
      </div>
      {#each ex.sets as s, i (s.id)}
        <SetRow
          set={s}
          index={i}
          fields={ex.fields}
          weightUnit={app.settings!.weight_unit}
          distanceUnit={app.settings!.distance_unit}
          onpatch={(p) => patchSet(s, p)}
          ondelete={() => deleteSet(ex, s)} />
      {/each}
      <button class="btn small" onclick={() => addSet(ex)}><Icon name="plus" size={16} /> Add set</button>
    </section>
  {:else}
    <p class="muted">Add your first exercise to begin.</p>
  {/each}

  <div class="bottom">
    <button class="btn" onclick={() => (picking = true)}><Icon name="plus" /> Add exercise</button>
    <button class="btn primary" disabled={busy} onclick={() => (confirmFinish = true)}>{editing ? 'Save' : 'Finish'}</button>
  </div>
{/if}

{#if picking && app.catalog}
  <ExercisePicker catalog={app.catalog} onpick={addExercise} onclose={() => (picking = false)} />
{/if}

{#if confirmFinish && workout}
  <ConfirmSheet
    title={editing ? 'Save changes?' : 'Finish workout?'}
    confirmLabel={editing ? 'Save' : 'Finish'}
    {busy}
    onconfirm={finish}
    oncancel={() => (confirmFinish = false)}>
    <p>{plural(workout.exercises.length, 'exercise')} · {plural(doneCount, 'set')} done · {formatDuration(elapsed)}</p>
    {#if undoneCount > 0}
      <p class="muted">{plural(undoneCount, 'unticked set')} will be dropped.</p>
    {/if}
  </ConfirmSheet>
{/if}

{#if confirmDiscard}
  <ConfirmSheet title="Discard this workout?" confirmLabel="Discard" danger onconfirm={discard} oncancel={() => (confirmDiscard = false)}>
    <p class="muted">Everything logged in it will be deleted.</p>
  </ConfirmSheet>
{/if}

<style>
  .elapsed { display: flex; align-items: center; gap: var(--space-1); color: var(--color-text-muted); font-variant-numeric: tabular-nums; }
  .ex-head { display: flex; justify-content: space-between; align-items: center; margin-right: calc(-1 * var(--space-2)); }
  .bottom {
    position: sticky; bottom: calc(var(--tabbar-h) + var(--safe-bottom) + var(--space-2));
    display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-2);
    padding: var(--space-2); background: var(--color-bg); border-radius: var(--radius-lg);
  }
  @media (min-width: 900px) { .bottom { bottom: var(--space-4); } }
</style>
```

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run check && npm run build`
Expected: 0 errors.

Manual (`make run-dev`, phone-sized viewport):
- Workouts → Start workout → active screen with a running clock.
- Add exercise → picker grouped by muscle group; search "curl" filters; pick Bench Press → sets prefilled from the seeded 135 × 8 in muted text.
- Tap ✓ → the check fills green with a pop; the value turns full-strength. Tap again → undone.
- Change weight with + / − and by typing; refresh the page → values persist (server-side).
- Add Run → distance + duration fields; type `30` in duration → shows `30:00`. Add Plank → play/stop timer fills the duration.
- Finish → summary says how many unticked sets will be dropped → detail screen of the new workout. Edit → back on this screen titled "Edit workout" with **Save**.
- With a workout open, the Workouts hub shows the Resume banner.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ExercisePicker.svelte frontend/src/screens/workouts/ActiveWorkout.svelte
git commit -m "feat(ui): active workout logging with exercise picker"
```

---

### Task 10: Self-care screens

**Files:**
- Replace: `frontend/src/screens/selfcare/SelfcareHub.svelte`, `SelfcareLog.svelte`, `SelfcareHistory.svelte`, `SelfcareDetail.svelte`

- [ ] **Step 1: `SelfcareHub.svelte`**

```svelte
<script lang="ts">
  import Calendar from '../../components/Calendar.svelte';
  import Icon from '../../components/Icon.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { monthLabel, rangeFor } from '../../lib/dates';
  import { dueText } from '../../lib/format';
  import { navigate } from '../../lib/router.svelte';
  import { toastError } from '../../lib/toast.svelte';
  import type { CalendarEntry, DueItem } from '../../lib/types';

  let due: DueItem[] = $state([]);
  let days: Record<string, CalendarEntry[]> = $state({});

  const range = $derived(rangeFor('month', app.today, app.settings!.week_start));

  $effect(() => {
    api.due().then((d) => (due = d)).catch(toastError);
  });

  $effect(() => {
    const { from, to } = range;
    api
      .calendar(from, to, ['selfcare'])
      .then((r) => (days = Object.fromEntries(r.map((d) => [d.date, d.entries]))))
      .catch(toastError);
  });
</script>

<header class="page-head"><h1>Self-care</h1></header>

<button class="btn primary big" onclick={() => navigate(['selfcare', 'log'])}><Icon name="plus" /> Log skincare</button>

{#if due.length}
  <section class="card">
    <strong>Due</strong>
    <ul class="due">
      {#each due as item (`${item.category_key}.${item.type_key}`)}
        <li class={item.status}>
          <span class="status" aria-hidden="true"></span>
          <span class="name">{item.type_name}</span>
          <span class="when">{dueText(item)}</span>
        </li>
      {/each}
    </ul>
  </section>
{/if}

<button class="card" onclick={() => navigate(['calendar'], { kind: 'selfcare', view: 'month' })}>
  <span class="row between"><strong>{monthLabel(app.today)}</strong><Icon name="chevron-right" /></span>
  <Calendar view="month" anchor={app.today} weekStart={app.settings!.week_start} today={app.today} {days} kinds={['selfcare']} compact />
</button>

<button class="btn block" onclick={() => navigate(['selfcare', 'history'])}><Icon name="clock" /> Past sessions</button>

<style>
  .between { justify-content: space-between; }
  .due { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
  .due li { display: grid; grid-template-columns: 12px 1fr auto; align-items: center; gap: var(--space-2); min-height: 32px; }
  .status { width: 10px; height: 10px; border-radius: var(--radius-pill); background: var(--color-text-faint); }
  .ok .status { background: var(--color-accent); }
  .soon .status { background: var(--color-warn); }
  .due li.due .status, .overdue .status { background: var(--color-danger); }
  .when { font-size: var(--text-sm); color: var(--color-text-muted); }
  .overdue .when { color: var(--color-danger); }
</style>
```

- [ ] **Step 2: `SelfcareLog.svelte`**

```svelte
<script lang="ts">
  import BackBar from '../../components/BackBar.svelte';
  import ConfirmSheet from '../../components/ConfirmSheet.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { navigate } from '../../lib/router.svelte';
  import { toast, toastError } from '../../lib/toast.svelte';
  import type { DueStatus } from '../../lib/types';

  let { id, initialDate }: { id?: number; initialDate?: string } = $props();

  const categories = $derived(app.catalog!.selfcare);
  let categoryKey = $state(app.catalog!.selfcare[0]?.key ?? '');
  let selected: string[] = $state([]);
  let date = $state(initialDate && initialDate <= app.today ? initialDate : app.today);
  let notes = $state('');
  let status: Record<string, DueStatus> = $state({});
  let busy = $state(false);
  let confirmDelete = $state(false);

  const category = $derived(categories.find((c) => c.key === categoryKey));

  $effect(() => {
    api
      .due()
      .then((items) => (status = Object.fromEntries(items.map((i) => [`${i.category_key}.${i.type_key}`, i.status]))))
      .catch(toastError);
  });

  $effect(() => {
    if (id === undefined) return;
    api
      .selfcareSession(id)
      .then((s) => {
        categoryKey = s.category_key;
        selected = s.types.map((t) => t.key);
        date = s.local_date;
        notes = s.notes ?? '';
      })
      .catch(toastError);
  });

  function toggle(key: string): void {
    selected = selected.includes(key) ? selected.filter((k) => k !== key) : [...selected, key];
  }

  const flagged = (key: string) => ['due', 'overdue'].includes(status[`${categoryKey}.${key}`] ?? '');

  async function save(): Promise<void> {
    busy = true;
    try {
      if (id === undefined) {
        await api.logSelfcare({ category: categoryKey, types: selected, date, notes: notes || null });
        toast('Logged');
        navigate(['selfcare'], {}, { replace: true });
      } else {
        await api.updateSelfcare(id, { types: selected, date, notes: notes || null });
        toast('Saved');
        navigate(['selfcare', String(id)], {}, { replace: true });
      }
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }

  async function remove(): Promise<void> {
    if (id === undefined) return;
    try {
      await api.deleteSelfcare(id);
      toast('Session deleted');
      navigate(['selfcare', 'history'], {}, { replace: true });
    } catch (e) {
      toastError(e);
    }
  }
</script>

<BackBar title={id === undefined ? 'Log skincare' : 'Edit session'} fallback={['selfcare']} />

{#if categories.length > 1 && id === undefined}
  <div class="segmented" role="group" aria-label="Category">
    {#each categories as c (c.key)}
      <button class:on={categoryKey === c.key} onclick={() => { categoryKey = c.key; selected = []; }}>{c.name}</button>
    {/each}
  </div>
{/if}

<label class="field">
  <span>Date</span>
  <input class="input" type="date" bind:value={date} max={app.today} />
</label>

{#if category}
  <div class="field">
    <span>What did you do?</span>
    <div class="types">
      {#each category.types as t (t.key)}
        <button
          class="type"
          class:on={selected.includes(t.key)}
          class:flagged={flagged(t.key)}
          aria-pressed={selected.includes(t.key)}
          onclick={() => toggle(t.key)}>
          {t.name}
        </button>
      {/each}
    </div>
  </div>
{:else}
  <p class="muted">No self-care categories configured — see config/selfcare.yaml.</p>
{/if}

<label class="field">
  <span>Note (optional)</span>
  <textarea class="input" bind:value={notes} maxlength="2000"></textarea>
</label>

<button class="btn primary big" disabled={busy || selected.length === 0} onclick={save}>
  {id === undefined ? 'Save' : 'Save changes'}
</button>

{#if id !== undefined}
  <button class="btn danger block" onclick={() => (confirmDelete = true)}>Delete session</button>
{/if}

{#if confirmDelete}
  <ConfirmSheet title="Delete this session?" confirmLabel="Delete" danger onconfirm={remove} oncancel={() => (confirmDelete = false)}>
    <p class="muted">This cannot be undone.</p>
  </ConfirmSheet>
{/if}

<style>
  .types { display: flex; flex-wrap: wrap; gap: var(--space-2); }
  .type {
    min-height: var(--tap-min); padding: 0 var(--space-4); border-radius: var(--radius-pill);
    background: var(--color-surface-2); border: 2px solid var(--color-border); cursor: pointer;
    transition: background var(--transition-fast), border-color var(--transition-fast);
  }
  .type.flagged { border-color: var(--color-warn); }
  .type.on { background: var(--color-selfcare); border-color: var(--color-selfcare); color: var(--color-on-accent); font-weight: 600; }
</style>
```

- [ ] **Step 3: `SelfcareHistory.svelte`**

```svelte
<script lang="ts">
  import BackBar from '../../components/BackBar.svelte';
  import RangeFilter from '../../components/RangeFilter.svelte';
  import SessionCard from '../../components/SessionCard.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { longDate } from '../../lib/dates';
  import { navigate } from '../../lib/router.svelte';
  import { toastError } from '../../lib/toast.svelte';
  import type { Range, SelfcareSession } from '../../lib/types';

  let { range }: { range?: string } = $props();

  const current: Range = $derived(
    range === '1W' || range === '1M' || range === '1Y' ? range : app.settings!.history_range,
  );
  let items: SelfcareSession[] = $state([]);
  let loaded = $state(false);

  $effect(() => {
    const r = current;
    api
      .selfcareSessions(r)
      .then((list) => {
        items = list;
        loaded = true;
      })
      .catch(toastError);
  });
</script>

<BackBar title="Past sessions" fallback={['selfcare']} />
<RangeFilter value={current} onchange={(r) => navigate(['selfcare', 'history'], { range: r }, { replace: true })} />

{#if loaded && items.length === 0}
  <p class="muted">No sessions in this period.</p>
{/if}

<div class="stack">
  {#each items as s (s.id)}
    <SessionCard
      kind="selfcare"
      title={longDate(s.local_date)}
      subtitle={s.category_name}
      chips={s.types.map((t) => t.name)}
      onclick={() => navigate(['selfcare', String(s.id)])} />
  {/each}
</div>
```

- [ ] **Step 4: `SelfcareDetail.svelte`**

```svelte
<script lang="ts">
  import BackBar from '../../components/BackBar.svelte';
  import { api } from '../../lib/api';
  import { longDate } from '../../lib/dates';
  import { navigate } from '../../lib/router.svelte';
  import { toastError } from '../../lib/toast.svelte';
  import type { SelfcareSession } from '../../lib/types';

  let { id }: { id: number } = $props();

  let session: SelfcareSession | null = $state(null);

  $effect(() => {
    api.selfcareSession(id).then((s) => (session = s)).catch(toastError);
  });
</script>

<BackBar title={session ? longDate(session.local_date) : 'Session'} fallback={['selfcare', 'history']} />

{#if session}
  <section class="card">
    <strong>{session.category_name}</strong>
    <div class="chips">{#each session.types as t (t.key)}<span class="chip">{t.name}</span>{/each}</div>
    {#if session.notes}<p class="muted">{session.notes}</p>{/if}
  </section>
  <button class="btn primary block" onclick={() => navigate(['selfcare', 'log', String(id)])}>Edit</button>
{/if}
```

- [ ] **Step 5: Verify**

Run: `cd frontend && npm run check && npm run build`
Expected: 0 errors.

Manual (`make run-dev`):
- Self-care hub: Log skincare button, Due list (e.g. Exfoliation "never done", AM routine "due today" in red), mini calendar, Past sessions.
- Log: due/overdue chips have an amber outline; select two, change the date to yesterday, Save → toast "Logged" → hub; Due list updates.
- Past sessions → card with type chips → detail → Edit → change types → Save changes → detail reflects it; Edit → Delete session → confirmation → history.
- From a Calendar day in the past, "Log skincare for this day" pre-fills that date.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/screens/selfcare
git commit -m "feat(ui): self-care hub, logging, history and detail"
```

---

### Task 11: Settings

**Files:**
- Replace: `frontend/src/screens/settings/SettingsScreen.svelte`

- [ ] **Step 1: Implement**

```svelte
<script lang="ts">
  import { app, updateSetting } from '../../lib/app.svelte';
  import { toast, toastError } from '../../lib/toast.svelte';
  import type { Settings } from '../../lib/types';

  type Option = { value: string; label: string };
  const SETTINGS: { key: keyof Settings; label: string; options: Option[] }[] = [
    { key: 'calendar_view', label: 'Default calendar view', options: [
      { value: 'week', label: 'Week' }, { value: 'month', label: 'Month' }, { value: 'year', label: 'Year' } ] },
    { key: 'week_start', label: 'Week starts on', options: [
      { value: 'monday', label: 'Monday' }, { value: 'sunday', label: 'Sunday' } ] },
    { key: 'weight_unit', label: 'Weight', options: [
      { value: 'lb', label: 'lb' }, { value: 'kg', label: 'kg' } ] },
    { key: 'distance_unit', label: 'Distance', options: [
      { value: 'mi', label: 'Miles' }, { value: 'km', label: 'Kilometres' } ] },
    { key: 'history_range', label: 'Default history range', options: [
      { value: '1W', label: '1 week' }, { value: '1M', label: '1 month' }, { value: '1Y', label: '1 year' } ] },
  ];

  async function change(key: keyof Settings, value: string): Promise<void> {
    if (app.settings?.[key] === value) return;
    try {
      await updateSetting(key, value as Settings[typeof key]);
      toast('Saved');
    } catch (e) {
      toastError(e);
    }
  }
</script>

<header class="page-head"><h1>Settings</h1></header>

{#each SETTINGS as s (s.key)}
  <section class="setting">
    <span class="label">{s.label}</span>
    <div class="segmented" role="radiogroup" aria-label={s.label}>
      {#each s.options as o (o.value)}
        <button
          role="radio"
          aria-checked={app.settings?.[s.key] === o.value}
          class:on={app.settings?.[s.key] === o.value}
          onclick={() => change(s.key, o.value)}>
          {o.label}
        </button>
      {/each}
    </div>
  </section>
{/each}

<p class="muted small">
  Exercises, skincare types, colors and the timezone live in <code>config/*.yaml</code> on the server; edit them and restart.
</p>

{#if app.configErrors.length}
  <section class="banner warn stack">
    <strong>Config errors</strong>
    <ul>{#each app.configErrors as e (e)}<li>{e}</li>{/each}</ul>
  </section>
{/if}

<style>
  .setting { display: grid; gap: var(--space-2); }
  .label { font-size: var(--text-sm); color: var(--color-text-muted); }
  .small { font-size: var(--text-sm); }
  ul { margin: 0; padding-left: var(--space-4); }
</style>
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npm run check && npm run build`
Expected: 0 errors.

Manual: change Default calendar view to Year → Calendar tab opens in Year. Switch weight to kg → an existing 135 lb set shows 61.23 kg. Break `config/exercises.yaml` (e.g. `type: nope`), restart the API → Settings shows the error; restore the file.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/screens/settings
git commit -m "feat(ui): settings screen"
```

---

### Task 12: Acceptance on the phone

- [ ] **Step 1: Full build and tests**

```bash
cd ~/Development/apollo
make clean && make build && make test
```
Expected: build completes; pytest and vitest pass.

- [ ] **Step 2: Run on the network and open on the iPhone**

```bash
make run
```
On the iPhone (same Wi-Fi), open `http://<mac-ip>:8000/ui/` in Safari. Find the Mac's IP with `ipconfig getifaddr en0`.

Walk the spec §9 acceptance list and tick each:
- [ ] Log a workout with a weight exercise, a run and a plank; tick sets; Finish.
- [ ] Find it in Past workouts (1W) and on the Calendar in week, month and year views.
- [ ] Open it, Edit, change a value, Save.
- [ ] Log two skincare sessions (one backdated); check the Due list.
- [ ] Change the default calendar view in Settings; the Calendar tab follows.
- [ ] Safari back and swipe-back move between screens; bookmarking `#/workouts/active` reopens it.
- [ ] Add to Home Screen; in standalone mode every sub-screen has a working in-app back button; nothing sits under the notch or home indicator.
- [ ] Number fields open the numeric keypad and do not zoom the page.
- [ ] Lock the phone for a minute mid-workout; the clock is correct on return.
- [ ] With Reduce Motion on (iOS Settings → Accessibility → Motion), screens switch without sliding.

- [ ] **Step 3: Record results** — note anything that failed or felt wrong in `docs/2026-09-22-mvp-acceptance-notes.md` and commit it:

```bash
git add docs/2026-09-22-mvp-acceptance-notes.md
git commit -m "docs: MVP acceptance notes"
```

The MVP is complete when every box above is ticked or has a written follow-up.
