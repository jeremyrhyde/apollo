import { describe, expect, it } from 'vitest';
import { PatchQueue } from './patchQueue';

interface Row { weight: number }

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe('PatchQueue', () => {
  it('shows the server copy once the only patch succeeds', async () => {
    const q = new PatchQueue<Row>();
    const shown: Row[] = [];
    await q.run(1, { weight: 100 }, async () => ({ weight: 105 }), (v) => shown.push(v), () => {});
    expect(shown).toEqual([{ weight: 105 }]);
  });

  it('sends patches for one id one at a time, in order', async () => {
    const q = new PatchQueue<Row>();
    const first = deferred<Row>();
    const sent: number[] = [];
    const a = q.run(1, { weight: 100 }, () => (sent.push(1), first.promise), () => {}, () => {});
    const b = q.run(1, { weight: 105 }, async () => (sent.push(2), { weight: 110 }), () => {}, () => {});
    await Promise.resolve();
    expect(sent).toEqual([1]);
    first.resolve({ weight: 105 });
    await Promise.all([a, b]);
    expect(sent).toEqual([1, 2]);
  });

  it('does not show an older response while a newer patch is queued', async () => {
    const q = new PatchQueue<Row>();
    const shown: Row[] = [];
    const show = (v: Row) => shown.push(v);
    await Promise.all([
      q.run(1, { weight: 100 }, async () => ({ weight: 105 }), show, () => {}),
      q.run(1, { weight: 105 }, async () => ({ weight: 110 }), show, () => {}),
    ]);
    expect(shown).toEqual([{ weight: 110 }]);
  });

  it('rolls back to the value before the first patch when everything fails', async () => {
    const q = new PatchQueue<Row>();
    const shown: Row[] = [];
    const errors: unknown[] = [];
    const fail = async (): Promise<Row> => {
      throw new Error('offline');
    };
    await Promise.all([
      q.run(1, { weight: 100 }, fail, (v) => shown.push(v), (e) => errors.push(e)),
      q.run(1, { weight: 105 }, fail, (v) => shown.push(v), (e) => errors.push(e)),
    ]);
    expect(errors).toHaveLength(2);
    expect(shown).toEqual([{ weight: 100 }]);
  });

  it('rolls back to the last saved value when only the newest patch fails', async () => {
    const q = new PatchQueue<Row>();
    const shown: Row[] = [];
    await Promise.all([
      q.run(1, { weight: 100 }, async () => ({ weight: 105 }), (v) => shown.push(v), () => {}),
      q.run(1, { weight: 105 }, () => Promise.reject(new Error('x')), (v) => shown.push(v), () => {}),
    ]);
    expect(shown).toEqual([{ weight: 105 }]);
  });

  it('lets a later success override an earlier failure without a rollback', async () => {
    const q = new PatchQueue<Row>();
    const shown: Row[] = [];
    await Promise.all([
      q.run(1, { weight: 100 }, () => Promise.reject(new Error('x')), (v) => shown.push(v), () => {}),
      q.run(1, { weight: 105 }, async () => ({ weight: 110 }), (v) => shown.push(v), () => {}),
    ]);
    expect(shown).toEqual([{ weight: 110 }]);
  });

  it('keeps ids independent', async () => {
    const q = new PatchQueue<Row>();
    const slow = deferred<Row>();
    const shown: [number, Row][] = [];
    const a = q.run(1, { weight: 1 }, () => slow.promise, (v) => shown.push([1, v]), () => {});
    await q.run(2, { weight: 2 }, async () => ({ weight: 3 }), (v) => shown.push([2, v]), () => {});
    expect(shown).toEqual([[2, { weight: 3 }]]);
    slow.resolve({ weight: 4 });
    await a;
    expect(shown).toEqual([[2, { weight: 3 }], [1, { weight: 4 }]]);
  });

  it('settled() waits for every queued patch', async () => {
    const q = new PatchQueue<Row>();
    const slow = deferred<Row>();
    let done = false;
    void q.run(1, { weight: 1 }, () => slow.promise, () => (done = true), () => {});
    const settled = q.settled().then(() => expect(done).toBe(true));
    slow.resolve({ weight: 2 });
    await settled;
  });

  it('starts from a fresh baseline once a queue drains', async () => {
    const q = new PatchQueue<Row>();
    const shown: Row[] = [];
    await q.run(1, { weight: 100 }, async () => ({ weight: 105 }), () => {}, () => {});
    // The UI now shows 110 (say, reconciled elsewhere); a failing patch rolls back to that, not to 100/105.
    await q.run(1, { weight: 110 }, () => Promise.reject(new Error('x')), (v) => shown.push(v), () => {});
    expect(shown).toEqual([{ weight: 110 }]);
  });
});
