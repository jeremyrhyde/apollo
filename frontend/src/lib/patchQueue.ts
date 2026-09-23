// Optimistic edits to one record, saved in order. The caller shows each change
// immediately, then hands the request to `run`. Requests for the same id are
// sent one at a time, so the server ends on the last edit; only the newest
// request's outcome touches the UI, so an older response (or an older
// failure's rollback) never snaps a field back over a newer edit.
// When the queue for an id drains, the newest response is shown — or, if the
// newest request failed, the last value the server confirmed (a rollback).
// If any request in that burst failed, `fail` is then called once with the
// latest error: a superseded failure still loses its edit, so it's never silent.

export class PatchQueue<T> {
  private tails = new Map<number, Promise<void>>();
  private latest = new Map<number, number>();
  private confirmed = new Map<number, T>();
  private errors = new Map<number, unknown>();

  /**
   * `before` is the record as shown before this edit was applied — the
   * rollback value if nothing in the current burst of edits gets saved.
   */
  run(id: number, before: T, send: () => Promise<T>, show: (value: T) => void, fail: (error: unknown) => void): Promise<void> {
    if (!this.confirmed.has(id)) this.confirmed.set(id, before);
    const seq = (this.latest.get(id) ?? 0) + 1;
    this.latest.set(id, seq);
    const run = (this.tails.get(id) ?? Promise.resolve()).then(async () => {
      try {
        this.confirmed.set(id, await send());
      } catch (e) {
        this.errors.set(id, e);
      }
      if (this.latest.get(id) !== seq) return; // a newer edit is queued; it decides what shows
      const value = this.confirmed.get(id)!;
      const failed = this.errors.has(id);
      const error = this.errors.get(id);
      this.tails.delete(id);
      this.latest.delete(id);
      this.confirmed.delete(id);
      this.errors.delete(id);
      try {
        show(value);
      } finally {
        if (failed) fail(error);
      }
    });
    // The stored tail never rejects: a throwing `show`/`fail` must not wedge
    // later edits to this id or `settled()`. The caller still sees the error.
    this.tails.set(id, run.catch(() => {}));
    return run;
  }

  /** Resolves once every queued request has finished. */
  async settled(): Promise<void> {
    while (this.tails.size) await Promise.all(this.tails.values());
  }
}
