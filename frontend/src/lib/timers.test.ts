import { describe, expect, it } from 'vitest';
import { clearSetTimers, setTimerKey } from './timers';

describe('clearSetTimers', () => {
  it('removes the timer key of every given set and nothing else', () => {
    const store = new Map([
      [setTimerKey(1), '100'],
      [setTimerKey(2), '200'],
      [setTimerKey(3), '300'],
      ['apollo:recent', '[]'],
    ]);
    clearSetTimers([{ id: 1 }, { id: 3 }], { removeItem: (k) => void store.delete(k) });
    expect([...store.keys()]).toEqual([setTimerKey(2), 'apollo:recent']);
  });

  it('swallows storage errors', () => {
    const store = { removeItem: () => { throw new Error('denied'); } };
    expect(() => clearSetTimers([{ id: 1 }], store)).not.toThrow();
  });

  it('does nothing without storage', () => {
    expect(() => clearSetTimers([{ id: 1 }])).not.toThrow(); // node: no localStorage
  });
});
