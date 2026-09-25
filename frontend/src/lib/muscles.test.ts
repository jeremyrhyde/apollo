import { describe, expect, it } from 'vitest';
import { musclesFor, musclesLabel } from './muscles';
import type { Catalog, ExerciseDef } from './types';

const bench: ExerciseDef = {
  key: 'bench_press', name: 'Bench Press (Barbell)', type: 'weight_reps', groups: ['chest'],
  muscles: { primary: ['chest'], secondary: ['front-deltoids', 'triceps'] },
};
const catalog = {
  metric_types: {}, muscle_groups: ['chest'], selfcare: [], colors: { workout: '', selfcare: '' },
  exercises_by_group: { chest: [bench], triceps: [bench] },
} as Catalog;

describe('muscles', () => {
  it('looks up an exercise by key', () => {
    expect(musclesFor(catalog, 'bench_press')).toEqual(bench.muscles);
    expect(musclesFor(catalog, 'gone')).toBeNull();
  });

  it('labels primary and secondary muscles', () => {
    expect(musclesLabel(bench.muscles)).toBe('Works chest; also front deltoids, triceps');
    expect(musclesLabel({ primary: ['quadriceps', 'gluteal'], secondary: [] })).toBe('Works quadriceps, gluteal');
    expect(musclesLabel({ primary: [], secondary: [] })).toBe('No muscles mapped');
  });
});
