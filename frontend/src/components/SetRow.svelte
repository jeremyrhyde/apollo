<script lang="ts">
  // One set. Inputs depend on the exercise's fields; values are display units
  // (weight lb/kg, distance mi/km) and seconds for duration. Changes are
  // reported through `onpatch` — the parent saves them.
  import Icon from './Icon.svelte';
  import { formatDuration, parseDuration } from '../lib/format';
  import type { FieldName, SetPatch, WorkoutSet } from '../lib/types';

  interface Props {
    set: WorkoutSet;
    index: number;
    fields: FieldName[];
    weightUnit: string;
    distanceUnit: string;
    readonly?: boolean;
    onpatch?: (patch: SetPatch) => void;
    ondelete?: () => void;
  }

  let { set, index, fields, weightUnit, distanceUnit, readonly = false, onpatch, ondelete }: Props = $props();

  const weightStep = $derived(weightUnit === 'kg' ? 2.5 : 5);
  const durationPlain = $derived(fields.includes('distance') ? 'minutes' : 'seconds');
  const canTime = $derived(fields.length === 1 && fields[0] === 'duration' && !readonly);

  // The timer stores its start instant, not a running counter: iOS suspends
  // JS timers in the background, so an incrementing counter would fall behind.
  // `now` just forces a redraw; the elapsed time is always `now - timerStart`.
  let timerStart: number | null = $state(null);
  let now = $state(Date.now());

  $effect(() => {
    if (timerStart === null) return;
    const id = setInterval(() => (now = Date.now()), 250);
    return () => clearInterval(id);
  });

  function emit(patch: SetPatch): void {
    onpatch?.(patch);
  }

  function onNumber(field: 'weight' | 'reps' | 'distance', e: Event): void {
    const raw = (e.currentTarget as HTMLInputElement).value.trim();
    if (raw === '') return emit({ [field]: null } as SetPatch);
    const value = Number(raw);
    if (!Number.isFinite(value) || value < 0) {
      (e.currentTarget as HTMLInputElement).value = String(set[field] ?? '');
      return;
    }
    emit({ [field]: field === 'reps' ? Math.round(value) : value } as SetPatch);
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
    emit({ duration: seconds });
  }

  function toggleTimer(): void {
    if (timerStart === null) {
      timerStart = Date.now();
      now = timerStart;
    } else {
      const seconds = Math.round((Date.now() - timerStart) / 1000);
      timerStart = null;
      emit({ duration: seconds });
    }
  }

  const shownDuration = $derived(
    timerStart !== null ? formatDuration(Math.round((now - timerStart) / 1000)) : formatDuration(set.duration),
  );
</script>

<div class="set" class:done={set.done} class:readonly>
  <span class="num">{index + 1}</span>
  <div class="fields">
    {#each fields as f (f)}
      {#if f === 'weight' || f === 'reps'}
        <div class="stepper">
          {#if !readonly}
            <button class="step" aria-label={`Decrease ${f}`} onclick={() => bump(f, f === 'reps' ? -1 : -weightStep)}>
              <Icon name="minus" size={16} />
            </button>
          {/if}
          <label class="value">
            <input
              inputmode={f === 'reps' ? 'numeric' : 'decimal'}
              value={set[f] ?? ''}
              placeholder="0"
              {readonly}
              aria-label={f === 'weight' ? `Weight (${weightUnit})` : 'Reps'}
              onchange={(e) => onNumber(f, e)} />
            <span>{f === 'weight' ? weightUnit : 'reps'}</span>
          </label>
          {#if !readonly}
            <button class="step" aria-label={`Increase ${f}`} onclick={() => bump(f, f === 'reps' ? 1 : weightStep)}>
              <Icon name="plus" size={16} />
            </button>
          {/if}
        </div>
      {:else if f === 'distance'}
        <label class="value wide">
          <input
            inputmode="decimal"
            value={set.distance ?? ''}
            placeholder="0.0"
            {readonly}
            aria-label={`Distance (${distanceUnit})`}
            onchange={(e) => onNumber('distance', e)} />
          <span>{distanceUnit}</span>
        </label>
      {:else}
        <label class="value wide">
          <input
            value={shownDuration}
            placeholder={durationPlain === 'minutes' ? 'min or h:mm:ss' : 'sec or m:ss'}
            readonly={readonly || timerStart !== null}
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
  {#if readonly}
    <span class="tick-static">{#if set.done}<Icon name="check" />{/if}</span>
  {:else}
    <button class="tick" class:on={set.done} aria-pressed={set.done} aria-label="Set done" onclick={() => emit({ done: !set.done })}>
      <Icon name="check" size={22} />
    </button>
    <button class="icon-btn del" aria-label="Delete set" onclick={() => ondelete?.()}><Icon name="x" size={18} /></button>
  {/if}
</div>

<style>
  .set { display: grid; grid-template-columns: 22px 1fr auto auto; align-items: center; gap: var(--space-2); }
  .set.readonly { grid-template-columns: 22px 1fr auto; }
  .num { color: var(--color-text-faint); font-size: var(--text-sm); text-align: center; }
  .fields { display: flex; flex-wrap: wrap; gap: var(--space-2); }
  .set:not(.done):not(.readonly) .value input { color: var(--color-text-muted); }
  .stepper, .value { display: inline-flex; align-items: center; gap: 2px; }
  .value {
    background: var(--color-surface-2); border-radius: var(--radius-sm); padding: 0 var(--space-2);
    min-height: var(--tap-min); border: 1px solid var(--color-border-soft);
  }
  .value input { width: 3.6em; border: 0; background: none; text-align: right; padding: 0; min-height: var(--tap-min); }
  .value.wide input { width: 6em; }
  .value span { font-size: var(--text-xs); color: var(--color-text-muted); }
  .step {
    display: grid; place-items: center; width: 36px; min-height: var(--tap-min);
    border: 0; background: none; color: var(--color-text-muted); cursor: pointer;
  }
  .tick {
    display: grid; place-items: center; width: var(--tap-min); height: var(--tap-min);
    border-radius: var(--radius-pill); border: 2px solid var(--color-border); background: none;
    color: var(--color-text-faint); cursor: pointer; transition: background var(--transition-fast), border-color var(--transition-fast);
  }
  .tick.on { background: var(--color-workout); border-color: var(--color-workout); color: var(--color-on-accent); animation: pop var(--transition); }
  .tick-static { color: var(--color-workout); }
  .del { min-width: 32px; }
  @keyframes pop { 50% { transform: scale(1.15); } }
</style>
