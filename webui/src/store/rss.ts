import type { RSS } from '#/rss';
import {
  getPendingReviewSources,
  getPendingReviewTotal,
} from '@/components/layout/pending-review';

export const useRSSStore = defineStore('rss', () => {
  const rss = ref<RSS[]>([]);
  const selectedRSS = ref<number[]>([]);
  const pendingCounts = ref<Record<number, number>>({});
  let pendingRefresh: Promise<void> | null = null;
  let pendingRefreshRequested = false;
  const pendingCountConcurrency = 4;

  const pendingReviewSources = computed(() =>
    getPendingReviewSources(rss.value, pendingCounts.value)
  );
  const pendingReviewTotal = computed(() =>
    getPendingReviewTotal(pendingReviewSources.value)
  );

  async function getAll() {
    const res = await apiRSS.get();

    function sort(arr: RSS[]) {
      return arr.sort((a, b) => b.id - a.id);
    }

    const enabled = sort(res.filter((e) => e.enabled));
    const disabled = sort(res.filter((e) => !e.enabled));

    rss.value = [...enabled, ...disabled];
  }

  async function updatePendingCounts() {
    const snapshot = [...rss.value];
    const results: Array<{ id: number; count: number }> = [];

    for (
      let index = 0;
      index < snapshot.length;
      index += pendingCountConcurrency
    ) {
      const batch = snapshot.slice(index, index + pendingCountConcurrency);
      results.push(
        ...(await Promise.all(
          batch.map(async (item) => {
            try {
              const res = await apiRSS.getPendingCount(item.id);
              return { id: item.id, count: res.pending_count };
            } catch {
              return { id: item.id, count: pendingCounts.value[item.id] ?? 0 };
            }
          })
        ))
      );
    }

    const currentIds = new Set(rss.value.map(({ id }) => id));
    pendingCounts.value = Object.fromEntries(
      results
        .filter(({ id }) => currentIds.has(id))
        .map(({ id, count }) => [id, count])
    );

    if (
      snapshot.length !== currentIds.size ||
      snapshot.some(({ id }) => !currentIds.has(id))
    ) {
      pendingRefreshRequested = true;
    }
  }

  async function refreshPendingCounts(force = false) {
    if (pendingRefresh) {
      if (force) pendingRefreshRequested = true;
      return pendingRefresh;
    }

    pendingRefresh = (async () => {
      do {
        pendingRefreshRequested = false;
        await updatePendingCounts();
      } while (pendingRefreshRequested);
    })();

    try {
      await pendingRefresh;
    } finally {
      pendingRefresh = null;
    }
  }

  const opts = {
    showMessage: true,
    async onSuccess() {
      selectedRSS.value = [];
      try {
        await getAll();
        await refreshPendingCounts(true);
      } catch (error) {
        console.error('[RSS] Failed to refresh after mutation:', error);
      }
    },
  };

  const { execute: updateRSS } = useApi(apiRSS.update, opts);
  const { execute: disableRSS } = useApi(apiRSS.disableMany, opts);
  const { execute: deleteRSS } = useApi(apiRSS.deleteMany, opts);
  const { execute: enableRSS } = useApi(apiRSS.enableMany, opts);
  const { execute: refreshRSS } = useApi(apiRSS.refresh, opts);

  const disableSelected = () => disableRSS(selectedRSS.value);
  const deleteSelected = (file = false) => deleteRSS(selectedRSS.value, file);
  const enableSelected = () => enableRSS(selectedRSS.value);

  return {
    rss,
    selectedRSS,
    pendingCounts,
    pendingReviewSources,
    pendingReviewTotal,

    getAll,
    refreshPendingCounts,
    updateRSS,
    disableRSS,
    deleteRSS,
    enableRSS,
    refreshRSS,
    disableSelected,
    deleteSelected,
    enableSelected,
  };
});
