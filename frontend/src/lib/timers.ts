// SetRow mirrors a running set timer to localStorage under one key per set id.
// Those keys must go once the sets can no longer be timed (workout finished,
// discarded or deleted, exercise removed) — ids get reused.

type KeyStore = Pick<Storage, 'removeItem'>;

export function setTimerKey(setId: number): string {
  return `apollo:set-timer:${setId}`;
}

export function clearSetTimers(sets: { id: number }[], store?: KeyStore): void {
  try {
    const target = store ?? localStorage;
    for (const s of sets) target.removeItem(setTimerKey(s.id));
  } catch {
    /* storage unavailable */
  }
}
