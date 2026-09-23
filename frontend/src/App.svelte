<script lang="ts">
  import { onMount } from 'svelte';
  import TabBar from './components/TabBar.svelte';
  import Toasts from './components/Toast.svelte';
  import { app, loadApp, refreshToday } from './lib/app.svelte';
  import { initRouter, router } from './lib/router.svelte';
  import CalendarScreen from './screens/calendar/CalendarScreen.svelte';
  import DayScreen from './screens/calendar/DayScreen.svelte';
  import ActiveWorkout from './screens/workouts/ActiveWorkout.svelte';
  import WorkoutDetail from './screens/workouts/WorkoutDetail.svelte';
  import WorkoutHistory from './screens/workouts/WorkoutHistory.svelte';
  import WorkoutsHub from './screens/workouts/WorkoutsHub.svelte';
  import SelfcareDetail from './screens/selfcare/SelfcareDetail.svelte';
  import SelfcareHistory from './screens/selfcare/SelfcareHistory.svelte';
  import SelfcareHub from './screens/selfcare/SelfcareHub.svelte';
  import SelfcareLog from './screens/selfcare/SelfcareLog.svelte';
  import SettingsScreen from './screens/settings/SettingsScreen.svelte';

  onMount(() => {
    const stopRouter = initRouter();
    void loadApp();
    const onVisible = () => {
      if (document.visibilityState === 'visible') void refreshToday();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      document.removeEventListener('visibilitychange', onVisible);
      stopRouter();
    };
  });

  const path = $derived(router.route.path);
  const query = $derived(router.route.query);
  const tab = $derived(path[0] ?? 'calendar');
  const screenKey = $derived(path.join('/'));

  function numeric(segment: string | undefined): number | null {
    return segment !== undefined && /^\d+$/.test(segment) ? Number(segment) : null;
  }
</script>

<main class="screen">
  {#if !app.ready}
    <div class="center-state">
      {#if app.error}
        <p>{app.error}</p>
        <button class="btn" onclick={() => location.reload()}>Retry</button>
      {:else}
        <p class="muted">Loading…</p>
      {/if}
    </div>
  {:else}
    {#key screenKey}
      {#if tab === 'calendar' && path[1] === 'day' && path[2]}
        <DayScreen date={path[2]} kind={query.kind ?? 'all'} />
      {:else if tab === 'workouts' && path[1] === 'active'}
        <ActiveWorkout editing={query.edit === '1'} />
      {:else if tab === 'workouts' && path[1] === 'history'}
        <WorkoutHistory range={query.range} />
      {:else if tab === 'workouts' && numeric(path[1]) !== null}
        <WorkoutDetail id={numeric(path[1])!} />
      {:else if tab === 'workouts'}
        <WorkoutsHub />
      {:else if tab === 'selfcare' && path[1] === 'log'}
        <SelfcareLog id={numeric(path[2]) ?? undefined} initialDate={query.date} />
      {:else if tab === 'selfcare' && path[1] === 'history'}
        <SelfcareHistory range={query.range} />
      {:else if tab === 'selfcare' && numeric(path[1]) !== null}
        <SelfcareDetail id={numeric(path[1])!} />
      {:else if tab === 'selfcare'}
        <SelfcareHub />
      {:else if tab === 'settings'}
        <SettingsScreen />
      {:else}
        <CalendarScreen {query} />
      {/if}
    {/key}
  {/if}
</main>
<TabBar active={tab} />
<Toasts />
