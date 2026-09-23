<script lang="ts">
  import BackBar from '../../components/BackBar.svelte';
  import ConfirmSheet from '../../components/ConfirmSheet.svelte';
  import { api, ApiError } from '../../lib/api';
  import { longDate } from '../../lib/dates';
  import { goBack, navigate } from '../../lib/router.svelte';
  import { toast, toastError } from '../../lib/toast.svelte';
  import type { SelfcareSession } from '../../lib/types';

  let { id }: { id: number } = $props();

  let session: SelfcareSession | null = $state(null);
  let error: string | null = $state(null);
  let confirmDelete = $state(false);
  let busy = $state(false);

  $effect(() => {
    session = null;
    error = null;
    api
      .selfcareSession(id)
      .then((s) => (session = s))
      .catch((e: unknown) => {
        // A 404 means this session no longer exists (deleted from its edit
        // screen, or reached by navigating back to a stale URL) — there's
        // nothing to show or retry, so leave quietly instead of an error.
        if (e instanceof ApiError && e.status === 404) {
          navigate(['selfcare', 'history'], {}, { replace: true });
          return;
        }
        error = e instanceof Error ? e.message : String(e);
        toastError(e);
      });
  });

  async function remove(): Promise<void> {
    busy = true;
    try {
      await api.deleteSelfcare(id);
      toast('Session deleted');
      // Detail is reached from history or a calendar day; both are still valid.
      goBack(['selfcare', 'history']);
    } catch (e) {
      toastError(e);
      busy = false;
    }
  }
</script>

<BackBar title={session ? longDate(session.local_date) : 'Session'} fallback={['selfcare', 'history']} />

{#if error}
  <p class="error">Couldn't load this session: {error}</p>
{:else if session}
  <section class="card">
    <strong>{session.category_name}</strong>
    <div class="chips">{#each session.types as t (t.key)}<span class="chip">{t.name}</span>{/each}</div>
    {#if session.notes}<p class="muted">{session.notes}</p>{/if}
  </section>
  <div class="actions">
    <button class="btn danger" disabled={busy} onclick={() => (confirmDelete = true)}>Delete</button>
    <button class="btn primary" disabled={busy} onclick={() => navigate(['selfcare', 'log', String(id)])}>Edit</button>
  </div>
{/if}

{#if confirmDelete}
  <ConfirmSheet title="Delete this session?" confirmLabel="Delete" danger {busy} onconfirm={remove} oncancel={() => (confirmDelete = false)}>
    <p class="muted">This cannot be undone.</p>
  </ConfirmSheet>
{/if}

<style>
  .error { color: var(--color-danger); }
  .actions { display: grid; grid-template-columns: 1fr 2fr; gap: var(--space-2); }
</style>
