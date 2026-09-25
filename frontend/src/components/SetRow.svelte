<script lang="ts">
  // One set. Inputs depend on the exercise's fields; values are display units
  // (weight lb/kg, distance mi/km) and seconds for duration. Changes are
  // reported through `onpatch` — the parent saves them.
  import { onMount } from 'svelte';
  import Icon from './Icon.svelte';
  import { formatDuration, parseDecimal, parseDuration } from '../lib/format';
  import { setTimerKey } from '../lib/timers';
  import type { FieldName, SetPatch, WorkoutSet } from '../lib/types';

  interface Props {
    set: WorkoutSet;
    index: number;
    fields: FieldName[];
    weightUnit: string;
    distanceUnit: string;
    onpatch?: (patch: SetPatch) => void;
    ondelete?: () => void;
  }

  let { set, index, fields, weightUnit, distanceUnit, onpatch, ondelete }: Props = $props();

  const weightStep = $derived(weightUnit === 'kg' ? 2.5 : 5);
  const durationPlain = $derived(fields.includes('distance') ? 'minutes' : 'seconds');
  const canTime = $derived(fields.length === 1 && fields[0] === 'duration');

  // The timer stores its start instant, not a running counter: iOS suspends
  // JS timers in the background, so an incrementing counter would fall behind.
  // `now` just forces a redraw; the elapsed time is always `now - timerStart`.
  // The instant is mirrored to localStorage (keyed by set id) so a reload or
  // a remount of this row — closing the tab mid-set, revisiting the active
  // workout — doesn't lose an in-progress timer.
  // SQLite reuses row ids (no AUTOINCREMENT), so a leftover key could
  // otherwise restore a bogus timer onto an unrelated, later set with the
  // same id — ignore (and drop) anything older than this.
  const MAX_TIMER_AGE_MS = 12 * 60 * 60 * 1000;

  function timerKey(): string {
    return setTimerKey(set.id);
  }

  function loadTimerStart(): number | null {
    try {
      const raw = localStorage.getItem(timerKey());
      const value = raw === null ? null : Number(raw);
      if (value === null || !Number.isFinite(value)) return null;
      if (Date.now() - value > MAX_TIMER_AGE_MS) {
        localStorage.removeItem(timerKey());
        return null;
      }
      return value;
    } catch {
      return null;
    }
  }

  function saveTimerStart(value: number | null): void {
    try {
      if (value === null) localStorage.removeItem(timerKey());
      else localStorage.setItem(timerKey(), String(value));
    } catch {
      /* private mode / storage blocked — the timer just won't survive a reload */
    }
  }

  let timerStart: number | null = $state(null);
  let now = $state(Date.now());

  // Restored once after mount, not in the `$state` initializer above, which Svelte's lint flags for reading a prop only once.
  onMount(() => {
    timerStart = loadTimerStart();
  });

  $effect(() => {
    if (timerStart === null) return;
    const id = setInterval(() => (now = Date.now()), 250);
    return () => clearInterval(id);
  });

  function emit(patch: SetPatch): void {
    onpatch?.(patch);
  }

  function onNumber(field: 'weight' | 'reps' | 'distance', e: Event): void {
    const input = e.currentTarget as HTMLInputElement;
    const raw = input.value.trim();
    if (raw === '') return emit({ [field]: null } as SetPatch);
    const value = parseDecimal(raw);
    if (value === null) {
      input.value = String(set[field] ?? '');
      return;
    }
    const normalized = field === 'reps' ? Math.round(value) : value;
    input.value = String(normalized); // normalize what's shown even when unchanged: "135.0" → "135", "9.4" reps → "9"
    emit({ [field]: normalized } as SetPatch);
  }

  function bump(field: 'weight' | 'reps', delta: number): void {
    const current = set[field] ?? 0;
    emit({ [field]: Math.max(0, Math.round((current + delta) * 100) / 100) } as SetPatch);
  }

  function onDuration(e: Event): void {
    const input = e.currentTarget as HTMLInputElement;
    const seconds = parseDuration(input.value, durationPlain);
    if (seconds === null && input.value.trim() !== '') {
      input.value = formatDuration(set.duration);
      return;
    }
    input.value = formatDuration(seconds); // e.g. "90" → "1:30"
    emit({ duration: seconds });
  }

  function toggleTimer(): void {
    if (timerStart === null) {
      timerStart = Date.now();
      now = timerStart;
      saveTimerStart(timerStart);
    } else {
      const seconds = Math.round((Date.now() - timerStart) / 1000);
      timerStart = null;
      saveTimerStart(null);
      emit({ duration: seconds });
    }
  }

  function toggleDone(): void {
    // Ticking done while the timer is running commits the elapsed time in
    // the same patch — otherwise it would be silently dropped.
    if (timerStart !== null) {
      const seconds = Math.round((Date.now() - timerStart) / 1000);
      timerStart = null;
      saveTimerStart(null);
      emit({ done: true, duration: seconds });
      return;
    }
    emit({ done: !set.done });
  }

  function handleDelete(): void {
    saveTimerStart(null);
    ondelete?.();
  }

  const shownDuration = $derived(
    timerStart !== null ? formatDuration(Math.round((now - timerStart) / 1000)) : formatDuration(set.duration),
  );
