<script lang="ts">
  import { onMount } from 'svelte';
  import { fly } from 'svelte/transition';
  import BackBar from '../../components/BackBar.svelte';
  import BodyMap from '../../components/BodyMap.svelte';
  import ConfirmSheet from '../../components/ConfirmSheet.svelte';
  import ExercisePicker from '../../components/ExercisePicker.svelte';
  import Icon from '../../components/Icon.svelte';
  import SetRow from '../../components/SetRow.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { longDate } from '../../lib/dates';
  import { formatDuration, plural } from '../../lib/format';
  import { dur } from '../../lib/motion';
  import { musclesFor } from '../../lib/muscles';
  import { PatchQueue } from '../../lib/patchQueue';
  import { goBack, navigate } from '../../lib/router.svelte';
  import { clearSetTimers } from '../../lib/timers';
  import { toast, toastError } from '../../lib/toast.svelte';
  import type { SetPatch, Workout, WorkoutExercise, WorkoutSet } from '../../lib/types';

  let workout = $state<Workout | null>(null);
  let loaded = $state(false);
  let loadError: string | null = $state(null);
  let picking = $state(false);
  let confirmFinish = $state(false);
  let confirmDiscard = $state(false);
  let busy = $state(false);
  let addButton: HTMLButtonElement | undefined = $state();
  let now = $state(Date.now());

  const sets = new PatchQueue<WorkoutSet>();

  // A finished workout reopened from its detail page: the server keeps the
  // flag, so edit mode survives a reload or a resume from the hub.
  const editMode = $derived(!!workout?.reopened);

  // Cleared on unmount so a slow load can't write into a screen that's gone.
  let live = true;

  async function load(): Promise<void> {
    loadError = null;
    loaded = false;
    try {
      const w = await api.openWorkout();
      if (live) workout = w;
    } catch (e) {
      // Inline, not a toast: "No workout in progress" + Start would be a lie
      // here, and Start would 409 if one is in fact open.
      if (live) loadError = e instanceof Error ? e.message : String(e);
    } finally {
      if (live) loaded = true;
    }
  }

  onMount(() => {
    void load();
    return () => {
      live = false;
    };
  });

  $effect(() => {
    const id = setInterval(() => (now = Date.now()), 1000);
    return () => clearInterval(id);
  });

  const elapsed = $derived(workout ? Math.max(0, Math.round((now - Date.parse(workout.started_at)) / 1000)) : 0);
  const allSets = $derived(workout ? workout.exercises.flatMap((e) => e.sets) : []);
  const doneCount = $derived(allSets.filter((s) => s.done).length);
  const undoneCount = $derived(allSets.length - doneCount);

  async function start(): Promise<void> {
    if (busy) return;
    busy = true;
    try {
      workout = await api.startWorkout();
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }

  function closePicker(): void {
    picking = false;
    addButton?.focus();
  }

  async function addExercise(key: string): Promise<void> {
    closePicker();
    if (!workout) return;
    try {
      workout.exercises.push(await api.addExercise(workout.id, key));
    } catch (e) {
      toastError(e);
    }
  }

  async function removeExercise(ex: WorkoutExercise): Promise<void> {
    if (!workout) return;
    const i = workout.exercises.indexOf(ex);
    workout.exercises.splice(i, 1);
    try {
      await sets.settled();
      await api.removeExercise(workout.id, ex.id);
      clearSetTimers(ex.sets);
    } catch (e) {
      workout.exercises.splice(i, 0, ex);
      toastError(e);
    }
  }

  async function addSet(ex: WorkoutExercise): Promise<void> {
    if (!workout) return;
    try {
      await sets.settled(); // the new set copies the last one's values server-side
      ex.sets.push(await api.addSet(workout.id, ex.id));
    } catch (e) {
      toastError(e);
    }
  }

  // Optimistic: show the change now; PatchQueue saves edits to a set in order
  // and only lets the newest one's response (or rollback) through, with one
  // toast if any save in the burst failed.
  function patchSet(set: WorkoutSet, patch: SetPatch): void {
    const before = $state.snapshot(set);
    Object.assign(set, patch);
    void sets.run(set.id, before, () => api.updateSet(set.id, patch), (v) => Object.assign(set, v), toastError);
  }

  async function deleteSet(ex: WorkoutExercise, set: WorkoutSet): Promise<void> {
    const i = ex.sets.indexOf(set);
    ex.sets.splice(i, 1);
    try {
      await sets.settled();
      await api.deleteSet(set.id);
    } catch (e) {
      ex.sets.splice(i, 0, set);
      toastError(e);
    }
  }

  // Back while editing: set edits are already saved, so leave by saving —
  // unless nothing is ticked, where saving would delete the workout; that
  // goes through the sheet's warning instead.
  function backFromEdit(): void {
    if (doneCount === 0) confirmFinish = true;
    else void finish(true);
  }

  async function finish(leaving = false): Promise<void> {
    if (!workout || busy) return;
    busy = true;
    try {
      await sets.settled(); // a just-ticked set must be saved before unticked ones are dropped
      const result = await api.finishWorkout(workout.id);
      clearSetTimers(allSets);
      confirmFinish = false;
      if (result.deleted || !result.workout) {
        toast('Nothing was ticked — workout discarded');
        navigate(['workouts'], {}, { replace: true });
      } else if (editMode) {
        toast('Workout saved');
        // Edit was pushed on top of the detail page: return to that entry
        // (it remounts and refetches) rather than stacking a second copy.
        goBack(['workouts', String(result.workout.id)]);
      } else {
        toast('Workout finished');
        navigate(['workouts', String(result.workout.id)], {}, { replace: true });
      }
    } catch (e) {
      toastError(e);
      // Offline Back mustn't strand the user; the edits themselves are saved.
      if (leaving) goBack(['workouts', String(workout.id)]);
    } finally {
      busy = false;
    }
  }

  async function discard(): Promise<void> {
    if (!workout || busy) return;
    busy = true;
    try {
      await sets.settled();
      await api.deleteWorkout(workout.id);
      clearSetTimers(allSets);
      confirmDiscard = false;
      toast('Workout discarded');
      navigate(['workouts'], {}, { replace: true });
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }
</script>

<BackBar title={editMode ? 'Edit workout' : 'Workout'} fallback={['workouts']} onback={editMode ? backFromEdit : undefined}>
  {#snippet actions()}
    {#if workout && !editMode}
      <button class="icon-btn" aria-label="Discard workout" onclick={() => (confirmDiscard = true)}><Icon name="trash" /></button>
    {/if}
  {/snippet}
</BackBar>

{#if loadError}
  <div class="center-state">
    <p>Couldn't load the workout: {loadError}</p>
    <button class="btn" onclick={load}>Retry</button>
  </div>
{:else if loaded && !workout}
  <div class="center-state">
    <p class="muted">No workout in progress.</p>
    <button class="btn primary big" disabled={busy} onclick={start}><Icon name="plus" /> Start workout</button>
  </div>
{:else if workout}
  {#if editMode}
    <!-- Elapsed time since a past start means nothing while editing. -->
    <p class="elapsed">{longDate(workout.local_date)}</p>
  {:else}
    <p class="elapsed" aria-live="off"><Icon name="clock" size={16} /> {formatDuration(elapsed)}</p>
  {/if}

  {#each workout.exercises as ex (ex.id)}
    {@const muscles = app.catalog && musclesFor(app.catalog, ex.exercise_key)}
    <section class="card" in:fly={{ y: 12, duration: dur(180) }}>
      <div class="ex-head">
        <strong>{ex.name}</strong>
        {#if muscles}<BodyMap primary={muscles.primary} secondary={muscles.secondary} />{/if}
        <button class="icon-btn" aria-label={`Remove ${ex.name}`} onclick={() => removeExercise(ex)}><Icon name="x" size={18} /></button>
      </div>
      {#each ex.sets as s, i (s.id)}
        <SetRow
          set={s}
          index={i}
          fields={ex.fields}
          weightUnit={app.settings!.weight_unit}
          distanceUnit={app.settings!.distance_unit}
          onpatch={(p) => patchSet(s, p)}
          ondelete={() => deleteSet(ex, s)} />
      {/each}
      <button class="btn small" onclick={() => addSet(ex)}><Icon name="plus" size={16} /> Add set</button>
    </section>
  {:else}
    <p class="muted">Add your first exercise to begin.</p>
  {/each}

  <div class="bottom">
    <button class="btn" bind:this={addButton} onclick={() => (picking = true)}><Icon name="plus" /> Add exercise</button>
    <button class="btn primary" disabled={busy} onclick={() => (confirmFinish = true)}>{editMode ? 'Save' : 'Finish'}</button>
  </div>
{/if}

{#if picking && app.catalog}
  <ExercisePicker catalog={app.catalog} onpick={addExercise} onclose={closePicker} />
{/if}

{#if confirmFinish && workout}
  <ConfirmSheet
    title={editMode ? 'Save changes?' : 'Finish workout?'}
    confirmLabel={editMode ? 'Save' : 'Finish'}
    danger={doneCount === 0}
    {busy}
    onconfirm={() => finish()}
    oncancel={() => (confirmFinish = false)}>
    <p>
      {plural(workout.exercises.length, 'exercise')} · {plural(doneCount, 'set')} done{#if !editMode}&nbsp;· {formatDuration(elapsed)}{/if}
    </p>
    {#if doneCount === 0}
      <p class="warn-text">No sets are ticked — {editMode ? 'saving' : 'finishing'} deletes this workout.</p>
    {:else if undoneCount > 0}
      <p class="muted">{plural(undoneCount, 'unticked set')} will be dropped.</p>
    {/if}
  </ConfirmSheet>
{/if}

{#if confirmDiscard}
  <ConfirmSheet title="Discard this workout?" confirmLabel="Discard" danger {busy} onconfirm={discard} oncancel={() => (confirmDiscard = false)}>
    <p class="muted">Everything logged in it will be deleted.</p>
  </ConfirmSheet>
{/if}

<style>
  .warn-text { color: var(--color-danger); }
  .elapsed { display: flex; align-items: center; gap: var(--space-1); color: var(--color-text-muted); font-variant-numeric: tabular-nums; }
  .ex-head { display: flex; align-items: center; gap: var(--space-3); margin-right: calc(-1 * var(--space-2)); }
  .ex-head strong { flex: 1; }
  .bottom {
    position: sticky; bottom: calc(var(--tabbar-h) + var(--safe-bottom) + var(--space-2));
    display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-2);
    padding: var(--space-2); background: var(--color-bg); border-radius: var(--radius-lg);
  }
  @media (min-width: 900px) { .bottom { bottom: var(--space-4); } }
</style>
