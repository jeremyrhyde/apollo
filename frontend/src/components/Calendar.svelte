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

  /* dots (kind markers, shared by week list and month grid) */
  .dot { width: 7px; height: 7px; border-radius: var(--radius-pill); flex: none; }
  .dot.workout { background: var(--color-workout); }
  .dot.selfcare { background: var(--color-selfcare); }

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
