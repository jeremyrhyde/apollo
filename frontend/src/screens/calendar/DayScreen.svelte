<script lang="ts">
  import BackBar from '../../components/BackBar.svelte';
  import SessionCard from '../../components/SessionCard.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { longDate } from '../../lib/dates';
  import { openEntry } from '../../lib/entries';
  import { navigate } from '../../lib/router.svelte';
  import { toastError } from '../../lib/toast.svelte';
  import type { CalendarEntry, Kind } from '../../lib/types';

  let { date, kind }: { date: string; kind: string } = $props();

  const kinds: Kind[] = $derived(kind === 'workout' || kind === 'selfcare' ? [kind] : ['workout', 'selfcare']);
  let entries: CalendarEntry[] = $state([]);
  let loaded = $state(false);
  let error: string | null = $state(null);

  $effect(() => {
    const wanted = kinds;
    let live = true;
    error = null;
    api
      .calendar(date, date, wanted)
      .then((r) => {
        if (live) {
          entries = r[0]?.entries ?? [];
          loaded = true;
        }
      })
      .catch((e: unknown) => {
        if (live) {
          error = e instanceof Error ? e.message : String(e);
          loaded = true;
        }
        toastError(e);
      });
    return () => {
      live = false;
    };
  });
</script>

<BackBar title={longDate(date)} fallback={['calendar']} />

{#if error}
  <p class="error">Couldn't load this day: {error}</p>
{:else if loaded && entries.length === 0}
  <p class="muted">Nothing logged on this day.</p>
{/if}

<div class="stack">
  {#each entries as e (`${e.kind}-${e.id}`)}
    <SessionCard
      kind={e.kind}
      title={e.title}
      subtitle={e.summary}
      meta={e.in_progress ? 'in progress' : undefined}
      onclick={() => openEntry(e)} />
  {/each}
</div>

{#if date <= app.today}
  <button class="btn block" onclick={() => navigate(['selfcare', 'log'], { date })}>Log skincare for this day</button>
{/if}

<style>
  .error { color: var(--color-danger); }
</style>
