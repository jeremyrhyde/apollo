// Mirrors the backend's schemas/ and core/api.py responses.
// Weights and distances arrive in the user's display units; durations in seconds.

export type FieldName = 'weight' | 'reps' | 'distance' | 'duration';
export type Kind = 'workout' | 'selfcare';
export type CalendarView = 'week' | 'month' | 'year';
export type Range = '1W' | '1M' | '1Y';
export type WeekStart = 'monday' | 'sunday';

export interface ExerciseDef { key: string; name: string; type: string; groups: string[] }
export interface SelfcareTypeDef { key: string; name: string; every_days: number | null }
export interface SelfcareCategoryDef { key: string; name: string; types: SelfcareTypeDef[] }

export interface Catalog {
  metric_types: Record<string, FieldName[]>;
  muscle_groups: string[];
  exercises_by_group: Record<string, ExerciseDef[]>;
  selfcare: SelfcareCategoryDef[];
  colors: Record<Kind, string>;
}

export interface Settings {
  calendar_view: CalendarView;
  week_start: WeekStart;
  weight_unit: 'lb' | 'kg';
  distance_unit: 'mi' | 'km';
  history_range: Range;
}

export interface Health { status: 'ok' | 'degraded'; config_errors: string[] }

export interface WorkoutSet {
  id: number;
  position: number;
  done: boolean;
  weight: number | null;
  reps: number | null;
  distance: number | null;
  duration: number | null;
}

export type SetPatch = Partial<Record<FieldName, number | null>> & { done?: boolean };

export interface WorkoutExercise {
  id: number;
  position: number;
  exercise_key: string;
  name: string;
  metric_type: string;
  fields: FieldName[];
  muscle_groups: string[];
  planned: boolean;
  notes: string | null;
  sets: WorkoutSet[];
}

export interface Workout {
  id: number;
  started_at: string;
  ended_at: string | null;
  local_date: string;
  notes: string | null;
  focus: string[];
  exercises: WorkoutExercise[];
  stale: boolean;
  /** A finished workout open again for editing; never `stale`. */
  reopened: boolean;
}

export interface WorkoutSummary {
  id: number;
  local_date: string;
  started_at: string;
  ended_at: string;
  duration_s: number;
  focus: string[];
  exercise_count: number;
  set_count: number;
}

export interface FinishResult { workout: Workout | null; deleted: boolean }

export interface SelfcareSession {
  id: number;
  category_key: string;
  category_name: string;
  local_date: string;
  performed_at: string;
  notes: string | null;
  types: { key: string; name: string }[];
}

export type DueStatus = 'never' | 'ok' | 'soon' | 'due' | 'overdue' | 'untracked';

export interface DueItem {
  category_key: string;
  type_key: string;
  type_name: string;
  every_days: number | null;
  last_done: string | null;
  next_due: string | null;
  days_since: number | null;
  days_over: number | null;
  ratio: number | null;
  status: DueStatus;
}

export interface CalendarEntry { kind: Kind; id: number; title: string; summary: string; in_progress: boolean }
export interface CalendarDay { date: string; entries: CalendarEntry[] }
export interface LastDone { workout: string | null; selfcare: string | null; types: Record<string, string> }
