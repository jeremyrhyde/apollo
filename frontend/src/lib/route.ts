// Hash routes: '#/workouts/42?edit=1'. Everything after '#' stays in the
// browser; the server always serves the same index.html at /.

export interface Route {
  path: string[];
  query: Record<string, string>;
}

export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#\/?/, '');
  const [p, q = ''] = raw.split('?');
  const path = p.split('/').filter(Boolean).map(decodeURIComponent);
  return { path: path.length ? path : ['calendar'], query: Object.fromEntries(new URLSearchParams(q)) };
}

export function buildHash(path: string[], query: Record<string, string | undefined> = {}): string {
  const pairs = Object.entries(query).filter((e): e is [string, string] => e[1] !== undefined && e[1] !== '');
  const qs = new URLSearchParams(pairs).toString();
  return `#/${path.map(encodeURIComponent).join('/')}${qs ? `?${qs}` : ''}`;
}
