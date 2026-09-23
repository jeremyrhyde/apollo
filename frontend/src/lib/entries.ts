import { navigate } from './router.svelte';
import type { CalendarEntry } from './types';

/** Open the detail screen for a calendar entry. */
export function openEntry(entry: CalendarEntry): void {
  if (entry.kind === 'workout') {
    navigate(entry.in_progress ? ['workouts', 'active'] : ['workouts', String(entry.id)]);
  } else {
    navigate(['selfcare', String(entry.id)]);
  }
}
