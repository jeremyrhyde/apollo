<script lang="ts">
  import BackBar from '../../components/BackBar.svelte';
  import ConfirmSheet from '../../components/ConfirmSheet.svelte';
  import SetRow from '../../components/SetRow.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { longDate } from '../../lib/dates';
  import { formatMinutes, titleCase } from '../../lib/format';
  import { goBack, navigate } from '../../lib/router.svelte';
  import { toast, toastError } from '../../lib/toast.svelte';
  import type { Workout } from '../../lib/types';

  let { id }: { id: number } = $props();

  let workout: Workout | null = $state(null);
  let confirmDelete = $state(false);
  let busy = $state(false);

  $effect(() => {
    api.workout(id).then((w) => (workout = w)).catch(toastError);
  });

  async function edit(): Promise<void> {
    busy = true;
    try {
      await api.reopenWorkout(id);
      navigate(['workouts', 'active'], { edit: '1' });
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
      toast('Workout deleted');
      goBack(['workouts', 'history']);
    } catch (e) {
      toastError(e);
      busy = false;
    }
  }
</script>

<BackBar title={workout ? longDate(workout.local_date) : 'Workout'} fallback={['workouts', 'history']} />

{#if workout}
  <div class="row">
    {#each workout.focus as g (g)}<span class="chip">{titleCase(g)}</span>{/each}
    {#if workout.ended_at}
      <span class="muted">{formatMinutes((Date.parse(workout.ended_at) - Date.parse(workout.started_at)) / 1000)}</span>
    {:else}
      <span class="muted">in progress</span>
    {/if}
  </div>

  {#each workout.exercises as ex (ex.id)}
    <section class="card">
      <strong>{ex.name}</strong>
      {#each ex.sets as s, i (s.id)}
        <SetRow set={s} index={i} fields={ex.fields} weightUnit={app.settings!.weight_unit} distanceUnit={app.settings!.distance_unit} readonly />
      {/each}
    </section>
  {/each}

  {#if workout.notes}<p class="muted">{workout.notes}</p>{/if}

  <div class="actions">
    <button class="btn danger" disabled={busy} onclick={() => (confirmDelete = true)}>Delete</button>
    <button class="btn primary" disabled={busy || !workout.ended_at} onclick={edit}>Edit</button>
  </div>
{/if}

{#if confirmDelete}
  <ConfirmSheet title="Delete this workout?" confirmLabel="Delete" danger {busy} onconfirm={remove} oncancel={() => (confirmDelete = false)}>
    <p class="muted">This cannot be undone.</p>
  </ConfirmSheet>
{/if}

<style>
  .actions { display: grid; grid-template-columns: 1fr 2fr; gap: var(--space-2); margin-top: var(--space-4); }
</style>
