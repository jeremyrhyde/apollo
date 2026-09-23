<script lang="ts">
  import BackBar from '../../components/BackBar.svelte';
  import { api } from '../../lib/api';
  import { longDate } from '../../lib/dates';
  import { navigate } from '../../lib/router.svelte';
  import { toastError } from '../../lib/toast.svelte';
  import type { SelfcareSession } from '../../lib/types';

  let { id }: { id: number } = $props();

  let session: SelfcareSession | null = $state(null);
  let error: string | null = $state(null);

  $effect(() => {
    session = null;
    error = null;
    api
      .selfcareSession(id)
      .then((s) => (session = s))
      .catch((e: unknown) => {
        error = e instanceof Error ? e.message : String(e);
        toastError(e);
      });
  });
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
  <button class="btn primary block" onclick={() => navigate(['selfcare', 'log', String(id)])}>Edit</button>
{/if}

<style>
  .error { color: var(--color-danger); }
</style>
