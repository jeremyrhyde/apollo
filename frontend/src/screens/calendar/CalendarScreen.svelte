<script lang="ts">
  import Calendar from '../../components/Calendar.svelte';
  import Icon from '../../components/Icon.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import {
    addDays, addMonths, isValidISODate, monthLabel, rangeFor, shortDate, shortDateWithYear,
  } from '../../lib/dates';
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
  const anchor = $derived(query.date && isValidISODate(query.date) ? query.date : app.today);
  const kind = $derived(query.kind === 'workout' || query.kind === 'selfcare' ? query.kind : 'all');
  const kinds: Kind[] = $derived(kind === 'all' ? ['workout', 'selfcare'] : [kind as Kind]);
  const weekStart = $derived(app.settings!.week_start);
  const range = $derived(rangeFor(view, anchor, weekStart));
  // Year view always covers parts of two calendar years; a week can too,
  // around New Year's — spell out the year in both those cases.
  const spansYears = $derived(range.from.slice(0, 4) !== range.to.slice(0, 4));
  const title = $derived(
    view === 'month'
      ? monthLabel(anchor)
      : view === 'year' || spansYears
        ? `${shortDateWithYear(range.from)} – ${shortDateWithYear(range.to)}`
        : `${shortDate(range.from)} – ${shortDate(range.to)}`,
  );

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
    // Year view is a rolling 53-week heatmap, not a calendar year, so step it
    // by whole weeks (364 = 52 * 7) to keep today's weekday column aligned —
    // addMonths(±12) snaps to the 1st and would drop the last few weeks.
    const date =
      view === 'week'
        ? addDays(anchor, 7 * direction)
        : view === 'year'
          ? addDays(anchor, 364 * direction)
          : addMonths(anchor, direction);
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
