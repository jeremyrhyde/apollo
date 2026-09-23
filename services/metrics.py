"""Stats over logged data — not built in the MVP.

This is where derived numbers will live, as pure functions over stored sets
(SI units, done sets only), computed on read and never persisted:

- estimated 1RM per set (formula configurable; Brzycki default, Epley
  alternative; eligible sets: weight > 0, 1 ≤ reps ≤ 10, not warmups)
- personal records per exercise: heaviest weight, best e1RM, most reps,
  longest duration, longest distance, best pace
- volume per session / week / muscle group
- distance totals per exercise per period
- self-care frequency per type per period

Query shapes are listed in docs/2026-09-22-mvp-spec.md §4.
"""
