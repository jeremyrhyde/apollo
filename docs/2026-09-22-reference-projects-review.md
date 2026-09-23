# Reference projects review — learnings for Apollo's MVP

_2026-09-22. Source-code review of open-source workout and habit trackers, plus
the export formats of commercial apps. Companion to
`2026-09-22-health-tracking-research.md` (the web survey). Everything here is
**reference material and proposals** — no design decision has been made yet._

Reviewed by reading code, not READMEs. Where a finding is a proposal for
Apollo rather than an observation, it says so.

---

## 1. What was reviewed

| Project | Stack | License | Area | Reuse verdict |
|---|---|---|---|---|
| [wger](https://github.com/wger-project/wger) (+ wger-react) | Django + React | AGPL-3.0 code; exercise data CC-BY-SA/CC0 per entry | Workouts | Ideas only. Exercise dataset importable with attribution |
| [OpenGym](https://github.com/alexpcosta/opengym) | React + JSON-blob Node server | AGPL-3.0 | Workouts, heatmap | Ideas only |
| [JournalGym](https://github.com/swagsystems/journalgym-app) | **FastAPI + raw sqlite3** + React | MIT | Workouts | **Code liftable** (same stack) |
| [Lyftr](https://github.com/Cawlumm/lyftr) | Go/Gin + SQLite + React | MIT | Workouts | Ideas (different language) |
| [RepoBean/workout-tracker](https://github.com/RepoBean/workout-tracker) | Express + SQLite + React (AI-built) | MIT (README only) | Workouts, calendar | Ideas; read its `docs/v3-plan.md` self-critique |
| [jovandeginste/workout-tracker](https://github.com/jovandeginste/workout-tracker) | Go + GORM | MIT | Cardio/GPS | Type→metric table, cardio records |
| [OpenHabitTracker](https://github.com/Jinjinov/OpenHabitTracker) | C# Blazor | GPL-3.0 | Recurrence, overdue % | Ideas only |
| [Loop / uhabits](https://github.com/iSoron/uhabits) | Kotlin | GPL-3.0 | Frequency, score, skip | Ideas only |
| [Beaver Habit Tracker](https://github.com/daya0576/beaverhabits) | Python (NiceGUI/FastAPI) | BSD-3 | Heatmap, periods | Code reusable with notice |
| [SkinRitual](https://github.com/EmmaVellard/SkinRitual) | Next.js + IndexedDB | **None (all rights reserved)** | Skincare steps | Ideas only |
| Strong / Hevy / FitNotes / JEFIT exports, Hevy API | — | — | Import/export | Formats documented below |

**What none of them do:** combine workouts and self-care in one app or one
calendar. Apollo's combined view has no precedent to copy.

---

## 2. Feature map — what they have vs. Apollo's MVP

Legend: **MVP** = build in the first version · **Later** = worth doing after ·
**Skip** = not relevant to a single-user self-hosted app.

### Workouts

| Feature | Seen in | Apollo |
|---|---|---|
| Exercise catalog with per-type metric schema | Hevy (8 types), jovandeginste (hardcoded) | **MVP** — YAML |
| Start a workout (blank or from a template), log sets, finish | all | **MVP** |
| In-progress session **persisted server-side**, resumable | wger (`datetime_end` null), RepoBean (`completedAt` null) | **MVP** — the others lose it in localStorage |
| Per-set `done` flag; only done sets count | OpenGym | **MVP** |
| Prefill from last session's same set ("previous: 135×8") | OpenGym, RepoBean | **MVP** |
| History list + session detail | all | **MVP** |
| PRs + estimated 1RM, computed on read | all (differently) | **MVP** |
| Mid-session "new PR" toast | RepoBean | **MVP** (cheap once PRs exist) |
| Session notes + 1–3 rating | wger, OpenGym | **MVP** (cheap) |
| Quick entry `3x8 @135` | JournalGym | MVP-nice |
| Weight modes: external / bodyweight / added / assisted | JournalGym | MVP-nice |
| Rest timer (absolute end time) | RepoBean, Lyftr, JournalGym | Later (small) |
| CSV export (one row per set) | RepoBean, JournalGym | Later — early win |
| Import from Strong/Hevy/FitNotes | OpenGym | Later |
| Workout templates / weekly plan | OpenGym, Lyftr, wger | Later |
| Progress charts (e1RM, volume per exercise) | OpenGym, Lyftr | Later |
| Progression suggestions (linear, double) | OpenGym, Lyftr | Later |
| RPE/RIR per set, warmup/drop set types | several | Later |
| Supersets, drop-set chains | wger, Hevy, RepoBean | Skip for now |
| Muscle maps, GIF exercise library, nutrition, AI coach, GPS/maps, multi-user auth, i18n, mobile apps | various | Skip |

### Self-care routines

| Feature | Seen in | Apollo |
|---|---|---|
| "Every N days since last done" (floating) | OpenHabitTracker | **MVP** |
| Specific weekdays / daily | all | **MVP** |
| X per week / month | Loop, Beaver, OHT | **MVP** |
| Today list sorted by overdue ratio, green/amber/red | OpenHabitTracker | **MVP** |
| Multi-step routine with per-session step snapshot (done/skipped) | SkinRitual only | **MVP** |
| Backdated logging | all | **MVP** |
| Explicit "skipped" | Loop, SkinRitual | **MVP** |
| Per-step schedules (retinoid every 3rd night, exfoliate weekly) | SkinRitual (suggestion engine) | MVP+ |
| Alternating steps (pick least-recently-used from a group) | SkinRitual | MVP+ |
| Fixed interval from an anchor date | — | Later |
| Streaks | OHT, Loop, Beaver | Later |
| Habit "strength" score | Loop | Later |
| Spacing / max-per-week constraints, product expiry | SkinRitual | Later |
| Reminders / notifications | Loop | Later |

### Calendar & history

| Feature | Seen in | Apollo |
|---|---|---|
| Month grid, click a day → that day's sessions | wger, OpenGym, RepoBean, OHT | **MVP** |
| Multiple sessions per day, each clickable | jovandeginste, OpenGym | **MVP** (RepoBean only reaches the first) |
| Direct session detail route (`/sessions/{id}`) | wger, jovandeginste | **MVP** |
| GitHub-style year heatmap | OpenGym, Beaver | MVP-nice (~40 lines) |
| Future "due" markers as projections | SkinRitual, OpenGym (planned days) | Later |

---

## 3. Workout data model — learnings

### What went wrong elsewhere

- **wger: two generic slots, "repetitions" and "weight", each with a unit.**
  A run is either 5 km *or* 30 min, never both; speed is stuffed into
  "weight". Strongest evidence for per-type schemas.
- **Lyftr, RepoBean: one wide set row, `0` meaning "not applicable".** A real
  zero can't be told from a missing value, and cardio is *inferred*
  (`durationSec > 0`). Neither app's UI actually collects duration/distance.
- **RepoBean: exercises identified by lowercased name.** Renaming an exercise
  splits its history. The author's v3 plan adds a catalog table.

### Patterns worth copying

- **Session → session_exercise (ordered) → set** hierarchy (Lyftr). Keep
  sessions exercises **on the server** from day one (RepoBean's v3 plan).
- **In progress = `ended_at IS NULL`.** Resume is trivial; the server rejects
  set edits on finished sessions (RepoBean). Decide what happens to stale open
  sessions (RepoBean's 24h window silently orphans them — prompt instead).
- **Stable key + name snapshot.** Store `exercise_key` (from YAML) *and* the
  name at log time, so history survives renames and YAML edits (RepoBean).
- **Snapshot the plan** on each session exercise (`target`), so past sessions
  are judged against what was planned then (OpenGym).
- **Canonical SI storage** (kg, m, s); convert for display; pace is derived,
  never stored (jovandeginste, Hevy API).
- **Local-day bucketing:** store `started_at` (UTC) plus the local date / tz
  offset; a session past midnight belongs to the day it began (wger, Lyftr).
- **Compute PRs on read.** OpenGym persists `prs` on the workout and wger
  stores them as trophies — both go stale when history is edited.
- **Nullable plan links** so ad-hoc sessions work (wger).

### Proposed shape (sketch, not a decision)

```sql
session(id, kind /*'workout'|'selfcare'*/, started_at /*UTC*/, ended_at NULL,
        local_date, tz_offset_min, title, notes, rating NULL)
session_exercise(id, session_id, position, exercise_key, exercise_name,
                 exercise_type, target JSON NULL, notes)
set(id, session_exercise_id, position, done BOOL, set_type DEFAULT 'normal',
    weight_kg NULL, reps NULL, duration_s NULL, distance_m NULL,
    weight_mode NULL /*external|bodyweight|added|assisted*/, rpe NULL, notes)
```

Typed nullable columns (NULL = not applicable) validated against the YAML type
beat both a wide zero-filled row and an opaque JSON blob — they keep PR and
calendar queries as plain SQL. The alternative is a `metrics JSON` column; it
is more flexible but every query needs `json_extract`.

### Metric types — reference list

Hevy's API has eight exercise types. They are a good checklist for the YAML:

| Hevy type | Fields | PRs (Hevy) |
|---|---|---|
| `weight_reps` | weight, reps | heaviest weight, best e1RM, best set volume, best session volume, rep-max per rep count |
| `reps_only` / `bodyweight_reps` | reps | most reps (set), session reps |
| `bodyweight_assisted_reps` | assist weight, reps | most reps |
| `weight_duration` | weight, duration | heaviest weight, best time |
| `duration` | duration | best time |
| `distance_duration` | distance, duration | longest distance, longest time, best pace |
| `short_distance_weight` | distance, weight | (carries/sled) |

FitNotes' import format encodes the same thing as a `Kind` of letters —
`w`, `r`, `d`, `t` (e.g. `wr`, `dt`). Note that "better" is direction-
dependent: longer is better for a plank, shorter is better for a 5 km time.
The YAML needs a per-metric direction.

Illustrative YAML (proposal):

```yaml
metric_types:
  weight_reps:   { fields: [weight, reps], prs: [max_weight, e1rm, set_volume] }
  distance_time: { fields: [distance, duration], prs: [max_distance, best_pace] }
  time:          { fields: [duration], prs: [max_duration] }
exercises:
  - { key: bench_press, name: Bench Press (Barbell), type: weight_reps, category: chest }
  - { key: run,         name: Run,                   type: distance_time, category: cardio }
  - { key: plank,       name: Plank,                 type: time, category: core }
```

---

## 4. Formulas

### Estimated 1RM

| Formula | Equation | Used by |
|---|---|---|
| Epley | w·(1 + r/30) | OpenGym (default), JournalGym, Lyftr, RepoBean |
| Brzycki | w·36/(37 − r) | **Strong, FitNotes** (official), wger |
| Lombardi | w·r^0.1 | OpenGym (option) |

Epley and Brzycki agree at 10 reps; Brzycki diverges above that (→∞ at 37).
Strong warns estimates "break down significantly" above 12 reps.

**Eligible sets (consensus):** done; weight > 0; 1 ≤ reps ≤ cap (OpenGym caps
at 12; recommendation: 10, hard ceiling 12); not a warmup; r = 1 → w itself.
Show the source set next to the number ("est. from 100 × 8" — OpenGym).

Recommendation from the export-format review: Brzycki by default to match
Strong/FitNotes, formula configurable. The open-source apps all chose Epley.
**Open decision.**

### PR query (JournalGym, MIT — same stack)

```sql
ROW_NUMBER() OVER (PARTITION BY exercise_id
                   ORDER BY e1rm DESC, workout_date ASC, set_id ASC)  -- rank 1
```
Earliest set reaching the best wins. Load PR and e1RM PR are **separate
categories** (OpenGym); don't double-report the same exercise.

### Mid-session PR check (RepoBean)

On the first set of an exercise, fetch its best e1RM from **completed**
sessions as the baseline; after each saved set, compare; on a beat, toast and
raise the baseline so later sets don't re-fire. No history → set baseline
silently.

### Effective weight and volume (JournalGym)

```
bodyweight → bw;  added → bw + w;  assisted → max(bw − w, 0);  external → w
volume = Σ effective × reps over non-warmup sets
```
Store bodyweight on the session. Mirror the Python function as a SQL `CASE`.

---

## 5. Self-care routines — learnings

### Recurrence kinds (proposal grounded in the review)

All arithmetic on **local dates**, where
`today = (now_in_tz − day_start_hour).date()` (Loop's "midnight delay").

| kind | next due | due today | overdue | progress |
|---|---|---|---|---|
| `floating` — every N days since last done | last_done + N | today ≥ next_due | today > next_due | (today − last)/N × 100 |
| `weekdays` — mask of Mon…Sun | next set weekday ≥ today | today's bit set and not done | a scheduled day after last_done was missed (report once, don't pile up) | — |
| `per_period` — X per week/month | — | done this bucket < X | bucket ended short, or X − done > days left | done / X |
| `fixed_interval` — every N days from an anchor (Later) | smallest anchor + kN ≥ today | (today − anchor) % N = 0 | a missed occurrence | — |

Colours (OpenHabitTracker): < 80 % green, 80–99 % amber, ≥ 100 % red. Default
sort: most overdue first.

### Sessions and steps

Routine → steps (ordered, optional, `alt_group`). Logging a routine creates a
session whose steps are **snapshotted** with `done | skipped | not_done`
(SkinRitual). OpenHabitTracker's checklist has one `DoneAt` per item and clears
it on completion — step history is lost. Don't do that.

```sql
routine(id, key, name, slot /*am|pm|null*/, active)
schedule(id, owner_type /*routine|step*/, owner_id, kind, interval_days,
         anchor_date, weekdays_mask, times, period, due_soon_pct DEFAULT 80)
routine_step(id, routine_id, position, name, optional, alt_group)
-- sessions share the `session` table with kind='selfcare'
session_step(session_id, step_key, step_name, position, status, note)
```

Routines and steps could equally be defined in YAML like exercises, with only
sessions in the database — **open decision**.

### Skip semantics (decide explicitly)

- Fixed schedules: a skip excuses that occurrence — not overdue, streak
  continues (Loop).
- Floating: skip resets the clock without credit (next due = skip + N), and is
  excluded from "last done" and stats.
- Partial (some required steps skipped): suggestion — satisfies the steps that
  were done, not the routine.

### Streaks and score (Later)

- Streaks (OpenHabitTracker): calendar buckets for daily/weekly habits;
  gap-based for every-N-days.
- Strength score (Loop): `m = 0.5^(√freq / 13)`; `score = prev·m + pct·(1−m)`;
  skip days freeze the score. Clever but opaque — buckets are easier to explain.

---

## 6. Calendar & history

- **API:** `GET /calendar?from=&to=` returning per day a **summary** list
  `[{session_id, kind, title, summary, status}]` — not full sets. RepoBean
  returns every set for the month; jovandeginste preloads every GPS point just
  to render titles.
- **Click-through:** each session its own link to `/sessions/{id}`. RepoBean's
  deep link only works for the 50 most recent sessions and only reaches the
  first session of a day.
- **Month grid:** Monday-first (make week start a setting — OHT hardcodes
  Monday and ignores its own setting), prev/next, month summary.
- **Heatmap (OpenGym):** 53 week columns × 7, ending on the current week;
  5 shade levels at the 25th/50th/75th percentiles of the user's own non-zero
  days; `color-mix` on the accent token; tooltip per cell; click a day → its
  session (one) or the day list (several). ~40 lines. For Apollo, one row per
  kind or a toggle.
- **Due markers** for future dates are computed on the fly and never stored.

---

## 7. Import / export

**Proposed neutral CSV** (one row per set; ISO 8601 with offset; SI units):

```
workout_id, workout_title, workout_start, workout_end, workout_notes,
exercise_order, exercise_name, exercise_type, superset_group, exercise_notes,
set_index, set_type, weight_kg, reps, distance_m, duration_s, rpe, rest_s, set_notes
```

| Source | Shape | Gotchas |
|---|---|---|
| Strong | `Date,Workout Name,Duration,Exercise Name,Set Order,Weight,Reps,Distance,Seconds,Notes,Workout Notes,RPE` | No units (user must say kg/lb); `Set Order` W/D/F; `Rest Timer` rows; some exports `;`-delimited — sniff |
| Hevy CSV | `title,start_time,end_time,description,exercise_title,superset_id,exercise_notes,set_index,set_type,weight_kg\|weight_lbs,reps,distance_km\|distance_miles,duration_seconds,rpe` | Unit in column name; locale-dependent dates; `dropset` vs `drop_set` |
| FitNotes (iOS) | `Date,Exercise,Category,Weight (kg),Weight (lbs),Reps,Distance,Distance Unit,Time,Notes,Kind` | Date only, no session — group by date |
| JEFIT | multi-section file; sets packed as `"135x8,135x8"` | Cumulative snapshots — keep the last |
| Hevy API | JSON, UTC, SI units | Pro only; may change |

Exporting a Strong-shaped CSV too would make Apollo's data importable into
Hevy and FitNotes. Escape CSV cells against formula injection (prefix `'` to
`= + - @` — RepoBean). Exercise names differ between apps; importers need an
alias table.

**wger exercise dataset** (optional seed): Django fixture JSON in
`wger/exercises/fixtures/` — 872 exercises, English names in
`translations.json`. CC-BY-SA: keep author + license if imported. It has no
metric types; Apollo would assign them (e.g. Cardio → distance_time).

---

## 8. Cross-cutting learnings

- **Dates:** store UTC timestamps plus local date; configurable day-start hour
  and week start. OpenHabitTracker uses timestamps (so "due" depends on time of
  day) and 30-day months; SkinRitual uses N×24 h (breaks across DST);
  Beaver falls back to UTC before it knows the timezone (late-evening ticks on
  the wrong day). Configure the timezone server-side.
- **Derive, don't store:** PRs, last done, next due, streaks. If `last_done` is
  cached, a backdated insert must not move it backwards and a delete must
  recompute it.
- **Uniqueness:** don't make `(routine, date)` unique (Loop does) — AM and PM
  sessions, or two in a day, must be possible. At most `(routine, date, slot)`.
- **Real tables, not blobs:** OpenGym and Beaver store whole-user JSON blobs;
  queries and history suffer.
- **SQLite setup** (JournalGym, Lyftr): WAL, `synchronous=NORMAL`,
  `foreign_keys=ON`, `busy_timeout`; one connection. `ON DELETE RESTRICT` from
  sets to exercises, archive instead of delete. Versioned migrations table
  (JournalGym) rather than ad-hoc column checks (Lyftr). Don't commit writes
  made before an `HTTPException` (JournalGym bug).
- **PUT semantics:** JournalGym's replace-all-sets PUT plus a client that drops
  fields silently wipes RPE/set type on edit. Edit sets individually.
- **Don't log uncompleted sets** (Lyftr logs planned sets as done).
- **Input bounds** on every field (JournalGym's Pydantic `Field` limits).

---

## 9. Licenses — what can be copied

| License | Projects | Meaning for Apollo |
|---|---|---|
| MIT | JournalGym, Lyftr, RepoBean, jovandeginste | Copy with notice. JournalGym's `estimate_1rm`, `effective_weight` (+ SQL), PR CTE, migration runner, `db()` helper, and `3x8 @135` parser port directly. |
| BSD-3 | Beaver | Copy with notice |
| GPL-3.0 | OpenHabitTracker, Loop | Ideas and formulas only |
| AGPL-3.0 | wger, OpenGym | Ideas only (copied code would make Apollo AGPL) |
| CC-BY-SA / CC0 | wger exercise data | Importable with attribution |
| None | SkinRitual | Ideas only |

Formulas (Epley, Brzycki, …) are public mathematics.

---

## 10. Open decisions for the design session

1. Metric storage: typed nullable columns vs. a JSON `metrics` column.
2. 1RM formula default (Brzycki to match Strong/FitNotes, or Epley like the
   open-source apps) and rep cap (10 or 12).
3. Are self-care routines and steps defined in YAML (like exercises) or edited
   in the UI and stored in the database?
4. Which recurrence kinds ship in the MVP (proposal: floating, weekdays,
   per_period).
5. Skip and partial semantics (§5).
6. One `session` table for both workouts and self-care, or two?
7. Stale in-progress sessions: auto-close after N hours, or prompt?
8. Units: display preference kg/lb and km/mi, stored SI.
9. Seed exercises from wger's dataset, or hand-write a short YAML list?
10. Import from Strong/Hevy/FitNotes in the MVP, or later?
