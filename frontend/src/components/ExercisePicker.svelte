<script lang="ts">
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import ConfigNotice from './ConfigNotice.svelte';
  import Icon from './Icon.svelte';
  import { titleCase } from '../lib/format';
  import { dur } from '../lib/motion';
  import { portal } from '../lib/portal';
  import { readRecent, rememberRecent } from '../lib/recent';
  import type { Catalog, ExerciseDef } from '../lib/types';

  interface Props { catalog: Catalog; onpick: (key: string) => void; onclose: () => void }

  let { catalog, onpick, onclose }: Props = $props();

  let search = $state('');
  let sheetEl: HTMLDivElement | undefined = $state();

  onMount(() => sheetEl?.focus());

  function onkeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') onclose();
  }

  const all: ExerciseDef[] = $derived.by(() => {
    const seen = new Map<string, ExerciseDef>();
    for (const list of Object.values(catalog.exercises_by_group)) for (const e of list) seen.set(e.key, e);
    return [...seen.values()];
  });
  const needle = $derived(search.trim().toLowerCase());
  // Recent keys no longer in the catalog (removed from exercises.yaml) drop out here.
  const recent: ExerciseDef[] = $derived(
    needle ? [] : readRecent().map((k) => all.find((e) => e.key === k)).filter((e): e is ExerciseDef => !!e),
  );
  const groups = $derived(
    Object.entries(catalog.exercises_by_group)
      .map(([group, list]) => [group, list.filter((e) => !needle || e.name.toLowerCase().includes(needle))] as const)
      .filter(([, list]) => list.length > 0),
  );

  function pick(key: string): void {
    rememberRecent(key);
    onpick(key);
  }
</script>

<svelte:window {onkeydown} />

<button class="backdrop" use:portal aria-label="Close" onclick={onclose} transition:fade={{ duration: dur(150) }}></button>
<div
  class="sheet"
  use:portal
  role="dialog"
  aria-modal="true"
  aria-label="Add exercise"
  tabindex="-1"
  bind:this={sheetEl}
  transition:fly={{ y: 400, duration: dur(220) }}
>
  <div class="top">
    <div class="head">
      <h2>Add exercise</h2>
      <button class="icon-btn" aria-label="Close" onclick={onclose}><Icon name="x" /></button>
    </div>
    <label class="search">
      <Icon name="search" size={18} />
      <input class="input" type="search" placeholder="Search exercises" aria-label="Search exercises" bind:value={search} />
    </label>
  </div>

  <ConfigNotice />

  {#if recent.length}
    <p class="section-title">Recent</p>
    <div class="list">
      {#each recent as e (e.key)}<button class="item" onclick={() => pick(e.key)}>{e.name}</button>{/each}
    </div>
  {/if}

  {#each groups as [group, list] (group)}
    <p class="section-title">{titleCase(group)}</p>
    <div class="list">
      {#each list as e (e.key)}<button class="item" onclick={() => pick(e.key)}>{e.name}</button>{/each}
    </div>
  {:else}
    {#if all.length === 0 && !needle}
      <p class="muted">No exercises configured — add them to config/exercises.yaml.</p>
    {:else}
      <p class="muted">No exercise matches “{search}”. Add it to config/exercises.yaml.</p>
    {/if}
  {/each}
</div>

<style>
  /* Title + search stay put while the list scrolls. The sheet scrolls inside
     its own padding, so pull the bar up over that padding to pin it flush. */
  .top {
    position: sticky; top: calc(-1 * var(--space-4)); z-index: 1;
    display: grid; gap: var(--space-3);
    margin-top: calc(-1 * var(--space-4)); padding: var(--space-4) 0 var(--space-2);
    background: var(--color-surface);
  }
  .head { display: flex; justify-content: space-between; align-items: center; }
  .search { display: flex; align-items: center; gap: var(--space-2); color: var(--color-text-muted); }
  .search .input { flex: 1; min-width: 0; }
  .list { display: grid; gap: 1px; background: var(--color-border-soft); border-radius: var(--radius-md); overflow: hidden; }
  .item { min-height: var(--tap-min); padding: 0 var(--space-4); text-align: left; background: var(--color-surface-2); border: 0; cursor: pointer; color: var(--color-text); }
  .item:active { background: var(--color-surface-3); }
</style>
