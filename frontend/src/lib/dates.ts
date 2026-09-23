// ISO local dates ('YYYY-MM-DD') as plain strings. All arithmetic is done in
// UTC so the browser's own timezone can never shift a day — the server decides
// what "today" is (GET /api/today).

import type { CalendarView, WeekStart } from './types';

export type ISODate = string;

const DAY_MS = 86_400_000;
const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export function parseISO(d: ISODate): Date {
  const [y, m, day] = d.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, day));
}

export function toISO(d: Date): ISODate {
  return d.toISOString().slice(0, 10);
}

export function addDays(d: ISODate, n: number): ISODate {
  return toISO(new Date(parseISO(d).getTime() + n * DAY_MS));
}

export function diffDays(a: ISODate, b: ISODate): number {
  return Math.round((parseISO(a).getTime() - parseISO(b).getTime()) / DAY_MS);
}

/** Position of `d` in its week: 0 is the configured first day. */
export function weekdayIndex(d: ISODate, weekStart: WeekStart): number {
  const js = parseISO(d).getUTCDay(); // 0 = Sunday
  return weekStart === 'monday' ? (js + 6) % 7 : js;
}

export function startOfWeek(d: ISODate, weekStart: WeekStart): ISODate {
  return addDays(d, -weekdayIndex(d, weekStart));
}

export function startOfMonth(d: ISODate): ISODate {
  return `${d.slice(0, 8)}01`;
}

/** First day of the month `n` months from `d`'s month. */
export function addMonths(d: ISODate, n: number): ISODate {
  const x = parseISO(startOfMonth(d));
  x.setUTCMonth(x.getUTCMonth() + n);
  return toISO(x);
}

export function endOfMonth(d: ISODate): ISODate {
  return addDays(addMonths(d, 1), -1);
}

export function weekDays(anchor: ISODate, weekStart: WeekStart): ISODate[] {
  const start = startOfWeek(anchor, weekStart);
  return Array.from({ length: 7 }, (_, i) => addDays(start, i));
}

/** Whole weeks covering `anchor`'s month. */
export function monthGrid(anchor: ISODate, weekStart: WeekStart): ISODate[][] {
  const last = endOfMonth(anchor);
  const weeks: ISODate[][] = [];
  for (let s = startOfWeek(startOfMonth(anchor), weekStart); s <= last; s = addDays(s, 7)) {
    weeks.push(Array.from({ length: 7 }, (_, i) => addDays(s, i)));
  }
  return weeks;
}

/** `count` week rows, newest (the week containing `anchor`) first. */
export function yearRows(anchor: ISODate, weekStart: WeekStart, count = 53): ISODate[][] {
  const start = startOfWeek(anchor, weekStart);
  return Array.from({ length: count }, (_, r) => {
    const rowStart = addDays(start, -7 * r);
    return Array.from({ length: 7 }, (_, i) => addDays(rowStart, i));
  });
}

export function rangeFor(view: CalendarView, anchor: ISODate, weekStart: WeekStart): { from: ISODate; to: ISODate } {
  if (view === 'week') {
    const days = weekDays(anchor, weekStart);
    return { from: days[0], to: days[6] };
  }
  if (view === 'month') {
    const grid = monthGrid(anchor, weekStart);
    return { from: grid[0][0], to: grid[grid.length - 1][6] };
  }
  const rows = yearRows(anchor, weekStart);
  return { from: rows[rows.length - 1][0], to: rows[0][6] };
}

export function weekdayLabels(weekStart: WeekStart): string[] {
  return weekStart === 'monday' ? [...WEEKDAYS.slice(1), WEEKDAYS[0]] : [...WEEKDAYS];
}

function fmt(d: ISODate, options: Intl.DateTimeFormatOptions): string {
  return parseISO(d).toLocaleDateString('en-US', { timeZone: 'UTC', ...options });
}

export const monthLabel = (d: ISODate) => fmt(d, { month: 'long', year: 'numeric' });
export const monthShort = (d: ISODate) => fmt(d, { month: 'short' });
export const shortDate = (d: ISODate) => fmt(d, { month: 'short', day: 'numeric' });
export const longDate = (d: ISODate) => fmt(d, { weekday: 'long', month: 'long', day: 'numeric' });
export const dayLabel = (d: ISODate) => `${WEEKDAYS[parseISO(d).getUTCDay()]} ${Number(d.slice(8))}`;
