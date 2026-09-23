# Research: workout, self-care and calendar tracking apps

_Deep-research run, 2026-09-22. Research only — no implementation decisions._

## Summary

Existing workout apps settle on one shared pattern: each exercise gets a type (weight and reps, bodyweight or assisted reps, duration, distance and duration), and that type decides both which fields you log per set and which personal records (PRs) are tracked. Hevy documents this most clearly. Its estimated 1RM (one-rep max) is calculated from each set's weight and reps, but Hevy doesn't say which formula it uses. For a self-hosted app like Apollo, the most useful open-source references are wger (a mature Django app with an exercise database under a Creative Commons licence), OpenGym (weekly plans, timed exercises, progression rules, a yearly activity heatmap), Lyftr (Go and SQLite) and JournalGym (FastAPI and SQLite, the same backend stack as Apollo, but very immature). For self-care routines, the best-evidenced model is OpenHabitTracker's: show how far through its "every N days" interval each item is (for example 120% when 2 days overdue) and sort by that, with streaks as an optional extra. Loop Habit Tracker instead uses targets like "X times per Y days". For the calendar and history view, the verified patterns are a month grid with a count of sessions per day, a clickable list of past sessions with a detail view and CSV export, and a GitHub-style yearly heatmap. Evidence for skincare-specific apps and for a combined calendar covering both workouts and self-care was not found or verified. That is both a gap in this research and a place where Apollo could stand out.

## Findings

### The exercise type decides both the logged fields and the PR set.

The exercise type decides both the logged fields and the PR set. Hevy: weight and reps exercises get Heaviest Weight, Best 1RM, Best Set Volume and Best Session Volume, plus set records (the heaviest weight for each rep count). Bodyweight and assisted exercises get only Most Reps (Set) and Session Reps, with no weight-based PRs. Duration-only exercises (plank, wall sit) get Best Time. Distance and duration exercises (running, cycling) get Longest Distance and Longest Time, and their chart also shows Best Pace. For Apollo, a YAML file where each exercise declares its type, with the type bringing its own metric fields and PR rules, matches how Hevy works.

- **Confidence:** high (verification vote 3-0 across 4 merged claims)
- **Evidence:** Hevy's own help centre (updated 2026-09-16) has a table of PRs per exercise type. The same table also lists Weighted bodyweight (Heaviest weight, Best Set Volume) and Weight duration (Heaviest weight, Best time). The article's glossary contradicts its table on Longest Time vs Best Time, so the direction in which a time counts as better needs to be set per exercise type.
- **Sources:** https://help.hevyapp.com/hc/en-us/articles/35649367857175-Personal-Records-PRs-and-Set-Records-Explained-How-They-Work-in-the-Hevy-App, https://help.hevyapp.com/hc/en-us/articles/35382889578135-Exercise-Performance-Tracking-in-Library-Weight-Bodyweight-Cardio-and-Duration-Based-Exercises

### Estimated 1RM is standard in workout apps: Hevy, JournalGym and OpenGym all calculate it from a set's weight and reps rather than recording an actual single-rep lift.

Estimated 1RM is standard in workout apps: Hevy, JournalGym and OpenGym all calculate it from a set's weight and reps rather than recording an actual single-rep lift. Hevy doesn't name its formula. OpenGym uses your best eligible set, tells you which set that was, and draws a progress curve per exercise. Apollo will need to choose a formula (Epley, Brzycki, etc.) and decide which sets count toward it.

- **Confidence:** high (verification vote 3-0)
- **Evidence:** Hevy: '1RM ... uses reps and weight from a set to estimate the max weight you could lift for a single rep.' No formula is named in either Hevy article. OpenGym's README: 'Estimated 1RM — per exercise, from your best eligible set (it names which one), with its own progress curve.'
- **Sources:** https://help.hevyapp.com/hc/en-us/articles/35649367857175-Personal-Records-PRs-and-Set-Records-Explained-How-They-Work-in-the-Hevy-App, https://github.com/alexpcosta/opengym, https://github.com/swagsystems/journalgym-app

### A flat table with one row per logged set, holding optional weight, reps, distance and time columns, is a simple storage and import/export model that already works in practice.

