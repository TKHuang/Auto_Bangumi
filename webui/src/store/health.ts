import type { MikanHealth } from '../api/health';

export const useHealthStore = defineStore('health', () => {
  const mikan = ref<MikanHealth | null>(null);
  let pollHandle: number | null = null;

  async function refresh() {
    try {
      mikan.value = await apiHealth.mikan();
    } catch {
      // keep last-known on error
    }
  }

  function startPolling(intervalMs = 30_000) {
    stopPolling();
    refresh();
    pollHandle = window.setInterval(refresh, intervalMs);
  }

  function stopPolling() {
    if (pollHandle !== null) {
      window.clearInterval(pollHandle);
      pollHandle = null;
    }
  }

  return { mikan, refresh, startPolling, stopPolling };
});
