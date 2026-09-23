import { describe, expect, it } from 'vitest';
import {
  addDays, addMonths, dayLabel, diffDays, isValidISODate, longDate, monthGrid, monthLabel,
  rangeFor, shortDate, startOfWeek, weekdayIndex, weekdayLabels, yearRows,
} from './dates';

// 2026-09-22 is a Tuesday; 2026-09-01 a Tuesday; 2026-09-30 a Wednesday.
describe('dates', () => {
  it('does day arithmetic across months and years', () => {
    expect(addDays('2026-09-30', 1)).toBe('2026-10-01');
    expect(addDays('2026-01-01', -1)).toBe('2025-12-31');
    expect(diffDays('2026-09-22', '2026-09-20')).toBe(2);
  });

  it('knows the week start', () => {
    expect(weekdayIndex('2026-09-22', 'monday')).toBe(1);
    expect(weekdayIndex('2026-09-22', 'sunday')).toBe(2);
    expect(startOfWeek('2026-09-22', 'monday')).toBe('2026-09-21');
    expect(startOfWeek('2026-09-22', 'sunday')).toBe('2026-09-20');
    expect(weekdayLabels('sunday')[0]).toBe('Sun');
  });

  it('adds months from the first of the month', () => {
    expect(addMonths('2026-12-15', 1)).toBe('2027-01-01');
    expect(addMonths('2026-01-31', -1)).toBe('2025-12-01');
  });

  it('builds a month grid of whole weeks', () => {
    const g = monthGrid('2026-09-22', 'monday');
    expect(g.map((w) => w[0])).toEqual(['2026-08-31', '2026-09-07', '2026-09-14', '2026-09-21', '2026-09-28']);
    expect(g[4][6]).toBe('2026-10-04');
    expect(monthGrid('2026-09-22', 'sunday')[0][0]).toBe('2026-08-30');
  });

  it('builds 53 year rows, newest first', () => {
    const rows = yearRows('2026-09-22', 'monday');
    expect(rows).toHaveLength(53);
    expect(rows[0][0]).toBe('2026-09-21');
    expect(rows[52][0]).toBe('2025-09-22');
  });

  it('computes fetch ranges per view', () => {
    expect(rangeFor('week', '2026-09-22', 'monday')).toEqual({ from: '2026-09-21', to: '2026-09-27' });
    expect(rangeFor('month', '2026-09-22', 'monday')).toEqual({ from: '2026-08-31', to: '2026-10-04' });
    expect(rangeFor('year', '2026-09-22', 'monday')).toEqual({ from: '2025-09-22', to: '2026-09-27' });
  });

  it('formats labels', () => {
    expect(monthLabel('2026-09-22')).toBe('September 2026');
    expect(shortDate('2026-09-22')).toBe('Sep 22');
    expect(longDate('2026-09-22')).toBe('Tuesday, September 22');
    expect(dayLabel('2026-09-22')).toBe('Tue 22');
  });

  it('validates YYYY-MM-DD dates', () => {
    expect(isValidISODate('2026-09-22')).toBe(true);
    expect(isValidISODate('2024-02-29')).toBe(true); // leap day
    expect(isValidISODate('2024-02-30')).toBe(false); // rolls over to March
    expect(isValidISODate('2026-13-01')).toBe(false);
    expect(isValidISODate('2026-9-22')).toBe(false);
    expect(isValidISODate('abc')).toBe(false);
  });
});
