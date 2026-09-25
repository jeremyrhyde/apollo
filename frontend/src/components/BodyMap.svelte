<script lang="ts">
  // Front and back body outlines with the exercise's muscles filled in:
  // primary in the workout colour, secondary in a tint of it.
  import { anteriorData, posteriorData, VIEWBOX } from '../lib/bodymap';
  import { musclesLabel } from '../lib/muscles';
  import type { Muscle } from '../lib/types';

  interface Props {
    primary: Muscle[];
    secondary: Muscle[];
    /** Height in px; each view's width follows the viewBox aspect. */
    size?: number;
    /** Hide from screen readers where the exercise name sits beside it. */
    ariaHidden?: boolean;
  }

  let { primary, secondary, size = 36, ariaHidden = false }: Props = $props();

  const width = $derived((size * VIEWBOX.width) / VIEWBOX.height);

  function tone(muscle: string): string {
    if ((primary as string[]).includes(muscle)) return 'primary';
    if ((secondary as string[]).includes(muscle)) return 'secondary';
    return '';
  }
</script>

<span
  class="bodymap"
  role={ariaHidden ? undefined : 'img'}
  aria-label={ariaHidden ? undefined : musclesLabel({ primary, secondary })}
  aria-hidden={ariaHidden || undefined}
>
  {#each [anteriorData, posteriorData] as view, v (v)}
    <svg {width} height={size} viewBox={`0 0 ${VIEWBOX.width} ${VIEWBOX.height}`} aria-hidden="true">
      {#each view as region (region.muscle)}
        {#each region.svgPoints as points (points)}<polygon {points} class={tone(region.muscle)} />{/each}
      {/each}
    </svg>
  {/each}
</span>

<style>
  .bodymap { display: inline-flex; flex-shrink: 0; gap: var(--space-1); }
  polygon { fill: var(--color-body); }
  polygon.primary { fill: var(--color-workout); }
  polygon.secondary { fill: color-mix(in srgb, var(--color-workout) 45%, var(--color-body)); }
</style>
