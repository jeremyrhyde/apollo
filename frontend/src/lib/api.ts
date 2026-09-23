import type {
  CalendarDay, Catalog, DueItem, FinishResult, Health, Kind, LastDone, Range,
  SelfcareSession, SetPatch, Settings, Workout, WorkoutExercise, WorkoutSet, WorkoutSummary,
} from './types';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export function detailOf(body: unknown): string | null {
  if (!body || typeof body !== 'object' || !('detail' in body)) return null;
  const detail = (body as { detail: unknown }).detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const item = d as { loc?: unknown; msg?: string };
        const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : undefined;
        const msg = item.msg ?? String(d);
        return typeof field === 'string' ? `${field}: ${msg}` : msg;
      })
      .join('; ');
  }
  return null;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    // Network failure (offline, server down): the browser's TypeError text
    // isn't meaningful to a user, so surface a readable message instead.
    throw new ApiError(0, "Can't reach the server");
  }
  if (res.status === 204) return undefined as T;
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, detailOf(data) ?? (res.statusText || `HTTP ${res.status}`));
  return data as T;
}

const q = (params: Record<string, string | undefined>) => {
  const pairs = Object.entries(params).filter((e): e is [string, string] => e[1] !== undefined);
  return pairs.length ? `?${new URLSearchParams(pairs)}` : '';
};

export const api = {
  health: () => request<Health>('GET', '/health'),
  today: () => request<{ today: string }>('GET', '/today'),
  catalog: () => request<Catalog>('GET', '/catalog'),
  settings: () => request<Settings>('GET', '/settings'),
  setSetting: (key: keyof Settings, value: string) => request<void>('PUT', `/settings/${key}`, { value }),

  startWorkout: (planned: string[] = []) => request<Workout>('POST', '/workouts', { planned_exercises: planned }),
  openWorkout: () => request<Workout | null>('GET', '/workouts/open'),
  workouts: (range: Range) => request<WorkoutSummary[]>('GET', `/workouts${q({ range })}`),
  workout: (id: number) => request<Workout>('GET', `/workouts/${id}`),
  addExercise: (id: number, key: string) =>
    request<WorkoutExercise>('POST', `/workouts/${id}/exercises`, { exercise_key: key }),
  removeExercise: (id: number, weId: number) => request<void>('DELETE', `/workouts/${id}/exercises/${weId}`),
  addSet: (id: number, weId: number) => request<WorkoutSet>('POST', `/workouts/${id}/exercises/${weId}/sets`),
  updateSet: (setId: number, patch: SetPatch) => request<WorkoutSet>('PATCH', `/sets/${setId}`, patch),
  deleteSet: (setId: number) => request<void>('DELETE', `/sets/${setId}`),
  finishWorkout: (id: number, atLastActivity = false) =>
    request<FinishResult>('POST', `/workouts/${id}/finish${q({ end_at_last_activity: atLastActivity ? 'true' : undefined })}`),
  reopenWorkout: (id: number) => request<Workout>('POST', `/workouts/${id}/reopen`),
  deleteWorkout: (id: number) => request<void>('DELETE', `/workouts/${id}`),

  logSelfcare: (body: { category: string; types: string[]; date?: string; notes?: string | null }) =>
    request<SelfcareSession>('POST', '/selfcare/sessions', body),
  selfcareSessions: (range: Range, category?: string) =>
    request<SelfcareSession[]>('GET', `/selfcare/sessions${q({ range, category })}`),
  selfcareSession: (id: number) => request<SelfcareSession>('GET', `/selfcare/sessions/${id}`),
  updateSelfcare: (id: number, body: { types?: string[]; date?: string; notes?: string | null }) =>
    request<SelfcareSession>('PATCH', `/selfcare/sessions/${id}`, body),
  deleteSelfcare: (id: number) => request<void>('DELETE', `/selfcare/sessions/${id}`),
  due: () => request<DueItem[]>('GET', '/selfcare/due'),

  calendar: (from: string, to: string, kinds: Kind[]) =>
    request<CalendarDay[]>('GET', `/calendar${q({ from, to, kinds: kinds.join(',') })}`),
  lastDone: () => request<LastDone>('GET', '/calendar/last-done'),
};
