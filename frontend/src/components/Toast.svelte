<script lang="ts">
  import { fly } from 'svelte/transition';
  import { dur } from '../lib/motion';
  import { toasts } from '../lib/toast.svelte';
</script>

<div class="toasts" aria-live="polite">
  {#each toasts as t (t.id)}
    <div class="toast {t.kind}" transition:fly={{ y: 16, duration: dur(180) }}>{t.text}</div>
  {/each}
</div>

<style>
  .toasts {
    position: fixed; left: 50%; transform: translateX(-50%); z-index: 40;
    bottom: calc(var(--tabbar-h) + var(--safe-bottom) + var(--space-3));
    display: grid; gap: var(--space-2); width: min(92vw, 420px); pointer-events: none;
  }
  .toast {
    padding: var(--space-3) var(--space-4); border-radius: var(--radius-md);
    background: var(--color-surface-3); box-shadow: var(--shadow-2); font-size: var(--text-sm);
  }
  .toast.error { background: var(--color-danger); color: var(--color-on-accent); }
</style>
