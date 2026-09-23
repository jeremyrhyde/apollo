<script lang="ts">
  import BackBar from '../../components/BackBar.svelte';
  import RangeFilter from '../../components/RangeFilter.svelte';
  import SessionCard from '../../components/SessionCard.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { longDate } from '../../lib/dates';
  import { navigate } from '../../lib/router.svelte';
  import { toastError } from '../../lib/toast.svelte';
  import type { Range, SelfcareSession } from '../../lib/types';

  let { range }: { range?: string } = $props();

  const current: Range = $derived(
    range === '1W' || range === '1M' || range === '1Y' ? range : app.settings!.history_range,
  );
  let items: SelfcareSession[] = $state([]);
  let loaded = $state(false);
  let error: string | null = $state(null);

  // `range` lives in the query string, and App.svelte keys this screen on
  // path only — switching 1W/1M/1Y re-runs this effect without a remount, so
  // guard against an older request resolving after a newer one.
  $effect(() => {
    const r = current;
    let live = true;
    error = null;
    api
      .selfcareSessions(r)
      .then((list) => {
        if (live) {
          items = list;
          loaded = true;
        }
      })
      .catch((e: unknown) => {
        if (live) {
          items = [];
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

<BackBar title="Past sessions" fallback={['selfcare']} />
<RangeFilter value={current} onchange={(r) => navigate(['selfcare', 'history'], { range: r }, { replace: true })} />

{#if error}
  <p class="error">Couldn't load past sessions: {error}</p>
{:else if loaded && items.length === 0}
  <p class="muted">No sessions in this period.</p>
{/if}

<div class="stack">
  {#each items as s (s.id)}
    <SessionCard
      kind="selfcare"
      title={longDate(s.local_date)}
      subtitle={s.category_name}
      chips={s.types.map((t) => t.name)}
      onclick={() => navigate(['selfcare', String(s.id)])} />
  {/each}
</div>

<style>
  .error { color: var(--color-danger); }
</style>
