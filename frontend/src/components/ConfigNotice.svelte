<script lang="ts">
  import { app } from '../lib/app.svelte';
  import { navigate } from '../lib/router.svelte';
</script>

<!-- The server loaded with YAML errors (GET /api/health); Settings lists them. -->
{#if app.configErrors.length}
  <button class="banner warn notice" onclick={() => navigate(['settings'])}>Config error — see Settings</button>
{/if}

<style>
  .notice { width: 100%; min-height: var(--tap-min); cursor: pointer; color: var(--color-text); text-align: left; }
</style>
