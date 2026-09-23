import { diffDays, type ISODate } from './dates';
import type { DueItem } from './types';

export function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`;
}

export function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Seconds → "m:ss" or "h:mm:ss"; null → "". */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '';
  const t = Math.max(0, Math.round(seconds));
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = String(t % 60).padStart(2, '0');
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`;
}

export function formatMinutes(seconds: number): string {
  const m = Math.round(seconds / 60);
  return m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`;
}

/**
 * "m:ss" / "h:mm:ss" → seconds. A bare number is seconds, or minutes when
 * `plain` is 'minutes' (runs are entered in minutes, planks in seconds).
 */
export function parseDuration(text: string, plain: 'seconds' | 'minutes' = 'seconds'): number | null {
  const t = text.trim();
  if (t === '') return null;
  if (/^\d+(\.\d+)?$/.test(t)) {
    const n = Number(t);
    return Math.round(plain === 'minutes' ? n * 60 : n);
  }
  const m = /^(?:(\d+):)?(\d{1,2}):(\d{2})$/.exec(t);
  if (!m) return null;
  const [, h, mm, ss] = m;
  if (Number(ss) > 59 || (h !== undefined && Number(mm) > 59)) return null;
  return Number(h ?? 0) * 3600 + Number(mm) * 60 + Number(ss);
}

function ago(days: number): string {
  if (days === 0) return 'today';
  if (days === 1) return 'yesterday';
  return `${days} days ago`;
}

export function relativeDays(date: ISODate, today: ISODate): string {
  const d = diffDays(today, date);
  if (d === -1) return 'tomorrow';
  return d >= 0 ? ago(d) : `in ${-d} days`;
}

export function dueText(item: DueItem): string {
  switch (item.status) {
    case 'never':
      return 'never done';
    case 'untracked':
      return item.days_since === null ? 'not logged yet' : `last ${ago(item.days_since)}`;
    case 'overdue':
      return `${plural(item.days_over ?? 0, 'day')} overdue`;
    case 'due':
      return 'due today';
    default: {
      const inDays = -(item.days_over ?? 0);
      return inDays === 1 ? 'due tomorrow' : `due in ${inDays} days`;
    }
  }
}

/** Sessions on a day → heatmap shade level 0–3. */
export function heatLevel(count: number): 0 | 1 | 2 | 3 {
  if (count <= 0) return 0;
  if (count === 1) return 1;
  if (count === 2) return 2;
  return 3;
}
