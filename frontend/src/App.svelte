<script lang="ts">
  import { onMount } from 'svelte';
  import TabBar from './components/TabBar.svelte';
  import Toasts from './components/Toast.svelte';
  import { app, loadApp, refreshToday } from './lib/app.svelte';
  import { isValidISODate } from './lib/dates';
  import { initRouter, navigate, router } from './lib/router.svelte';
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

  // Every recognized route resolves to exactly one of these; anything else
  // (a typo'd tab, a non-numeric detail id, a truncated /calendar/day) is
  // `null` and gets redirected to the calendar tab below, so the address bar
  // never shows a route with nothing behind it.
  type Screen =
    | { kind: 'calendar' }
    | { kind: 'day'; date: string }
    | { kind: 'workouts-hub' }
    | { kind: 'workouts-active' }
    | { kind: 'workouts-history' }
    | { kind: 'workout-detail'; id: number }
    | { kind: 'selfcare-hub' }
    | { kind: 'selfcare-log'; id?: number }
    | { kind: 'selfcare-history' }
    | { kind: 'selfcare-detail'; id: number }
    | { kind: 'settings' };

  function matchRoute(currentTab: string, segments: string[]): Screen | null {
    if (currentTab === 'calendar') {
      if (segments.length === 1) return { kind: 'calendar' };
      if (segments.length === 3 && segments[1] === 'day' && isValidISODate(segments[2])) {
        return { kind: 'day', date: segments[2] };
      }
      return null;
    }
    if (currentTab === 'workouts') {
      if (segments.length === 1) return { kind: 'workouts-hub' };
      if (segments.length === 2 && segments[1] === 'active') return { kind: 'workouts-active' };
      if (segments.length === 2 && segments[1] === 'history') return { kind: 'workouts-history' };
      if (segments.length === 2) {
        const id = numeric(segments[1]);
        if (id !== null) return { kind: 'workout-detail', id };
      }
      return null;
    }
    if (currentTab === 'selfcare') {
      if (segments.length === 1) return { kind: 'selfcare-hub' };
      if (segments[1] === 'log') {
        if (segments.length === 2) return { kind: 'selfcare-log' };
        if (segments.length === 3) {
          const id = numeric(segments[2]);
          return id !== null ? { kind: 'selfcare-log', id } : null;
        }
        return null;
      }
      if (segments.length === 2 && segments[1] === 'history') return { kind: 'selfcare-history' };
      if (segments.length === 2) {
        const id = numeric(segments[1]);
        if (id !== null) return { kind: 'selfcare-detail', id };
      }
      return null;
    }
    if (currentTab === 'settings') {
      return segments.length === 1 ? { kind: 'settings' } : null;
    }
    return null;
  }

  const screen = $derived(matchRoute(tab, path));

  $effect(() => {
    if (app.ready && !screen) navigate(['calendar'], {}, { replace: true });
  });
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
      {#if screen?.kind === 'calendar'}
        <CalendarScreen {query} />
      {:else if screen?.kind === 'day'}
        <DayScreen date={screen.date} kind={query.kind ?? 'all'} />
      {:else if screen?.kind === 'workouts-hub'}
        <WorkoutsHub />
      {:else if screen?.kind === 'workouts-active'}
        <ActiveWorkout />
      {:else if screen?.kind === 'workouts-history'}
        <WorkoutHistory range={query.range} />
      {:else if screen?.kind === 'workout-detail'}
        <WorkoutDetail id={screen.id} />
      {:else if screen?.kind === 'selfcare-hub'}
        <SelfcareHub />
      {:else if screen?.kind === 'selfcare-log'}
        <SelfcareLog id={screen.id} initialDate={query.date} />
      {:else if screen?.kind === 'selfcare-history'}
        <SelfcareHistory range={query.range} />
      {:else if screen?.kind === 'selfcare-detail'}
        <SelfcareDetail id={screen.id} />
      {:else if screen?.kind === 'settings'}
        <SettingsScreen />
      {/if}
    {/key}
  {/if}
</main>
<TabBar active={tab} />
<Toasts />
