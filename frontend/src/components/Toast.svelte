<script lang="ts">
  import { fly } from 'svelte/transition';
  import { dur } from '../lib/motion';
  import { toasts } from '../lib/toast.svelte';
</script>

<div class="toasts" aria-live="polite">
  {#each toasts as t (t.id)}
    <div class="toast {t.kind}" role={t.kind === 'error' ? 'alert' : undefined} transition:fly={{ y: 16, duration: dur(180) }}>{t.text}</div>
  {/each}
</div>

<style>
  .toasts {
    position: fixed; left: 50%; transform: translateX(-50%); z-index: 40;
    /* Below 900px the tab bar sits at the bottom (--tabbar-h tall); above
       that, or on a short landscape screen, it moves to the top or the left,
       so toasts only need to clear the safe area. */
    bottom: calc(var(--tabbar-h) + var(--safe-bottom) + var(--space-3));
    display: grid; gap: var(--space-2); width: min(92vw, 420px); pointer-events: none;
  }
  .toast {
    padding: var(--space-3) var(--space-4); border-radius: var(--radius-md);
    background: var(--color-surface-3); box-shadow: var(--shadow-2); font-size: var(--text-sm);
  }
  .toast.error { background: var(--color-danger); color: var(--color-on-accent); }

  @media (min-width: 900px), (orientation: landscape) and (max-height: 560px) {
    .toasts { bottom: calc(var(--safe-bottom) + var(--space-4)); }
  }
</style>
