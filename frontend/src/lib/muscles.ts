// Muscle-map lookups: which muscles an exercise works, from the catalog.

import type { Catalog, Muscles } from './types';

/** The exercise's muscles, or null when its key is no longer in the catalog. */
export function musclesFor(catalog: Catalog, exerciseKey: string): Muscles | null {
  for (const list of Object.values(catalog.exercises_by_group)) {
    const def = list.find((e) => e.key === exerciseKey);
    if (def) return def.muscles;
  }
  return null;
}

const names = (list: string[]): string => list.map((m) => m.replace('-', ' ')).join(', ');

/** "Works chest; also front deltoids, triceps" — the body map's aria-label. */
export function musclesLabel(m: Muscles): string {
  if (!m.primary.length) return 'No muscles mapped';
  return `Works ${names(m.primary)}${m.secondary.length ? `; also ${names(m.secondary)}` : ''}`;
}
