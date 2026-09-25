# Muscle map icons — spec

_2026-09-25 · approved in conversation_

## Goal

A small front + back body diagram (~36 px tall) next to each exercise that
highlights the muscles it works: **primary** muscles in the workout colour,
**secondary** muscles in a lighter tint. Shown in:

- the exercise picker rows (right side of each row),
- the exercise card headers on the active-workout screen,
- the exercise headers on the past-workout detail screen.

We'll judge the size on the phone and adjust.

## Asset

Polygon data from **react-body-highlighter** (github.com/giavinh79/react-body-highlighter,
MIT, © 2020 GV79), copied as plain coordinate data into the frontend and
rendered by our own Svelte component — no React, no npm dependency. Credit in
`THIRD_PARTY_NOTICES.md`. Exercise→muscle mappings are hand-authored, informed
by free-exercise-db (github.com/yuhonas/free-exercise-db, Unlicense).

## Muscle vocabulary

The highlightable regions of the asset become the allowed muscle names:

| Area | Muscles |
|---|---|
| Arms | `biceps`, `triceps`, `forearm` |
| Shoulders | `front-deltoids`, `back-deltoids` |
| Torso front | `chest`, `abs`, `obliques` |
| Back | `trapezius`, `upper-back` (incl. lats), `lower-back` |
| Legs | `quadriceps`, `hamstring`, `gluteal`, `adductor`, `abductors`, `calves` |

(The asset's `head`, `neck`, `knees`, `left-soleus`, `right-soleus` are drawn
as part of the silhouette but are not selectable muscles.)

## Configuration

`config/exercises.yaml` — each exercise may add:

```yaml
- { key: bench_press, name: Bench Press (Barbell), group: chest, type: weight_reps,
    muscles: { primary: [chest], secondary: [front-deltoids, triceps] } }
```

- Optional. `primary` must be non-empty; `secondary` optional; names must be
  in the vocabulary; a muscle may not appear in both lists. Errors are
  reported like other config errors (file + exercise), server stays up.
- Without `muscles`, the backend derives primaries from the exercise's
  groups: chest→chest; back→upper-back, lower-back; shoulders→front-deltoids,
  back-deltoids; biceps→biceps; triceps→triceps; legs→quadriceps, hamstring,
  calves; glutes→gluteal; core→abs, obliques; cardio→(none).
- The shipped catalog sets `muscles` for every exercise.

## API

`GET /api/catalog` — each exercise object gains
`"muscles": {"primary": [...], "secondary": [...]}`, already resolved (explicit
or derived). Nothing else changes; workouts keep referencing exercises by key.

## Frontend

- `BodyMap` component: props `primary`, `secondary`, `size` (height px,
  default 36). Front and back side by side. Unworked regions use a neutral
  body tone; colours are tokens and work in both themes. It has an
  `aria-label` like "Works chest; also front deltoids, triceps", or is hidden
  from screen readers where the exercise name already sits beside it.
- Screens look up muscles by exercise key in the catalog. An exercise no
  longer in the catalog shows no icon (history is unaffected).

## Non-goals

Left/right distinction, side delts, per-set muscle data, filtering the picker
by muscle, muscle-based stats.
