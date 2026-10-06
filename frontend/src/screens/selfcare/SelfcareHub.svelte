<script lang="ts">
  import Calendar from '../../components/Calendar.svelte';
  import ConfigNotice from '../../components/ConfigNotice.svelte';
  import Icon from '../../components/Icon.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { monthLabel, rangeFor } from '../../lib/dates';
  import { dueText } from '../../lib/format';
  import { navigate } from '../../lib/router.svelte';
  import { toastError } from '../../lib/toast.svelte';
  import type { CalendarEntry, DueItem } from '../../lib/types';

  let due: DueItem[] = $state([]);
  let dueError: string | null = $state(null);
  let days: Record<string, CalendarEntry[]> = $state({});

  const range = $derived(rangeFor('month', app.today, app.settings!.week_start));

  $effect(() => {
    dueError = null;
    api
      .due()
      .then((d) => (due = d))
      .catch((e: unknown) => {
        dueError = e instanceof Error ? e.message : String(e);
        toastError(e);
      });
  });

  $effect(() => {
    const { from, to } = range;
    api
      .calendar(from, to, ['selfcare'])
      .then((r) => (days = Object.fromEntries(r.map((d) => [d.date, d.entries]))))
      .catch(toastError);
  });
</script>

<div class="hub">
  <div class="hub-main">
    <header class="page-head"><h1>Self-care</h1></header>

    <ConfigNotice />

    <button class="btn primary big" onclick={() => navigate(['selfcare', 'log'])}><Icon name="plus" /> Log skincare</button>

    {#if dueError}
      <p class="error">Couldn't load what's due: {dueError}</p>
    {:else if due.length}
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
  </div>

  <div class="hub-side">
    <button class="card" onclick={() => navigate(['calendar'], { kind: 'selfcare', view: 'month' })}>
      <span class="row between"><strong>{monthLabel(app.today)}</strong><Icon name="chevron-right" /></span>
      <Calendar view="month" anchor={app.today} weekStart={app.settings!.week_start} today={app.today} {days} kinds={['selfcare']} compact />
    </button>
  </div>

  <div class="hub-foot">
    <button class="btn block" onclick={() => navigate(['selfcare', 'history'])}><Icon name="clock" /> Past sessions</button>
  </div>
</div>

<style>
  .error { color: var(--color-danger); }
  .between { justify-content: space-between; }
  .due { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
  .due li { display: grid; grid-template-columns: 12px 1fr auto; align-items: center; gap: var(--space-2); min-height: var(--space-8); }
  .status { width: 10px; height: 10px; border-radius: var(--radius-pill); background: var(--color-text-faint); }
  .ok .status { background: var(--color-accent); }
  .soon .status { background: var(--color-warn); }
  .never .status, .due li.due .status, .overdue .status { background: var(--color-danger); }
  .when { font-size: var(--text-sm); color: var(--color-text-muted); }
  .overdue .when { color: var(--color-danger); }
</style>