</script>

<div class="set" class:done={set.done}>
  <div class="set-top">
    <span class="num">Set {index + 1}</span>
    <div class="set-actions">
      <button class="tick" class:on={set.done} aria-pressed={set.done} aria-label="Set done" onclick={toggleDone}>
        <Icon name="check" size={20} />
      </button>
      <button class="icon-btn del" aria-label="Delete set" onclick={handleDelete}><Icon name="x" size={18} /></button>
    </div>
  </div>
  <div class="fields">
    {#each fields as f (f)}
      {#if f === 'weight' || f === 'reps'}
        <div class="stepper">
          <button class="step" aria-label={`Decrease ${f}`} onclick={() => bump(f, f === 'reps' ? -1 : -weightStep)}>
            <Icon name="minus" size={16} />
          </button>
          <label class="value">
            <input
              inputmode={f === 'reps' ? 'numeric' : 'decimal'}
              value={set[f] ?? ''}
              placeholder="0"
              aria-label={f === 'weight' ? `Weight (${weightUnit})` : 'Reps'}
              onchange={(e) => onNumber(f, e)} />
            <span>{f === 'weight' ? weightUnit : 'reps'}</span>
          </label>
          <button class="step" aria-label={`Increase ${f}`} onclick={() => bump(f, f === 'reps' ? 1 : weightStep)}>
            <Icon name="plus" size={16} />
          </button>
        </div>
      {:else if f === 'distance'}
        <label class="value wide">
          <input
            inputmode="decimal"
            value={set.distance ?? ''}
            placeholder="0.0"
            aria-label={`Distance (${distanceUnit})`}
            onchange={(e) => onNumber('distance', e)} />
          <span>{distanceUnit}</span>
        </label>
      {:else}
        <label class="value wide">
          <input
            value={shownDuration}
            placeholder={durationPlain === 'minutes' ? 'min or h:mm:ss' : 'sec or m:ss'}
            readonly={timerStart !== null}
            aria-label="Duration"
            onchange={onDuration} />
          {#if canTime}
            <button class="step" aria-label={timerStart === null ? 'Start timer' : 'Stop timer'} onclick={toggleTimer}>
              <Icon name={timerStart === null ? 'play' : 'stop'} size={16} />
            </button>
          {/if}
        </label>
      {/if}
    {/each}
  </div>
</div>

<style>
  /* Two lines rather than one cramped row: set number + done/delete on top,
     the metric fields (which can themselves wrap) below, full width. */
  .set { display: grid; gap: var(--space-2); padding: var(--space-2) 0; border-bottom: 1px solid var(--color-border-soft); }
  .set:last-child { border-bottom: 0; }
  .set-top { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); min-height: var(--tap-min); }
  .set-actions { display: flex; align-items: center; gap: var(--space-1); }
  .num { color: var(--color-text-faint); font-size: var(--text-sm); }
  .fields { display: flex; flex-wrap: wrap; gap: var(--space-2); }
  .set:not(.done) .value input { color: var(--color-text-muted); }
  .stepper, .value { display: inline-flex; align-items: center; gap: 2px; }
  .value {
    background: var(--color-surface-2); border-radius: var(--radius-sm); padding: 0 var(--space-2);
    min-height: var(--tap-min); border: 1px solid var(--color-border-soft);
  }
  .value input { width: 3.6em; border: 0; background: none; text-align: right; padding: 0; min-height: var(--tap-min); }
  .value.wide input { width: 6em; }
  .value span { font-size: var(--text-xs); color: var(--color-text-muted); }
  .step {
    display: grid; place-items: center; width: var(--tap-min); min-height: var(--tap-min);
    border: 0; background: none; color: var(--color-text-muted); cursor: pointer;
  }
  .tick {
    display: grid; place-items: center; width: var(--tap-min); height: var(--tap-min);
    border-radius: var(--radius-pill); border: 2px solid var(--color-border); background: none;
    color: var(--color-text-faint); cursor: pointer; transition: background var(--transition-fast), border-color var(--transition-fast);
  }
  .tick.on { background: var(--color-workout); border-color: var(--color-workout); color: var(--color-on-kind); animation: pop var(--transition); }
  @keyframes pop { 50% { transform: scale(1.15); } }
</style>
