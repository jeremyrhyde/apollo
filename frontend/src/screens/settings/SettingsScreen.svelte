<script lang="ts">
  import { api } from '../../lib/api';
  import { app, updateSetting } from '../../lib/app.svelte';
  import { toast, toastError } from '../../lib/toast.svelte';
  import type { Settings } from '../../lib/types';

  type Option = { value: string; label: string };
  const SETTINGS: { key: keyof Settings; label: string; options: Option[] }[] = [
    { key: 'calendar_view', label: 'Default calendar view', options: [
      { value: 'week', label: 'Week' }, { value: 'month', label: 'Month' }, { value: 'year', label: 'Year' } ] },
    { key: 'week_start', label: 'Week starts on', options: [
      { value: 'monday', label: 'Monday' }, { value: 'sunday', label: 'Sunday' } ] },
    { key: 'weight_unit', label: 'Weight', options: [
      { value: 'lb', label: 'lb' }, { value: 'kg', label: 'kg' } ] },
    { key: 'distance_unit', label: 'Distance', options: [
      { value: 'mi', label: 'Miles' }, { value: 'km', label: 'Kilometres' } ] },
    { key: 'history_range', label: 'Default history range', options: [
      { value: '1W', label: '1 week' }, { value: '1M', label: '1 month' }, { value: '1Y', label: '1 year' } ] },
  ];

  // Shown immediately (other screens read app.settings live, so this takes
  // effect app-wide with no reload), then confirmed against the server. A
  // failure puts back whatever the server still has and reports once. `busy`
  // blocks a second tap on the same setting until its request settles, so
  // two quick taps on one control can't have their responses race.
  //
  // Units are the exception: other screens show numbers the API already
  // converted server-side using the *stored* unit. Flipping the label here
  // before the PUT resolves could show an old-unit number under the new
  // unit if a fetch lands in that window, so weight_unit/distance_unit are
  // applied only once the server confirms — `busy` (disabling the control)
  // is the only pending feedback, and there's nothing to roll back.
  let busy: Partial<Record<keyof Settings, boolean>> = $state({});
  const PESSIMISTIC: (keyof Settings)[] = ['weight_unit', 'distance_unit'];

  // A plain `settings[key] = value` with key typed as `keyof Settings` (a
  // union) doesn't type-check — TS can't prove the value matches whichever
  // key it turns out to be at runtime. Routed through a generic K it can.
  function setLocal<K extends keyof Settings>(key: K, value: Settings[K]): void {
    if (app.settings) app.settings[key] = value;
  }

  async function change(key: keyof Settings, value: string): Promise<void> {
    const settings = app.settings;
    if (!settings || busy[key] || settings[key] === value) return;
    busy[key] = true;
    if (PESSIMISTIC.includes(key)) {
      try {
        await updateSetting(key, value as Settings[typeof key]);
        toast('Saved');
      } catch (e) {
        toastError(e);
      } finally {
        busy[key] = false;
      }
      return;
    }
    const previous = settings[key];
    setLocal(key, value as Settings[typeof key]);
    try {
      await api.setSetting(key, value);
      toast('Saved');
    } catch (e) {
      setLocal(key, previous);
      toastError(e);
    } finally {
      busy[key] = false;
    }
  }
</script>

<header class="page-head"><h1>Settings</h1></header>

{#each SETTINGS as s (s.key)}
  <section class="setting">
    <span class="label">{s.label}</span>
    <div class="segmented" role="radiogroup" aria-label={s.label}>
      {#each s.options as o (o.value)}
        <button
          role="radio"
          aria-checked={app.settings?.[s.key] === o.value}
          class:on={app.settings?.[s.key] === o.value}
          disabled={busy[s.key]}
          onclick={() => change(s.key, o.value)}>
          {o.label}
        </button>
      {/each}
    </div>
  </section>
{/each}

<p class="muted small">
  Exercises, skincare types, colors and the timezone live in <code>config/*.yaml</code> on the server; edit them and restart.
</p>

{#if app.configErrors.length}
  <section class="banner warn stack">
    <strong>Config errors</strong>
    <ul>{#each app.configErrors as e (e)}<li>{e}</li>{/each}</ul>
  </section>
{/if}

<style>
  .setting { display: grid; gap: var(--space-2); }
  .label { font-size: var(--text-sm); color: var(--color-text-muted); }
  .small { font-size: var(--text-sm); }
  ul { margin: 0; padding-left: var(--space-4); }
  li { overflow-wrap: anywhere; }
  .segmented button:disabled { opacity: 0.5; cursor: default; }
</style>
