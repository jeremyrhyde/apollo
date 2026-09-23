<script lang="ts">
  import type { Range } from '../lib/types';

  let { value, onchange }: { value: Range; onchange: (range: Range) => void } = $props();

  const RANGES: { key: Range; label: string }[] = [
    { key: '1W', label: '1 week' },
    { key: '1M', label: '1 month' },
    { key: '1Y', label: '1 year' },
  ];
</script>

<div class="segmented" role="radiogroup" aria-label="Time range">
  {#each RANGES as r (r.key)}
    <button role="radio" aria-checked={value === r.key} class:on={value === r.key} onclick={() => onchange(r.key)}>
      {r.label}
    </button>
  {/each}
</div>
