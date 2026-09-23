// App-wide state loaded once at boot: catalog (YAML), settings (DB), and the
// server's "today" (timezone + day-start hour applied).

import { api, ApiError } from './api';
import type { Catalog, Kind, Settings } from './types';

interface AppState {
  ready: boolean;
  error: string | null;
  catalog: Catalog | null;
  settings: Settings | null;
  today: string;
  configErrors: string[];
}

export const app: AppState = $state({
  ready: false, error: null, catalog: null, settings: null, today: '', configErrors: [],
});

function applyColors(colors: Record<Kind, string>): void {
  const root = document.documentElement.style;
  root.setProperty('--color-workout', colors.workout);
  root.setProperty('--color-selfcare', colors.selfcare);
}

export async function loadApp(): Promise<void> {
  try {
    const [catalog, settings, today, health] = await Promise.all([
      api.catalog(), api.settings(), api.today(), api.health(),
    ]);
    app.catalog = catalog;
    app.settings = settings;
    app.today = today.today;
    app.configErrors = health.config_errors;
    applyColors(catalog.colors);
    app.ready = true;
  } catch (e) {
    app.error = e instanceof ApiError && e.status === 0
      ? 'Could not reach the Apollo server.'
      : `Could not reach the Apollo server (${(e as Error).message}).`;
  }
}

/** Called when the page becomes visible again — the day may have rolled over. */
export async function refreshToday(): Promise<void> {
  try {
    app.today = (await api.today()).today;
  } catch {
    /* offline; keep the old value */
  }
}

export async function updateSetting<K extends keyof Settings>(key: K, value: Settings[K]): Promise<void> {
  await api.setSetting(key, value);
  if (app.settings) app.settings[key] = value;
}
