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

export function initRouter(): void {
  if (!location.hash) history.replaceState({ idx: 0 }, '', buildHash(['calendar']));
  else history.replaceState({ idx: 0 }, '');
  index = 0;
  router.route = parseHash(location.hash);
  addEventListener('popstate', (event: PopStateEvent) => {
    const idx = typeof event.state?.idx === 'number' ? (event.state.idx as number) : 0;
    const direction = idx < index ? 'back' : 'forward';
    index = idx;
    apply(parseHash(location.hash), direction, true);
  });
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
