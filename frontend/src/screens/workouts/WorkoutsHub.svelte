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
  let loaded = $state(false);
  let days: Record<string, CalendarEntry[]> = $state({});
  let busy = $state(false);
  let confirmDiscard = $state(false);
  let now = $state(Date.now());

  const range = $derived(rangeFor('month', app.today, app.settings!.week_start));

  $effect(() => {
    api
      .openWorkout()
      .then((w) => (open = w))
      .catch(toastError)
      .finally(() => (loaded = true)); // failed or not, stop blocking the Start button
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
      // A 409 usually means a workout was already open (another tab, a
      // stale reload) — refetch so the hub shows it instead of a dead end.
      try {
        open = await api.openWorkout();
      } catch (e2) {
        toastError(e2);
      }
    } finally {
      busy = false;
    }
  }

  async function finishStale(): Promise<void> {
    if (!open || busy) return;
    busy = true;
    try {
      const result = await api.finishWorkout(open.id, true);
      toast(result.deleted ? 'Nothing was ticked — workout discarded' : 'Workout finished');
      open = null;
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }

  async function discard(): Promise<void> {
    if (!open || busy) return;
    busy = true;
    try {
      await api.deleteWorkout(open.id);
      toast('Workout discarded');
      open = null;
      confirmDiscard = false;
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }
</script>

<header class="page-head"><h1>Workouts</h1></header>

{#if loaded}
  {#if open?.stale}
    <section class="banner warn stack">
      <p>A workout from {longDate(open.local_date)} is still open.</p>
      <div class="row">
        <button class="btn" disabled={busy} onclick={finishStale}>Finish</button>
        <button class="btn danger" disabled={busy} onclick={() => (confirmDiscard = true)}>Discard</button>
        <button class="btn" disabled={busy} onclick={() => navigate(['workouts', 'active'])}>Keep going</button>
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
  <ConfirmSheet title="Discard this workout?" confirmLabel="Discard" danger {busy} onconfirm={discard} oncancel={() => (confirmDiscard = false)}>
    <p class="muted">Everything logged in it will be deleted.</p>
  </ConfirmSheet>
{/if}

<style>
  .resume { display: flex; justify-content: space-between; align-items: center; width: 100%; min-height: 56px; cursor: pointer; color: var(--color-text); text-align: left; }
  .between { justify-content: space-between; }
  .stats { opacity: 0.7; }
</style>
