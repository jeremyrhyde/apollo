import { describe, expect, it } from 'vitest';
import { buildHash, parseHash } from './route';

describe('route', () => {
  it('defaults to the calendar', () => {
    expect(parseHash('')).toEqual({ path: ['calendar'], query: {} });
    expect(parseHash('#/')).toEqual({ path: ['calendar'], query: {} });
  });

  it('parses path and query', () => {
    expect(parseHash('#/workouts/42?edit=1')).toEqual({ path: ['workouts', '42'], query: { edit: '1' } });
    expect(parseHash('#/calendar/day/2026-09-22')).toEqual({ path: ['calendar', 'day', '2026-09-22'], query: {} });
  });

  it('builds hashes and drops empty values', () => {
    expect(buildHash(['calendar'], { view: 'month', kind: undefined, date: '' })).toBe('#/calendar?view=month');
    expect(buildHash(['workouts', 'active'])).toBe('#/workouts/active');
  });

  it('round-trips', () => {
    const hash = buildHash(['calendar'], { view: 'year', kind: 'workout' });
    expect(parseHash(hash)).toEqual({ path: ['calendar'], query: { view: 'year', kind: 'workout' } });
  });
});
