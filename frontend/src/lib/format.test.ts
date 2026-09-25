import { describe, expect, it } from 'vitest';
import { dueText, formatDuration, formatMinutes, heatLevel, parseDecimal, parseDuration, relativeDays, setCells, titleCase } from './format';
import type { WorkoutSet } from './types';
import type { DueItem } from './types';

const due = (over: Partial<DueItem>): DueItem => ({
  category_key: 'skincare', type_key: 'x', type_name: 'X', every_days: 7, last_done: null,
  next_due: null, days_since: null, days_over: null, ratio: null, status: 'ok', ...over,
});

describe('format', () => {
  it('formats durations', () => {
    expect(formatDuration(null)).toBe('');
    expect(formatDuration(59)).toBe('0:59');
    expect(formatDuration(90)).toBe('1:30');
    expect(formatDuration(3723)).toBe('1:02:03');
    expect(formatMinutes(2700)).toBe('45 min');
    expect(formatMinutes(5400)).toBe('1 h 30 min');
  });

  it('parses durations', () => {
    expect(parseDuration('1:30')).toBe(90);
    expect(parseDuration('1:02:03')).toBe(3723);
    expect(parseDuration('45')).toBe(45);
    expect(parseDuration('30', 'minutes')).toBe(1800);
    expect(parseDuration('1,5', 'minutes')).toBe(90);
    expect(parseDuration('')).toBeNull();
    expect(parseDuration('1:75')).toBeNull();
    expect(parseDuration('abc')).toBeNull();
  });

  it('parses comma-tolerant decimals', () => {
    expect(parseDecimal('135')).toBe(135);
    expect(parseDecimal('12,5')).toBe(12.5);
    expect(parseDecimal('12.5')).toBe(12.5);
    expect(parseDecimal('')).toBeNull();
    expect(parseDecimal('-1')).toBeNull();
    expect(parseDecimal('abc')).toBeNull();
  });

  it('describes relative days', () => {
    expect(relativeDays('2026-09-22', '2026-09-22')).toBe('today');
    expect(relativeDays('2026-09-21', '2026-09-22')).toBe('yesterday');
    expect(relativeDays('2026-09-19', '2026-09-22')).toBe('3 days ago');
    expect(relativeDays('2026-09-24', '2026-09-22')).toBe('in 2 days');
  });

  it('describes due items', () => {
    expect(dueText(due({ status: 'never' }))).toBe('never done');
    expect(dueText(due({ status: 'overdue', days_over: 1 }))).toBe('1 day overdue');
    expect(dueText(due({ status: 'overdue', days_over: 4 }))).toBe('4 days overdue');
    expect(dueText(due({ status: 'due', days_over: 0 }))).toBe('due today');
    expect(dueText(due({ status: 'soon', days_over: -1 }))).toBe('due tomorrow');
    expect(dueText(due({ status: 'ok', days_over: -5 }))).toBe('due in 5 days');
    expect(dueText(due({ status: 'untracked', days_since: 2 }))).toBe('last 2 days ago');
    expect(dueText(due({ status: 'untracked', days_since: null }))).toBe('not logged yet');
  });

  it('maps counts to heat levels and title-cases', () => {
    expect([0, 1, 2, 3, 9].map(heatLevel)).toEqual([0, 1, 2, 3, 3]);
    expect(titleCase('chest')).toBe('Chest');
  });

  it('formats a set as cells: reps, then weight/distance, then time', () => {
    const set = (over: Partial<WorkoutSet>): WorkoutSet => ({
      id: 1, position: 1, done: true, weight: null, reps: null, distance: null, duration: null, ...over,
    });
    expect(setCells(set({ weight: 135, reps: 8 }), ['weight', 'reps'], 'lb', 'mi')).toEqual(['8 reps', '135 lb']);
    expect(setCells(set({ reps: 1 }), ['reps'], 'lb', 'mi')).toEqual(['1 rep']);
    expect(setCells(set({ distance: 3.1, duration: 1500 }), ['distance', 'duration'], 'lb', 'mi')).toEqual(['3.1 mi', '25:00']);
    expect(setCells(set({ duration: 60 }), ['duration'], 'kg', 'km')).toEqual(['1:00']);
    expect(setCells(set({ weight: 60 }), ['weight', 'reps'], 'kg', 'km')).toEqual(['—', '60 kg']);
  });
});