A flat table with one row per logged set, holding optional weight, reps, distance and time columns, is a simple storage and import/export model that already works in practice. FitNotes (iOS) imports CSV with the columns Date, Exercise, Category, Weight (kg), Weight (lbs), Reps, Distance, Distance Unit, Time, Notes and Kind, with the sets for an exercise grouped together.

- **Confidence:** medium (verification vote 3-0 (a related claim that FitNotes stores metric types as w/r/d/t flags was refuted 0-3))
- **Evidence:** Official FitNotes documentation. This is the import format, not necessarily how the app stores data internally. It works well as an export format for Apollo or as a way to bring in history from other apps.
- **Sources:** https://www.getfitnotes.com/docs/migrate-from-other-apps.html

### wger is the most mature open-source reference: a free, self-hostable (Docker) workout manager with routines, automatic weight progression rules, and a built-in exercise database that the community contributes to.

wger is the most mature open-source reference: a free, self-hostable (Docker) workout manager with routines, automatic weight progression rules, and a built-in exercise database that the community contributes to. The code is AGPL-3.0, while the exercise data is under Creative Commons licences set per entry, so the exercise library could be reused separately with attribution.

- **Confidence:** high (verification vote 3-0 (2 merged claims))
- **Evidence:** README: 'Create flexible routines with automatic weight progression rules'; 'Application Code: AGPL-3.0-or-later; Exercise/Ingredient Data: Creative Commons (see individual entries)'. The AGPL applies if code is copied, not if the schema is only used as a model. Reusing the exercise data requires attribution and may be share-alike (usually CC-BY-SA).
- **Sources:** https://github.com/wger-project/wger

### OpenGym (self-hosted, AGPL, about 351 stars) organises training as a weekly plan with one routine per weekday, drawn from a library of 1,324 exercises with animated demos.

OpenGym (self-hosted, AGPL, about 351 stars) organises training as a weekly plan with one routine per weekday, drawn from a library of 1,324 exercises with animated demos. Timed exercises (planks, hangs, wall sits, loaded carries) are logged by time, bodyweight exercises progress by reps, and cardio is logged as time plus speed. You pick a progression scheme per routine and can override it per exercise: linear, Greyskull LP, double progression, or adding time. It reports estimated 1RM, effort per set (RIR/RPE), a GitHub-style yearly activity heatmap, a muscle map, and PR detection.

- **Confidence:** high (verification vote 3-0 (3 merged claims))
- **Evidence:** The README states each of these features. The repo is a fork of DuarteSantos8/openGym that adds an optional AI coach. The exercise count is what the author reports.
- **Sources:** https://github.com/alexpcosta/opengym

### Two smaller self-hosted projects use stacks close to Apollo's.

Two smaller self-hosted projects use stacks close to Apollo's. JournalGym is built on FastAPI and SQLite (with a React PWA frontend), is MIT-licensed, and has tables for users, workout sessions, exercises, sets, body measurements and goals. It has set types for external-load, bodyweight, added-weight and assisted-weight, quick entry like '3x8 @135', and reports estimated 1RM, volume, PRs and weekly consistency. Lyftr (MIT, Go/Gin and a single SQLite file, React web app plus a React Native app, about 342 stars, beta) has an 800+ exercise library, a program builder, a guided full-screen active-workout mode with a rest timer, PRs, progression charts, muscle diagrams and a dashboard.

- **Confidence:** medium (verification vote 3-0 (6 merged claims))
- **Evidence:** All from the projects' own READMEs; the code was not checked. JournalGym is very immature (4 commits, 0 stars) and covers strength training only, with no cardio or time/distance metrics. Its backend schema is a possible starting point to study, not a proven design.
- **Sources:** https://github.com/swagsystems/journalgym-app, https://github.com/Cawlumm/lyftr

### The workout-tracker built with AI that most closely matches Apollo is RepoBean/workout-tracker, which describes itself as 'vibe coded' with LLMs.

