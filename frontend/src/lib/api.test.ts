import { describe, expect, it } from 'vitest';
import { detailOf } from './api';

describe('detailOf', () => {
  it('returns a string detail unchanged', () => {
    expect(detailOf({ detail: 'workout not found' })).toBe('workout not found');
  });

  it('prefixes the field name when the last loc segment is a string', () => {
    const body = { detail: [{ loc: ['body', 'reps'], msg: 'Input should be greater than or equal to 0' }] };
    expect(detailOf(body)).toBe('reps: Input should be greater than or equal to 0');
  });

  it('falls back to the message alone when the last loc segment is not a string', () => {
    const body = { detail: [{ loc: ['body', 0], msg: 'Field required' }] };
    expect(detailOf(body)).toBe('Field required');
  });

  it('returns null for missing or null detail', () => {
    expect(detailOf(null)).toBeNull();
    expect(detailOf({})).toBeNull();
    expect(detailOf({ detail: null })).toBeNull();
  });
});
