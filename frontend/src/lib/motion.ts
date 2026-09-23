/** Transition duration that collapses to 0 under prefers-reduced-motion. */
export function dur(ms: number): number {
  return typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : ms;
}
