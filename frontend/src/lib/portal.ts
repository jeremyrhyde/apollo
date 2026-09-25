/**
 * Svelte action: move the element to the end of <body>.
 *
 * Sheets and their backdrops are rendered inside `.screen`, whose
 * `view-transition-name` makes it a stacking context — so their z-index can't
 * lift them above the fixed tab bar. Rendering them under <body> fixes that.
 * Svelte still removes the node itself (after any outro), wherever it lives.
 */
export function portal(node: HTMLElement) {
  document.body.appendChild(node);
}
