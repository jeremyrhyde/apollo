<script lang="ts">
  import Icon from './Icon.svelte';
  import { navigate, router } from '../lib/router.svelte';

  let { active }: { active: string } = $props();

  const TABS = [
    { key: 'calendar', label: 'Calendar', icon: 'calendar' },
    { key: 'workouts', label: 'Workouts', icon: 'dumbbell' },
    { key: 'selfcare', label: 'Self-care', icon: 'sparkles' },
    { key: 'settings', label: 'Settings', icon: 'sliders' },
  ];

  function select(key: string): void {
    const alreadyOnTab = active === key;
    // Already at this tab's root: no-op, don't push a duplicate entry.
    if (alreadyOnTab && router.route.path.length === 1) return;
    // Returning to a tab's root from one of its subroutes replaces rather
    // than pushes, since it's a reset within the section, not a new place.
    navigate([key], {}, { replace: alreadyOnTab });
  }
</script>

<nav class="tabbar" aria-label="Sections">
  {#each TABS as tab (tab.key)}
    <button
      class:active={active === tab.key}
      aria-current={active === tab.key ? 'page' : undefined}
      onclick={() => select(tab.key)}>
      <Icon name={tab.icon} size={22} />
      <span>{tab.label}</span>
    </button>
  {/each}
</nav>

<style>
  .tabbar {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 20;
    display: flex; background: var(--color-surface);
    border-top: 1px solid var(--color-border);
    padding: 0 var(--safe-right) var(--safe-bottom) var(--safe-left);
    view-transition-name: tabbar;
  }
  button {
    flex: 1; min-height: var(--tabbar-h);
    display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;
    background: none; border: 0; color: var(--color-text-muted); font-size: var(--text-xs); cursor: pointer;
  }
  .active { color: var(--color-accent); }
  @media (min-width: 900px) {
    .tabbar {
      top: 0; bottom: auto; justify-content: center; border-top: 0;
      border-bottom: 1px solid var(--color-border); padding: var(--safe-top) 0 0;
    }
    button { flex: 0 0 150px; flex-direction: row; gap: var(--space-2); font-size: var(--text-sm); }
  }
</style>
