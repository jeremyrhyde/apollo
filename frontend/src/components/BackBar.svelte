<script lang="ts">
  import type { Snippet } from 'svelte';
  import Icon from './Icon.svelte';
  import { goBack } from '../lib/router.svelte';

  interface Props {
    title: string;
    fallback: string[];
    actions?: Snippet;
    /** Replaces the default back navigation (the handler navigates itself). */
    onback?: () => void | Promise<void>;
  }

  let { title, fallback, actions, onback }: Props = $props();
</script>

<header class="backbar">
  <button class="icon-btn" onclick={() => (onback ? onback() : goBack(fallback))} aria-label="Back">
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
