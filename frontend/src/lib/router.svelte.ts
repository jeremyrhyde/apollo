// History-aware hash router. Each navigation pushes a history entry carrying
// its index, so popstate can tell back from forward (for the slide direction).
// Screen changes run inside document.startViewTransition where supported
// (iOS 18+, Chromium) and just swap otherwise.

import { tick } from 'svelte';
import { buildHash, parseHash, type Route } from './route';

export const router: { route: Route } = $state({ route: parseHash(location.hash) });

let index = 0;

type ViewTransitionDoc = Document & { startViewTransition?: (cb: () => Promise<void>) => unknown };

function apply(route: Route, direction: 'forward' | 'back', animate: boolean): void {
  const doc = document as ViewTransitionDoc;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!animate || reduce || !doc.startViewTransition) {
    router.route = route;
    return;
  }
  document.documentElement.dataset.nav = direction;
  doc.startViewTransition(async () => {
    router.route = route;
    await tick();
  });
}

// Safari's edge-swipe back/forward gesture sets this on the PopStateEvent it
// dispatches, since it already animated the transition itself.
type SwipePopStateEvent = PopStateEvent & { hasUAVisualTransition?: boolean };

export function initRouter(): () => void {
  // A reload keeps the tab's history.state, so an existing numeric idx means
  // we're re-entering an existing history entry, not starting a fresh one —
  // leave it alone so back/forward still work.
  const existingIdx = typeof history.state?.idx === 'number' ? (history.state.idx as number) : null;
  index = existingIdx ?? 0;
  if (!location.hash) {
    history.replaceState({ idx: index }, '', buildHash(['calendar']));
  } else if (existingIdx === null) {
    history.replaceState({ idx: index }, '');
  }
  router.route = parseHash(location.hash);
  const onPopState = (event: SwipePopStateEvent) => {
    const idx = typeof event.state?.idx === 'number' ? (event.state.idx as number) : 0;
    const direction = idx < index ? 'back' : 'forward';
    index = idx;
    const swiped = 'hasUAVisualTransition' in event && event.hasUAVisualTransition === true;
    apply(parseHash(location.hash), direction, !swiped);
  };
  addEventListener('popstate', onPopState);
  return () => removeEventListener('popstate', onPopState);
}

export function navigate(
  path: string[],
  query: Record<string, string | undefined> = {},
  opts: { replace?: boolean } = {},
): void {
  const hash = buildHash(path, query);
  if (opts.replace) {
    history.replaceState({ idx: index }, '', hash);
  } else {
    index += 1;
    history.pushState({ idx: index }, '', hash);
  }
  apply(parseHash(hash), 'forward', !opts.replace);
}

/** In-app back: browser history when there is some, else a sensible parent. */
export function goBack(fallback: string[]): void {
  if (index > 0) history.back();
  else navigate(fallback, {}, { replace: true });
}
