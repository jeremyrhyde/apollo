<script lang="ts">
  import BackBar from '../../components/BackBar.svelte';
  import RangeFilter from '../../components/RangeFilter.svelte';
  import SessionCard from '../../components/SessionCard.svelte';
  import { api } from '../../lib/api';
  import { app } from '../../lib/app.svelte';
  import { longDate } from '../../lib/dates';
  import { formatMinutes, plural, titleCase } from '../../lib/format';
  import { navigate } from '../../lib/router.svelte';
  import { toastError } from '../../lib/toast.svelte';
  import type { Range, WorkoutSummary } from '../../lib/types';

  let { range }: { range?: string } = $props();

  const current: Range = $derived(
    range === '1W' || range === '1M' || range === '1Y' ? range : app.settings!.history_range,
  );
  let items: WorkoutSummary[] = $state([]);
  let loaded = $state(false);

  // `range` lives in the query string, and App.svelte keys this screen on
  // path only — switching 1W/1M/1Y re-runs this effect without a remount, so
  // guard against an older request resolving after a newer one.
  $effect(() => {
    const r = current;
    let live = true;
    api
      .workouts(r)
      .then((list) => {
        if (live) {
          items = list;
          loaded = true;
        }
      })
      .catch(toastError);
    return () => {
      live = false;
    };
  });
</script>

<BackBar title="Past workouts" fallback={['workouts']} />
<RangeFilter value={current} onchange={(r) => navigate(['workouts', 'history'], { range: r }, { replace: true })} />

{#if loaded && items.length === 0}
  <p class="muted">No workouts in this period.</p>
{/if}

<div class="stack">
  {#each items as w (w.id)}
    <SessionCard
      kind="workout"
      title={longDate(w.local_date)}
      subtitle={`${plural(w.exercise_count, 'exercise')} · ${plural(w.set_count, 'set')} · ${formatMinutes(w.duration_s)}`}
      chips={w.focus.map(titleCase)}
      onclick={() => navigate(['workouts', String(w.id)])} />
  {/each}
</div>