The workout-tracker built with AI that most closely matches Apollo is RepoBean/workout-tracker, which describes itself as 'vibe coded' with LLMs. It has a guided active session with set logging and rest timers, a toast when you hit a new PR mid-session, and a history list where you can browse past sessions, open details and export to CSV. It also has a monthly calendar grid showing how often you worked out, and an optional AI coach where you supply your own API key. This matches Apollo's 'start new workout' flow and its calendar click-through.

- **Confidence:** medium (verification vote 3-0 (3 merged claims))
- **Evidence:** The verifier cloned the repo (last commit 2026-09-14) and confirmed Calendar.tsx draws a month grid using useCalendarSessions(year, month) to count sessions per day, and that /api/sessions/export-csv escapes cells against spreadsheet formula injection. The stack is React 19, Express 5, SQLite and Docker. It is a single hobby project with 0 stars.
- **Sources:** https://github.com/RepoBean/workout-tracker

### For self-care routines, the interval-elapsed model suits skincare-style upkeep better than streaks.

For self-care routines, the interval-elapsed model suits skincare-style upkeep better than streaks. OpenHabitTracker shows how much of each habit's 'every N days' interval has passed: 12 days into a 10-day interval reads 120%, and a 4-day interval that is 2 days overdue reads 150%. The list is sorted by that percentage, overdue items are highlighted (it has no notifications), the badge changes colour from green to amber to red, and streaks exist only as an option since v1.2.2, off by default. This maps directly onto Apollo's 'last done / due today / overdue' needs: due date = last done + interval, and overdue % = time since last done / interval.

- **Confidence:** medium (verification vote 3-0 and 2-1)
- **Evidence:** The developer's own site, which reads partly as marketing but describes how the app behaves. The code is open source (C#/.NET Blazor). The same page has a comparison table covering Beaver Habits, HabitTrove and HabitSync, which could be a lead for further comparison.
- **Sources:** https://openhabittracker.net/self-hosted-habit-tracker.html, https://github.com/Jinjinov/OpenHabitTracker

### Loop Habit Tracker (open source, Android) models recurrence as a target of X repetitions per Y days (for example 3 times per week, or every other day) rather than as fixed calendar dates.

Loop Habit Tracker (open source, Android) models recurrence as a target of X repetitions per Y days (for example 3 times per week, or every other day) rather than as fixed calendar dates. That is a different model from a fixed interval measured from when you last did something. Apollo probably needs both: 'every N days since last done' for things like exfoliating, and fixed weekday or frequency targets for daily AM/PM routines.

- **Confidence:** medium (verification vote 3-0)
- **Evidence:** README: 'Loop supports habits with more complex schedules, such as 3 times per week or every other day.' The verifier noted these are frequency targets, not calendar recurrence like 'every Monday'.
- **Sources:** https://github.com/iSoron/uhabits

### Two calendar and history patterns showed up in the verified sources and could be combined for Apollo: a month grid showing how many sessions happened each day, opening into a day's sessions and their details (RepoBean), and a GitHub-style yearly heatmap shaded by training time (OpenGym).

Two calendar and history patterns showed up in the verified sources and could be combined for Apollo: a month grid showing how many sessions happened each day, opening into a day's sessions and their details (RepoBean), and a GitHub-style yearly heatmap shaded by training time (OpenGym). No verified source showed a single calendar that combines workouts with self-care or habit sessions.

- **Confidence:** medium (verification vote 3-0)
- **Evidence:** Month grid confirmed in RepoBean's code. Heatmap stated in OpenGym's README ('Activity heatmap — a GitHub-style year view, shaded by time spent training').
- **Sources:** https://github.com/RepoBean/workout-tracker, https://github.com/alexpcosta/opengym

## Refuted claims

