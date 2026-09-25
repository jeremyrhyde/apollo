# Muscle map icons — plan

Spec: `docs/2026-09-25-muscle-map-spec.md`. Branch `feat/mvp`. Two tasks, in order.

---

### Task 1: Backend — muscles in the catalog

**Files:** `schemas/config.py`, `services/catalog.py` (if the derivation lives
there), `core/api.py`, `config/exercises.yaml`, tests (`tests/test_config_schema.py`,
`tests/test_catalog.py`, `tests/test_api.py`), `THIRD_PARTY_NOTICES.md` (new).

1. `schemas/config.py`: a `Muscle` Literal with the 17 names from the spec;
   an `ExerciseMuscles` model (`primary: list[Muscle]` min 1, `secondary:
   list[Muscle] = []`, strict/extra-forbid, validator: no duplicates within a
   list, no muscle in both); `Exercise.muscles: ExerciseMuscles | None = None`.
   Error messages name the exercise key.
2. Derivation (where the catalog lookups live): `GROUP_MUSCLES` mapping from
   the spec; a method returning an exercise's resolved
   `{"primary": [...], "secondary": [...]}` — explicit if set, else the
   de-duplicated union of its groups' muscles in group order, secondary empty.
3. `core/api.py` `/api/catalog`: add `"muscles"` to each exercise object.
4. `config/exercises.yaml`: add `muscles` to every exercise (below); update the
   file's header comment to list the allowed muscle names.
5. `THIRD_PARTY_NOTICES.md`: react-body-highlighter MIT notice (full licence
   text, © 2020 GV79, source URL) and a courtesy line for free-exercise-db.
6. Tests: valid muscles; unknown name; empty primary; overlap; duplicate;
   derivation from groups (incl. cardio → empty); API includes resolved
   muscles; the shipped config still validates with zero errors.

Proposed mappings (primary; secondary):

| key | primary | secondary |
|---|---|---|
| bench_press | chest | front-deltoids, triceps |
| incline_dumbbell_press | chest, front-deltoids | triceps |
| push_up | chest | triceps, front-deltoids, abs |
| barbell_row | upper-back | back-deltoids, biceps, trapezius, lower-back, forearm |
| lat_pulldown | upper-back | biceps, back-deltoids, forearm |
| pull_up | upper-back | biceps, forearm, back-deltoids, trapezius |
| deadlift | lower-back, gluteal, hamstring | quadriceps, trapezius, upper-back, forearm, adductor |
| overhead_press | front-deltoids | triceps, trapezius, abs |
| lateral_raise | front-deltoids, back-deltoids | trapezius |
| bicep_curl | biceps | forearm |
| hammer_curl | biceps, forearm | |
| tricep_pushdown | triceps | |
| dip | triceps, chest | front-deltoids |
| squat | quadriceps, gluteal | hamstring, adductor, lower-back, calves |
| leg_press | quadriceps, gluteal | hamstring, adductor, calves |
| romanian_deadlift | hamstring, gluteal | lower-back, forearm |
| lunge | quadriceps, gluteal | hamstring, adductor, calves |
| calf_raise | calves | |
| plank | abs | obliques, lower-back, front-deltoids |
| side_plank | obliques | abs, gluteal, abductors |
| hanging_leg_raise | abs | obliques, forearm |
| run | quadriceps, hamstring, calves | gluteal |
| stair_climb | quadriceps, gluteal | calves, hamstring |
| cycle | quadriceps | hamstring, calves, gluteal |
| row_erg | upper-back, quadriceps | hamstring, gluteal, biceps, back-deltoids, lower-back |

Verify: `uv run pytest -q`. Commit: `feat: muscles per exercise in the catalog`.

---

### Task 2: Frontend — BodyMap and placements

**Files:** `frontend/src/lib/bodymap.ts` (new, data), `frontend/src/components/BodyMap.svelte`
(new), `frontend/src/lib/types.ts`, `frontend/src/lib/muscles.ts` (+ test, lookup
helpers), `ExercisePicker.svelte`, `screens/workouts/ActiveWorkout.svelte`,
`screens/workouts/WorkoutDetail.svelte`, possibly `styles/tokens.css`.

1. Copy the anterior and posterior polygon data from react-body-highlighter's
   `src/assets/index.ts` (fetch the raw file from GitHub; pin the commit SHA in
   a header comment with the MIT credit). Keep only what's needed:
   `{ muscle: string; svgPoints: string[] }[]` for each view, plus the viewBox
   the library uses. Don't hand-edit coordinates.
2. `types.ts`: `Muscle` union; `ExerciseDef.muscles: { primary: Muscle[]; secondary: Muscle[] }`.
3. `lib/muscles.ts`: `musclesFor(catalog, exerciseKey)` → the def's muscles or
   `null` if the key is gone; `musclesLabel(m)` → "Works chest; also front
   deltoids, triceps". vitest for both.
4. `BodyMap.svelte`: props `primary`, `secondary`, `size = 36`. Front and back
   SVGs side by side, each `height={size}`, width from the viewBox aspect.
   Region fill: primary `var(--color-workout)`; secondary `color-mix(in srgb,
   var(--color-workout) 45%, var(--color-body))`; others `var(--color-body)`.
   Add `--color-body` to tokens (dark and light) — a neutral tone that reads
   against `--color-surface` in both themes. `role="img"` + `aria-label`, or an
   `ariaHidden` prop for places where the name is adjacent.
5. Placements:
   - ExercisePicker items: name left, BodyMap right, row stays ≥ var(--tap-min).
   - ActiveWorkout exercise card header: BodyMap beside the exercise name.
   - WorkoutDetail exercise header: same.
   No icon when `musclesFor` returns null.
6. Screenshot check at 390 px (headless Chrome through a 390 px iframe — Chrome
   won't size a window below ~500 px), dark and light, of the picker and a
   workout detail; include the PNG paths in the report. Stop any server by PID.

Verify: `npm run check` (0/0), `npx vitest run`, `npm run build`, `make test`.
Commit: `feat(ui): muscle map icons in the picker and workout screens`.
