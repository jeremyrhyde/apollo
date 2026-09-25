<script lang="ts">
  import BackBar from '../../components/BackBar.svelte';
  import ConfirmSheet from '../../components/ConfirmSheet.svelte';
  import { api, ApiError } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { longDate } from '../../lib/dates';
  import { formatMinutes, setCells, titleCase } from '../../lib/format';
  import { goBack, navigate } from '../../lib/router.svelte';
  import { clearSetTimers } from '../../lib/timers';
  import { toast, toastError } from '../../lib/toast.svelte';
  import type { Workout } from '../../lib/types';

  let { id }: { id: number } = $props();

  let workout: Workout | null = $state(null);
  let error: string | null = $state(null);
  let confirmDelete = $state(false);
  let busy = $state(false);

  $effect(() => {
    workout = null;
    error = null;
    let live = true;
    api
      .workout(id)
      .then((w) => {
        if (live) workout = w;
      })
      .catch((e: unknown) => {
        if (!live) return;
        // A 404 means this workout no longer exists (deleted, or emptied by
        // a Save with nothing ticked) — nothing to show or retry.
        if (e instanceof ApiError && e.status === 404) {
          navigate(['workouts', 'history'], {}, { replace: true });
          return;
        }
        error = e instanceof Error ? e.message : String(e);
        toastError(e);
      });
    return () => {
      live = false;
    };
  });

  async function edit(): Promise<void> {
    busy = true;
    try {
      await api.reopenWorkout(id);
      navigate(['workouts', 'active']);
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
      if (workout) clearSetTimers(workout.exercises.flatMap((e) => e.sets));
      toast('Workout deleted');
      goBack(['workouts', 'history']);
    } catch (e) {
      toastError(e);
      busy = false;
    }
  }
</script>

<BackBar title={workout ? longDate(workout.local_date) : 'Workout'} fallback={['workouts', 'history']} />

{#if error}
  <p class="error">Couldn't load this workout: {error}</p>
{:else if !workout}
  <div class="center-state"><p class="muted">Loading…</p></div>
{:else}
  <div class="row">
    {#each workout.focus as g (g)}<span class="chip">{titleCase(g)}</span>{/each}
    {#if workout.ended_at}
      <span class="muted">{formatMinutes((Date.parse(workout.ended_at) - Date.parse(workout.started_at)) / 1000)}</span>
    {:else if workout.reopened}
      <span class="muted">being edited</span>
    {:else}
      <span class="muted">in progress</span>
    {/if}
  </div>

  {#each workout.exercises as ex (ex.id)}
    <section class="card exercise">
      <strong>{ex.name}</strong>
      <ol class="sets">
        {#each ex.sets as s, i (s.id)}
          <li class:undone={!s.done}>
            <span class="num">Set {i + 1}</span>
            {#each setCells(s, ex.fields, app.settings!.weight_unit, app.settings!.distance_unit) as cell, c (c)}
              <span>{cell}</span>
            {/each}
          </li>
        {/each}
      </ol>
    </section>
  {/each}

  {#if workout.notes}<p class="muted">{workout.notes}</p>{/if}

  <div class="actions">
    <button class="btn danger" disabled={busy} onclick={() => (confirmDelete = true)}>Delete</button>
    {#if workout.reopened}
      <button class="btn primary" onclick={() => navigate(['workouts', 'active'])}>Keep editing</button>
    {:else}
      <button class="btn primary" disabled={busy || !workout.ended_at} onclick={edit}>Edit</button>
    {/if}
  </div>
{/if}

{#if confirmDelete}
  <ConfirmSheet title="Delete this workout?" confirmLabel="Delete" danger {busy} onconfirm={remove} oncancel={() => (confirmDelete = false)}>
    <p class="muted">This cannot be undone.</p>
  </ConfirmSheet>
{/if}

<style>
  .error { color: var(--color-danger); }
  .exercise { gap: var(--space-2); }
  .sets { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-1); font-variant-numeric: tabular-nums; }
  /* One line per set; fixed columns so values line up down the list. */
  .sets li { display: grid; grid-template-columns: 4em 5.5em 5.5em; gap: var(--space-3); }
  .num { color: var(--color-text-muted); }
  .undone { color: var(--color-text-muted); }
  .actions { display: grid; grid-template-columns: 1fr 2fr; gap: var(--space-2); margin-top: var(--space-4); }
</style>
