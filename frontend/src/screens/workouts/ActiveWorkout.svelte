<script lang="ts">
  import { fly } from 'svelte/transition';
  import BackBar from '../../components/BackBar.svelte';
  import ConfirmSheet from '../../components/ConfirmSheet.svelte';
  import ExercisePicker from '../../components/ExercisePicker.svelte';
  import Icon from '../../components/Icon.svelte';
  import SetRow from '../../components/SetRow.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { longDate } from '../../lib/dates';
  import { formatDuration, plural } from '../../lib/format';
  import { dur } from '../../lib/motion';
  import { PatchQueue } from '../../lib/patchQueue';
  import { navigate } from '../../lib/router.svelte';
  import { toast, toastError } from '../../lib/toast.svelte';
  import type { SetPatch, Workout, WorkoutExercise, WorkoutSet } from '../../lib/types';

  let { editing = false }: { editing?: boolean } = $props();

  let workout = $state<Workout | null>(null);
  let loaded = $state(false);
  let editMode = $state(false);
  let picking = $state(false);
  let confirmFinish = $state(false);
  let confirmDiscard = $state(false);
  let busy = $state(false);
  let now = $state(Date.now());

  const sets = new PatchQueue<WorkoutSet>();

  // A reopened workout looks like any open one to the API, and it can be
  // resumed later from the hub or calendar without `?edit=1`. So entering
  // with `?edit=1` marks it on this device, keyed by id and start time
  // (SQLite reuses ids; a new workout never shares both).
  const EDIT_KEY = 'apollo:editing-workout';
  const editTag = (w: Workout) => `${w.id}@${w.started_at}`;

  function readEditMark(w: Workout): boolean {
    try {
      return localStorage.getItem(EDIT_KEY) === editTag(w);
    } catch {
      return false;
    }
  }

  function writeEditMark(w: Workout | null): void {
    try {
      if (w) localStorage.setItem(EDIT_KEY, editTag(w));
      else localStorage.removeItem(EDIT_KEY);
    } catch {
      /* storage unavailable — the label falls back to Finish on resume */
    }
  }

  // SetRow persists a running timer under this key; drop them once the sets
  // can no longer be timed.
  function clearTimers(list: WorkoutSet[]): void {
    try {
      for (const s of list) localStorage.removeItem(`apollo:set-timer:${s.id}`);
    } catch {
      /* storage unavailable */
    }
  }

  function show(w: Workout | null): void {
    workout = w;
    editMode = !!w && (editing || readEditMark(w));
    if (w && editMode) writeEditMark(w);
  }

  $effect(() => {
    let live = true;
    api
      .openWorkout()
      .then((w) => {
        if (live) show(w);
      })
      .catch(toastError)
      .finally(() => (loaded = true));
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
      show(await api.startWorkout());
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }

  async function addExercise(key: string): Promise<void> {
    picking = false;
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
      clearTimers(ex.sets);
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
  // and only lets the newest one's response (or rollback) through.
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

  async function finish(): Promise<void> {
    if (!workout || busy) return;
    busy = true;
    try {
      await sets.settled(); // a just-ticked set must be saved before unticked ones are dropped
      const result = await api.finishWorkout(workout.id);
      clearTimers(allSets);
      writeEditMark(null);
      confirmFinish = false;
      if (result.deleted || !result.workout) {
        toast('Nothing was ticked — workout discarded');
        navigate(['workouts'], {}, { replace: true });
      } else {
        toast(editMode ? 'Workout saved' : 'Workout finished');
        navigate(['workouts', String(result.workout.id)], {}, { replace: true });
      }
    } catch (e) {
      toastError(e);
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
      clearTimers(allSets);
      writeEditMark(null);
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

<BackBar title={editMode ? 'Edit workout' : 'Workout'} fallback={['workouts']}>
  {#snippet actions()}
    {#if workout && !editMode}
      <button class="icon-btn" aria-label="Discard workout" onclick={() => (confirmDiscard = true)}><Icon name="trash" /></button>
    {/if}
  {/snippet}
</BackBar>

{#if loaded && !workout}
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
    <section class="card" in:fly={{ y: 12, duration: dur(180) }}>
      <div class="ex-head">
        <strong>{ex.name}</strong>
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
    <button class="btn" onclick={() => (picking = true)}><Icon name="plus" /> Add exercise</button>
    <button class="btn primary" disabled={busy} onclick={() => (confirmFinish = true)}>{editMode ? 'Save' : 'Finish'}</button>
  </div>
{/if}

{#if picking && app.catalog}
  <ExercisePicker catalog={app.catalog} onpick={addExercise} onclose={() => (picking = false)} />
{/if}

{#if confirmFinish && workout}
  <ConfirmSheet
    title={editMode ? 'Save changes?' : 'Finish workout?'}
    confirmLabel={editMode ? 'Save' : 'Finish'}
    {busy}
    onconfirm={finish}
    oncancel={() => (confirmFinish = false)}>
    <p>
      {plural(workout.exercises.length, 'exercise')} · {plural(doneCount, 'set')} done{#if !editMode}&nbsp;· {formatDuration(elapsed)}{/if}
    </p>
    {#if undoneCount > 0}
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
  .elapsed { display: flex; align-items: center; gap: var(--space-1); color: var(--color-text-muted); font-variant-numeric: tabular-nums; }
  .ex-head { display: flex; justify-content: space-between; align-items: center; margin-right: calc(-1 * var(--space-2)); }
  .bottom {
    position: sticky; bottom: calc(var(--tabbar-h) + var(--safe-bottom) + var(--space-2));
    display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-2);
    padding: var(--space-2); background: var(--color-bg); border-radius: var(--radius-lg);
  }
  @media (min-width: 900px) { .bottom { bottom: var(--space-4); } }
</style>
