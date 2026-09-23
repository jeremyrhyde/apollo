<script lang="ts">
  import type { Snippet } from 'svelte';
  import Icon from './Icon.svelte';
  import { goBack } from '../lib/router.svelte';

  let { title, fallback, actions }: { title: string; fallback: string[]; actions?: Snippet } = $props();
</script>

<header class="backbar">
  <button class="icon-btn" onclick={() => goBack(fallback)} aria-label="Back">
    <Icon name="chevron-left" size={26} />
  </button>
  <h1>{title}</h1>
  <div class="actions">{@render actions?.()}</div>
</header>

<style>
  .backbar { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: var(--space-1); margin-left: calc(-1 * var(--space-3)); }
  h1 { font-size: var(--text-lg); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .actions { display: flex; }
</style>
