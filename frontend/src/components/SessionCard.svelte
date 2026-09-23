<script lang="ts">
  import Icon from './Icon.svelte';
  import type { Kind } from '../lib/types';

  interface Props {
    kind: Kind;
    title: string;
    subtitle?: string;
    meta?: string;
    chips?: string[];
    onclick: () => void;
  }

  let { kind, title, subtitle, meta, chips = [], onclick }: Props = $props();
</script>

<button class="session {kind}" {onclick}>
  <span class="bar" aria-hidden="true"></span>
  <span class="body">
    <span class="top">
      <strong>{title}</strong>
      {#if meta}<span class="meta">{meta}</span>{/if}
    </span>
    {#if subtitle}<span class="sub">{subtitle}</span>{/if}
    {#if chips.length}
      <span class="chips">{#each chips as c (c)}<span class="chip">{c}</span>{/each}</span>
    {/if}
  </span>
  <Icon name="chevron-right" />
</button>

<style>
  .session {
    display: grid; grid-template-columns: 4px 1fr auto; align-items: center; gap: var(--space-3);
    width: 100%; min-height: var(--tap-min); padding: var(--space-3) var(--space-3) var(--space-3) 0;
    background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md);
    text-align: left; cursor: pointer; color: var(--color-text-muted); overflow: hidden;
  }
  .bar { align-self: stretch; background: var(--color-text-faint); }
  .workout .bar { background: var(--color-workout); }
  .selfcare .bar { background: var(--color-selfcare); }
  .body { display: grid; gap: var(--space-1); min-width: 0; }
  .top { display: flex; justify-content: space-between; gap: var(--space-2); color: var(--color-text); }
  .meta, .sub { font-size: var(--text-sm); color: var(--color-text-muted); }
</style>