- ~~Hevy gives each exercise a type that decides how it is measured. There are seven types: weight & reps, assisted, bodyweight reps, weighted bodyweight, duration, weighted duration, and distance & duration.~~ (0-3, https://help.hevyapp.com/hc/en-us/articles/35649367857175-Personal-Records-PRs-and-Set-Records-Explained-How-They-Work-in-the-Hevy-App)
- ~~FitNotes stores each exercise's metric type as a combination of four flags, w (weight), r (reps), d (distance) and t (time), so strength and cardio exercises share one set table.~~ (0-3, https://www.getfitnotes.com/docs/migrate-from-other-apps.html)

## Caveats

Almost all evidence comes from each vendor's or project's own documentation or README. Features were not tested hands-on, and the small projects (JournalGym, RepoBean, Lyftr) are hobby or beta work with few stars. Hevy's help pages returned 403 to direct fetches, so they were checked through the Zendesk API and search snippets. Hevy's own glossary contradicts its PR table on Best Time vs Longest Time. Features change, and Hevy's articles were updated 2026-09-16. Several apps named in the question (Strong, JEFIT, Strava, workout.lol, Habitica, Beaver Habit Tracker, HabitNest, Tududi) and every skincare-specific app produced no verified claims, so the self-care and calendar sections rest on only 2 to 3 sources. Two claims were refuted: that Hevy has exactly seven exercise types, and that FitNotes stores metric types as w/r/d/t flags. Licences need attention before reuse: wger and OpenGym are AGPL, JournalGym and Lyftr are MIT, and wger's exercise data is Creative Commons with licences set per entry.

## Open questions

- How do skincare-specific apps (e.g. routine or product trackers) model multi-step AM/PM routines, product rotation such as retinoid nights, and per-step intervals? None were verified here.
- Which 1RM formula should Apollo use (Epley, Brzycki, or several), and which sets should count (for example capping reps at 10 to 12)?
- Should one recurrence model cover both 'every N days since last done' (floating intervals) and fixed weekday or X-per-period schedules, and how would that be expressed in YAML config?
- What do wger's actual Django models (exercise, routine, slot/set config, workout log) and Strong's/Hevy's CSV exports look like at field level, and could one of them become Apollo's import/export format?

## Sources

- [primary] https://help.hevyapp.com/hc/en-us/articles/35649367857175-Personal-Records-PRs-and-Set-Records-Explained-How-They-Work-in-the-Hevy-App — Workout data model and PR calculation
- [primary] https://help.hevyapp.com/hc/en-us/articles/35382889578135-Exercise-Performance-Tracking-in-Library-Weight-Bodyweight-Cardio-and-Duration-Based-Exercises — Workout data model and PR calculation
- [primary] https://www.getfitnotes.com/docs/migrate-from-other-apps.html — Workout data model and PR calculation
- [primary] https://github.com/wger-project/wger — Open-source self-hosted workout trackers
- [primary] https://github.com/swagsystems/journalgym-app — Open-source self-hosted workout trackers
- [primary] https://github.com/alexpcosta/opengym — Open-source self-hosted workout trackers
- [primary] https://github.com/Cawlumm/lyftr — Open-source self-hosted workout trackers
- [primary] https://github.com/RepoBean/workout-tracker — Open-source self-hosted workout trackers
- [secondary] https://github.com/topics/workout-tracker — Open-source self-hosted workout trackers
- [primary] https://openhabittracker.net/self-hosted-habit-tracker.html — Recurring routine and overdue tracking
- [primary] https://github.com/iSoron/uhabits — Recurring routine and overdue tracking
- [primary] https://github.com/daya0576/beaverhabits — Recurring routine and overdue tracking
- [blog] https://github.com/EmmaVellard/SkinRitual — Recurring routine and overdue tracking
- [primary] https://opengym.duarte-santos.ch/ — Calendar and heatmap history UI
- [forum] https://github.com/danielleon21/fit-tracker/pull/11 — Calendar and heatmap history UI
- [primary] https://community.obsidian.md/plugins/habits — Calendar and heatmap history UI
- [primary] https://github.com/jovandeginste/workout-tracker — Calendar and heatmap history UI
- [blog] https://habitheat.com/heatmap-habit-tracker/ — Calendar and heatmap history UI
- [blog] https://getfitoapp.com/en/best-workout-data-insight-and-charts-design-app/ — Calendar and heatmap history UI
- [primary] https://github.com/kapekost/workout-tracker — DIY and AI-built personal health dashboards
- [primary] https://github.com/coleam00/habit-tracker — DIY and AI-built personal health dashboards
- [primary] https://github.com/Poisson-seawater/habit-tracker — DIY and AI-built personal health dashboards
