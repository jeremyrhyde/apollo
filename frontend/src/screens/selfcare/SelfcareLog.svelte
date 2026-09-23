<script lang="ts">
  import { untrack } from 'svelte';
  import BackBar from '../../components/BackBar.svelte';
  import ConfirmSheet from '../../components/ConfirmSheet.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { isValidISODate } from '../../lib/dates';
  import { goBack, navigate } from '../../lib/router.svelte';
  import { toast, toastError } from '../../lib/toast.svelte';
  import type { DueStatus } from '../../lib/types';

  let { id, initialDate }: { id?: number; initialDate?: string } = $props();

  // A date from the query string (the Calendar day view's "Log skincare for
  // this day" link): only honoured when it parses and isn't in the future —
  // the backend 422s a future date, so an invalid value just falls back to
  // today. `untrack` because this is an initial value only, like `id` below;
  // App.svelte remounts this screen whenever the path (hence `id`) changes.
  const categories = $derived(app.catalog!.selfcare);
  let categoryKey = $state(app.catalog!.selfcare[0]?.key ?? '');
  let selected: string[] = $state([]);
  const presetDate = untrack(() =>
    initialDate && isValidISODate(initialDate) && initialDate <= app.today ? initialDate : null,
  );
  let date = $state(untrack(() => presetDate ?? app.today));
  // Create mode sends `date` only when it was chosen (a valid `?date=` or the
  // picker); otherwise the server's today applies at save time, which stays
  // right in a tab left open past midnight.
  let datePicked = $state(presetDate !== null);
  let notes = $state('');
  let status: Record<string, DueStatus> = $state({});
  let busy = $state(false);
  let confirmDelete = $state(false);

  // Edit mode only: gates the form so it doesn't flash create-mode defaults
  // before the real session arrives, and what to diff Save's PATCH against.
  let loaded = $state(untrack(() => id === undefined));
  let loadError: string | null = $state(null);
  let original: { types: string[]; date: string; notes: string } | null = null;

  // Until a date is picked, the field tracks today (refreshed on focus and
  // every few minutes by App.svelte).
  $effect(() => {
    if (id === undefined && !datePicked) date = app.today;
  });

  const category = $derived(categories.find((c) => c.key === categoryKey));
  const dateOk = $derived(date !== '' && date <= app.today);

  $effect(() => {
    api
      .due()
      .then((items) => (status = Object.fromEntries(items.map((i) => [`${i.category_key}.${i.type_key}`, i.status]))))
      .catch(toastError);
  });

  $effect(() => {
    if (id === undefined) return;
    api
      .selfcareSession(id)
      .then((s) => {
        categoryKey = s.category_key;
        selected = s.types.map((t) => t.key);
        date = s.local_date;
        notes = s.notes ?? '';
        original = { types: [...selected], date, notes };
        loaded = true;
      })
      .catch((e: unknown) => {
        loadError = e instanceof Error ? e.message : String(e);
        loaded = true;
        toastError(e);
      });
  });

  function toggle(key: string): void {
    selected = selected.includes(key) ? selected.filter((k) => k !== key) : [...selected, key];
  }

  const flagged = (key: string) => ['due', 'overdue'].includes(status[`${categoryKey}.${key}`] ?? '');

  const sameTypes = (a: string[], b: string[]) => a.length === b.length && [...a].sort().join() === [...b].sort().join();

  async function save(): Promise<void> {
    if (!dateOk) return;
    busy = true;
    try {
      if (id === undefined) {
        await api.logSelfcare({ category: categoryKey, types: selected, date: datePicked ? date : undefined, notes: notes || null });
        toast('Logged');
        navigate(['selfcare'], {}, { replace: true });
      } else {
        // Only the fields that actually changed — the backend rejects an
        // explicit `date: null`, so `date` is included only when it moved.
        const patch: { types?: string[]; date?: string; notes?: string | null } = {};
        if (!original || !sameTypes(selected, original.types)) patch.types = selected;
        if (!original || date !== original.date) patch.date = date;
        const currentNotes = notes || null;
        if (!original || currentNotes !== (original.notes || null)) patch.notes = currentNotes;
        await api.updateSelfcare(id, patch);
        toast('Saved');
        // Not a plain navigate: that would replace this entry with the
        // detail URL, leaving two adjacent history entries at the same URL
        // (Back would look like a no-op). goBack instead reuses the detail
        // entry we arrived from, so it remounts and refetches.
        goBack(['selfcare', String(id)]);
      }
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }

  async function remove(): Promise<void> {
    if (id === undefined) return;
    busy = true;
    try {
      await api.deleteSelfcare(id);
      toast('Session deleted');
      // Not goBack: the entry we'd return to is this very session's detail
      // page, which no longer exists once it's deleted.
      navigate(['selfcare', 'history'], {}, { replace: true });
    } catch (e) {
      toastError(e);
      busy = false;
    }
  }
</script>

<BackBar title={id === undefined ? 'Log skincare' : 'Edit session'} fallback={['selfcare']} />

{#if loadError}
  <p class="error">Couldn't load this session: {loadError}</p>
{:else if loaded}
  {#if categories.length > 1 && id === undefined}
    <div class="segmented" role="group" aria-label="Category">
      {#each categories as c (c.key)}
        <button class:on={categoryKey === c.key} onclick={() => { categoryKey = c.key; selected = []; }}>{c.name}</button>
      {/each}
    </div>
  {/if}

  <label class="field">
    <span>Date</span>
    <input class="input" type="date" bind:value={date} max={app.today} oninput={() => (datePicked = true)} />
  </label>

  {#if category}
    <div class="field">
      <span>What did you do?</span>
      <div class="types">
        {#each category.types as t (t.key)}
          <button
            class="type"
            class:on={selected.includes(t.key)}
            class:flagged={flagged(t.key)}
            aria-pressed={selected.includes(t.key)}
            onclick={() => toggle(t.key)}>
            {t.name}
          </button>
        {/each}
      </div>
    </div>
  {:else}
    <p class="muted">No self-care categories configured — see config/selfcare.yaml.</p>
  {/if}

  <label class="field">
    <span>Note (optional)</span>
    <textarea class="input" bind:value={notes} maxlength="2000"></textarea>
  </label>

  <button class="btn primary big" disabled={busy || selected.length === 0 || !dateOk} onclick={save}>
    {id === undefined ? 'Save' : 'Save changes'}
  </button>

  {#if id !== undefined}
    <button class="btn danger block" disabled={busy} onclick={() => (confirmDelete = true)}>Delete session</button>
  {/if}
{/if}

{#if confirmDelete}
  <ConfirmSheet title="Delete this session?" confirmLabel="Delete" danger {busy} onconfirm={remove} oncancel={() => (confirmDelete = false)}>
    <p class="muted">This cannot be undone.</p>
  </ConfirmSheet>
{/if}

<style>
  .error { color: var(--color-danger); }
  .types { display: flex; flex-wrap: wrap; gap: var(--space-2); }
  .type {
    min-height: var(--tap-min); padding: 0 var(--space-4); border-radius: var(--radius-pill);
    background: var(--color-surface-2); border: 2px solid var(--color-border); cursor: pointer;
    transition: background var(--transition-fast), border-color var(--transition-fast);
  }
  .type.flagged { border-color: var(--color-warn); }
  .type.on { background: var(--color-selfcare); border-color: var(--color-selfcare); color: var(--color-on-kind); font-weight: 600; }
</style>
