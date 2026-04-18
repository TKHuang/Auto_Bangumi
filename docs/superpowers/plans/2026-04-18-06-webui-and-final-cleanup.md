# WebUI Pages + Dashboard Banner + Final Backend Cleanup (Phase 06)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Ship the new `/series`, `/pending-resolution`, `/merge-history` WebUI pages; add the Mikan health dashboard banner; clean up the final backend residue (`_SERIES_MAPPED_KEYS` legacy remap in `BangumiRepository`). After this plan, the bangumi-identity refactor (spec 2026-04-17) is complete end-to-end.

**Architecture:**
- WebUI pages use the existing Vue 3 + vue-router/auto + Pinia + UnoCSS stack. API clients in `webui/src/api/`, stores in `webui/src/store/`, pages in `webui/src/pages/index/`.
- Pages are functional, not highly polished — we match existing page patterns (bangumi.vue, rss.vue) for the layout. Plan 07 (if needed) would polish visuals.
- Dashboard banner polls `/api/v1/health/mikan` every 30s and displays a colored banner for `degraded`/`down` states.
- `_SERIES_MAPPED_KEYS` cleanup: once the new WebUI PATCH paths send series-direct updates (via `/api/v1/series/{id}`), the legacy `/api/v1/bangumi/update/*` path's reliance on the remap is tested and removed.

**Tech Stack:** Vue 3 (Composition API), TypeScript, UnoCSS, Pinia, axios, vue-router/auto, vitest.

**Out of scope:**
- Visual polish beyond matching existing pages
- Rate-limiter degradation indicator UI (low value — request data exists in `/api/v1/health/concurrency`, but no user complaints)
- Test coverage for new WebUI (only smoke tests — full E2E coverage would be Plan 07)

---

## File Map

### Created
- `webui/src/api/series.ts`
- `webui/src/api/merge.ts`
- `webui/src/api/pendingResolution.ts`
- `webui/src/api/health.ts`
- `webui/src/store/series.ts`
- `webui/src/store/mergeHistory.ts`
- `webui/src/store/health.ts`
- `webui/src/pages/index/series.vue`
- `webui/src/pages/index/[id].vue` — series detail (may need subdirectory `series/[id].vue` depending on router setup)
- `webui/src/pages/index/pending-resolution.vue`
- `webui/src/pages/index/merge-history.vue`
- `webui/src/components/dashboard/MikanHealthBanner.vue`

### Modified
- `webui/src/i18n/en.json` — new keys
- `webui/src/i18n/zh-CN.json` — new keys
- `webui/src/components/ab-sidebar.vue` (or wherever nav links live) — add new page links
- `backend/src/module/repositories/bangumi.py` — remove `_SERIES_MAPPED_KEYS` once tests pass without it

---

## Task 1: API clients

**Files:** `webui/src/api/series.ts`, `merge.ts`, `pendingResolution.ts`, `health.ts`

Copy the style of `webui/src/api/bangumi.ts` and `webui/src/api/rss.ts`. Each file exports an `api<Name>` object with async methods.

- [ ] **Step 1: Create `webui/src/api/series.ts`**

```ts
import type { ApiSuccess } from '#/api';

export interface SeriesItem {
  id: number;
  canonical_title: string;
  normalized_title: string;
  season: number;
  cour_part: number | null;
  year: number | null;
  root_path: string;
  poster_url: string | null;
  default_filter: string | null;
  default_offset: number | null;
  pending_review: boolean;
}

export interface SeriesList {
  items: SeriesItem[];
  total: number;
}

export interface SeriesPatch {
  canonical_title?: string;
  root_path?: string;
  default_filter?: string;
  default_offset?: number;
  poster_url?: string;
}

export const apiSeries = {
  async list(limit = 50, offset = 0) {
    const { data } = await axios.get<SeriesList>(
      `api/v1/series/?limit=${limit}&offset=${offset}`
    );
    return data;
  },
  async get(id: number) {
    const { data } = await axios.get<SeriesItem>(`api/v1/series/${id}`);
    return data;
  },
  async patch(id: number, body: SeriesPatch) {
    const { data } = await axios.patch<SeriesItem>(`api/v1/series/${id}`, body);
    return data;
  },
};
```

- [ ] **Step 2: `webui/src/api/merge.ts`**

```ts
export interface MergeHistoryItem {
  id: number;
  winner_bangumi_id: number;
  loser_bangumi_id: number;
  merge_reason: string;
  merged_at: string | null;
  merged_by: string | null;
  undone_at: string | null;
  undone_by: string | null;
}

export const apiMerge = {
  async merge(winnerId: number, loserId: number, reason = 'manual') {
    const { data } = await axios.post<{ history_id: number; winner_id: number; loser_id: number }>(
      'api/v1/bangumi/merge',
      { winner_id: winnerId, loser_id: loserId, reason }
    );
    return data;
  },
  async listHistory(limit = 50, offset = 0) {
    const { data } = await axios.get<{ items: MergeHistoryItem[]; total: number }>(
      `api/v1/merge-history/?limit=${limit}&offset=${offset}`
    );
    return data;
  },
  async undo(historyId: number) {
    const { data } = await axios.post<{ undone: boolean; history_id: number }>(
      `api/v1/merge-history/${historyId}/undo`
    );
    return data;
  },
};
```

- [ ] **Step 3: `webui/src/api/pendingResolution.ts`**

```ts
export interface PendingItem {
  info_hash: string;
  raw_name: string;
  homepage: string | null;
  url: string;
  rss_id: number;
  first_seen_at: string | null;
  attempt_count: number;
  last_error: string | null;
  last_attempt_at: string | null;
}

export interface RetryResult {
  info_hash: string;
  resolved: boolean;
  mikan_bangumi_id?: number;
  mikan_subgroup_id?: number;
  error?: string;
}

export const apiPendingResolution = {
  async list(limit = 50, offset = 0) {
    const { data } = await axios.get<{ items: PendingItem[]; total: number }>(
      `api/v1/pending-resolution/?limit=${limit}&offset=${offset}`
    );
    return data;
  },
  async retry(infoHash: string) {
    const { data } = await axios.post<RetryResult>(
      `api/v1/pending-resolution/${infoHash}/retry`
    );
    return data;
  },
};
```

- [ ] **Step 4: `webui/src/api/health.ts`**

```ts
export interface MikanPendingItem {
  info_hash: string;
  raw_name: string;
  homepage: string | null;
  attempts: number;
  last_error: string | null;
  first_seen_at: string | null;
}

export interface MikanHealth {
  status: 'ok' | 'degraded' | 'down';
  pending_count: number;
  last_success_at: string | null;
  hours_since_last_success: number | null;
  consecutive_failures: number;
  pending_items: MikanPendingItem[];
}

export interface ConcurrencyHealth {
  rss_locks: Array<{ rss_id: number; held: boolean; held_duration_s: number }>;
  rate_limiters: Record<string, { queue: number; in_flight: number; req_per_min: number; error_rate_5m: number; degraded: boolean }>;
}

export const apiHealth = {
  async mikan() {
    const { data } = await axios.get<MikanHealth>('api/v1/health/mikan');
    return data;
  },
  async concurrency() {
    const { data } = await axios.get<ConcurrencyHealth>('api/v1/health/concurrency');
    return data;
  },
};
```

- [ ] **Step 5: Verify imports — `webui/src/api/index.ts` or similar aggregator**

Find how existing clients are exposed (check `webui/src/api/index.ts` if it exists, or the auto-import config in `vite.config.ts`). If there's an index that re-exports `apiBangumi`, `apiRss`, etc., add the new ones.

```bash
grep -rn "apiBangumi\|apiRss" webui/src/ --include="*.ts" --include="*.vue" | head -10
```

If they're auto-imported via `unplugin-auto-import`, the new exports should be picked up automatically — just confirm the config allows it.

- [ ] **Step 6: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi
git add webui/src/api/series.ts webui/src/api/merge.ts \
        webui/src/api/pendingResolution.ts webui/src/api/health.ts
git commit -m "feat(webui): api clients for series/merge/pending-resolution/health"
```

---

## Task 2: Pinia stores

**Files:** `webui/src/store/series.ts`, `mergeHistory.ts`, `health.ts`

- [ ] **Step 1: `webui/src/store/series.ts`**

```ts
import type { SeriesItem, SeriesPatch } from '#/series';

export const useSeriesStore = defineStore('series', () => {
  const items = ref<SeriesItem[]>([]);
  const total = ref(0);
  const loading = ref(false);

  async function refresh(limit = 100, offset = 0) {
    loading.value = true;
    try {
      const data = await apiSeries.list(limit, offset);
      items.value = data.items;
      total.value = data.total;
    } finally {
      loading.value = false;
    }
  }

  async function updateSeries(id: number, patch: SeriesPatch) {
    const updated = await apiSeries.patch(id, patch);
    const idx = items.value.findIndex((s) => s.id === id);
    if (idx >= 0) items.value[idx] = updated;
    return updated;
  }

  return { items, total, loading, refresh, updateSeries };
});
```

- [ ] **Step 2: `webui/src/store/mergeHistory.ts`**

```ts
import type { MergeHistoryItem } from '#/merge';

export const useMergeHistoryStore = defineStore('mergeHistory', () => {
  const items = ref<MergeHistoryItem[]>([]);
  const total = ref(0);

  async function refresh() {
    const data = await apiMerge.listHistory(100, 0);
    items.value = data.items;
    total.value = data.total;
  }

  async function undo(id: number) {
    await apiMerge.undo(id);
    await refresh();
  }

  return { items, total, refresh, undo };
});
```

- [ ] **Step 3: `webui/src/store/health.ts`**

```ts
import type { MikanHealth } from '#/health';

export const useHealthStore = defineStore('health', () => {
  const mikan = ref<MikanHealth | null>(null);
  let pollHandle: number | null = null;

  async function refresh() {
    try {
      mikan.value = await apiHealth.mikan();
    } catch {
      // keep last known state on error
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
```

- [ ] **Step 4: Commit**

```
git commit -m "feat(webui): pinia stores for series/mergeHistory/health"
```

---

## Task 3: Series list page

**File:** `webui/src/pages/index/series.vue`

Match the layout pattern from `webui/src/pages/index/bangumi.vue`. Minimal scope: list series, show status badges, clicking a row navigates to `/series/:id`.

- [ ] **Step 1: Build page**

```vue
<script lang="ts" setup>
definePage({ name: 'Series' });

const seriesStore = useSeriesStore();
const router = useRouter();

onMounted(() => seriesStore.refresh());

function openDetail(id: number) {
  router.push(`/series/${id}`);
}
</script>

<template>
  <div class="series-page">
    <div v-if="seriesStore.loading" class="loading">Loading...</div>
    <div v-else-if="seriesStore.items.length === 0" class="empty">
      {{ $t('series.empty') }}
    </div>
    <table v-else class="series-table">
      <thead>
        <tr>
          <th>{{ $t('series.col.title') }}</th>
          <th>{{ $t('series.col.season') }}</th>
          <th>{{ $t('series.col.year') }}</th>
          <th>{{ $t('series.col.root') }}</th>
          <th>{{ $t('series.col.status') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="s in seriesStore.items"
          :key="s.id"
          class="series-row"
          @click="openDetail(s.id)"
        >
          <td>{{ s.canonical_title }}</td>
          <td>{{ s.season }}</td>
          <td>{{ s.year ?? '-' }}</td>
          <td class="mono">{{ s.root_path }}</td>
          <td>
            <span v-if="s.pending_review" class="badge badge-warn">
              {{ $t('series.status.pending') }}
            </span>
            <span v-else class="badge badge-ok">
              {{ $t('series.status.active') }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style lang="scss" scoped>
.series-page { padding: 12px; }
.series-table { width: 100%; border-collapse: collapse; }
.series-table th, .series-table td { padding: 8px 12px; text-align: left; }
.series-row { cursor: pointer; transition: background 120ms; }
.series-row:hover { background: rgba(0, 0, 0, 0.04); }
.mono { font-family: var(--font-mono, monospace); font-size: 12px; }
.badge { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.badge-ok { background: #c6f6d5; color: #22543d; }
.badge-warn { background: #fefcbf; color: #744210; }
.loading, .empty { text-align: center; padding: 40px; color: #888; }
</style>
```

- [ ] **Step 2: Commit**

```
git commit -m "feat(webui): /series list page"
```

---

## Task 4: Series detail page

**File:** `webui/src/pages/index/series/[id].vue` (or `webui/src/pages/index/series-[id].vue` — match the router convention)

Check how dynamic routes work in this app:

```bash
cat webui/vite.config.ts | grep -A 5 "router\|pages"
find webui/src/pages -type d
```

Use whichever convention exists. If no dynamic route examples, use the standard vue-router/auto `[param].vue` nested under a `series/` directory.

- [ ] **Step 1: Build page**

```vue
<script lang="ts" setup>
definePage({ name: 'SeriesDetail' });

const route = useRoute();
const seriesId = computed(() => Number(route.params.id));

const seriesStore = useSeriesStore();
const series = ref<SeriesItem | null>(null);

async function load() {
  series.value = await apiSeries.get(seriesId.value);
}

async function patchField<K extends keyof SeriesPatch>(key: K, value: SeriesPatch[K]) {
  if (!series.value) return;
  const patch = { [key]: value } as SeriesPatch;
  series.value = await apiSeries.patch(seriesId.value, patch);
}

onMounted(load);
watch(seriesId, load);
</script>

<template>
  <div v-if="series" class="series-detail">
    <h2>{{ series.canonical_title }}</h2>

    <div class="field-group">
      <label>{{ $t('series.field.title') }}</label>
      <input
        :value="series.canonical_title"
        @change="patchField('canonical_title', ($event.target as HTMLInputElement).value)"
      />
    </div>

    <div class="field-group">
      <label>{{ $t('series.field.root') }}</label>
      <input
        :value="series.root_path"
        @change="patchField('root_path', ($event.target as HTMLInputElement).value)"
      />
    </div>

    <div class="field-group">
      <label>{{ $t('series.field.filter') }}</label>
      <input
        :value="series.default_filter ?? ''"
        @change="patchField('default_filter', ($event.target as HTMLInputElement).value)"
      />
    </div>

    <div class="meta">
      <div><strong>{{ $t('series.field.season') }}:</strong> {{ series.season }}</div>
      <div><strong>{{ $t('series.field.year') }}:</strong> {{ series.year ?? '-' }}</div>
      <div v-if="series.poster_url">
        <img :src="series.poster_url" :alt="series.canonical_title" class="poster" />
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.series-detail { padding: 16px; max-width: 600px; }
.field-group { margin-bottom: 12px; display: flex; flex-direction: column; gap: 4px; }
.field-group label { font-size: 12px; color: #666; }
.field-group input { padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; }
.meta { margin-top: 20px; display: flex; flex-direction: column; gap: 8px; }
.poster { max-width: 200px; border-radius: 4px; margin-top: 10px; }
</style>
```

- [ ] **Step 2: Commit**

```
git commit -m "feat(webui): /series/:id detail + inline edit"
```

---

## Task 5: Pending-resolution page

**File:** `webui/src/pages/index/pending-resolution.vue`

- [ ] **Step 1**

```vue
<script lang="ts" setup>
definePage({ name: 'PendingResolution' });

const items = ref<PendingItem[]>([]);
const loading = ref(false);

async function refresh() {
  loading.value = true;
  try {
    const data = await apiPendingResolution.list(200, 0);
    items.value = data.items;
  } finally {
    loading.value = false;
  }
}

async function retryOne(infoHash: string) {
  await apiPendingResolution.retry(infoHash);
  await refresh();
}

onMounted(refresh);
// Refresh every 30s
const timer = window.setInterval(refresh, 30_000);
onBeforeUnmount(() => window.clearInterval(timer));
</script>

<template>
  <div class="pending-page">
    <div class="toolbar">
      <button class="btn" :disabled="loading" @click="refresh">
        {{ $t('common.refresh') }}
      </button>
      <span class="count">{{ items.length }} {{ $t('pending.items') }}</span>
    </div>

    <div v-if="items.length === 0" class="empty">
      {{ $t('pending.empty') }}
    </div>

    <table v-else class="pending-table">
      <thead>
        <tr>
          <th>{{ $t('pending.col.name') }}</th>
          <th>{{ $t('pending.col.attempts') }}</th>
          <th>{{ $t('pending.col.last_error') }}</th>
          <th>{{ $t('pending.col.first_seen') }}</th>
          <th>{{ $t('common.actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.info_hash">
          <td class="name">{{ item.raw_name }}</td>
          <td>{{ item.attempt_count }}</td>
          <td class="err">{{ item.last_error || '-' }}</td>
          <td>{{ item.first_seen_at ?? '-' }}</td>
          <td>
            <button class="btn btn-sm" @click="retryOne(item.info_hash)">
              {{ $t('pending.retry') }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style lang="scss" scoped>
.pending-page { padding: 12px; }
.toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.count { color: #666; }
.pending-table { width: 100%; border-collapse: collapse; }
.pending-table th, .pending-table td { padding: 8px 12px; text-align: left; }
.name { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.err { color: #c05621; font-size: 12px; max-width: 300px; }
.empty { text-align: center; padding: 40px; color: #888; }
.btn { padding: 4px 12px; border: 1px solid #ccc; border-radius: 4px; background: #fff; cursor: pointer; }
.btn-sm { padding: 2px 8px; font-size: 12px; }
</style>
```

- [ ] **Step 2: Commit**

```
git commit -m "feat(webui): /pending-resolution inspection + manual retry"
```

---

## Task 6: Merge-history page

**File:** `webui/src/pages/index/merge-history.vue`

```vue
<script lang="ts" setup>
definePage({ name: 'MergeHistory' });

const store = useMergeHistoryStore();
onMounted(() => store.refresh());

async function undoMerge(id: number) {
  if (!confirm('Undo this merge?')) return;
  await store.undo(id);
}
</script>

<template>
  <div class="merge-page">
    <div class="toolbar">
      <button class="btn" @click="store.refresh()">{{ $t('common.refresh') }}</button>
      <span class="count">{{ store.total }} {{ $t('merge.records') }}</span>
    </div>

    <div v-if="store.items.length === 0" class="empty">
      {{ $t('merge.empty') }}
    </div>

    <table v-else class="merge-table">
      <thead>
        <tr>
          <th>{{ $t('merge.col.when') }}</th>
          <th>{{ $t('merge.col.winner') }}</th>
          <th>{{ $t('merge.col.loser') }}</th>
          <th>{{ $t('merge.col.reason') }}</th>
          <th>{{ $t('merge.col.by') }}</th>
          <th>{{ $t('common.actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="h in store.items" :key="h.id">
          <td>{{ h.merged_at }}</td>
          <td>{{ h.winner_bangumi_id }}</td>
          <td>{{ h.loser_bangumi_id }}</td>
          <td>{{ h.merge_reason }}</td>
          <td>{{ h.merged_by ?? '-' }}</td>
          <td>
            <button
              v-if="!h.undone_at"
              class="btn btn-sm"
              @click="undoMerge(h.id)"
            >
              {{ $t('merge.undo') }}
            </button>
            <span v-else class="undone">
              {{ $t('merge.undone') }} ({{ h.undone_by }})
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style lang="scss" scoped>
.merge-page { padding: 12px; }
.toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.count { color: #666; }
.merge-table { width: 100%; border-collapse: collapse; }
.merge-table th, .merge-table td { padding: 8px 12px; text-align: left; }
.empty { text-align: center; padding: 40px; color: #888; }
.undone { color: #718096; font-size: 12px; font-style: italic; }
.btn { padding: 4px 12px; border: 1px solid #ccc; border-radius: 4px; background: #fff; cursor: pointer; }
.btn-sm { padding: 2px 8px; font-size: 12px; }
</style>
```

Commit: `git commit -m "feat(webui): /merge-history list + undo"`

---

## Task 7: Dashboard MikanHealthBanner

**File:** `webui/src/components/dashboard/MikanHealthBanner.vue`

```vue
<script lang="ts" setup>
const healthStore = useHealthStore();

onMounted(() => healthStore.startPolling(30_000));
onBeforeUnmount(() => healthStore.stopPolling());

const bannerClass = computed(() => {
  const s = healthStore.mikan?.status;
  if (s === 'down') return 'banner banner-down';
  if (s === 'degraded') return 'banner banner-warn';
  return '';
});

const show = computed(() =>
  healthStore.mikan && healthStore.mikan.status !== 'ok'
);
</script>

<template>
  <div v-if="show" :class="bannerClass">
    <strong v-if="healthStore.mikan?.status === 'down'">
      ⚠️ {{ $t('health.down_title') }}
    </strong>
    <strong v-else>
      ⚠️ {{ $t('health.degraded_title') }}
    </strong>
    <span>
      {{ $t('health.pending_count', { n: healthStore.mikan!.pending_count }) }}
    </span>
    <RouterLink to="/pending-resolution" class="banner-link">
      {{ $t('health.view_details') }}
    </RouterLink>
  </div>
</template>

<style lang="scss" scoped>
.banner { padding: 10px 16px; border-radius: 6px; margin-bottom: 12px; display: flex; gap: 12px; align-items: center; }
.banner-warn { background: #fefcbf; color: #744210; border-left: 4px solid #d69e2e; }
.banner-down { background: #fed7d7; color: #822727; border-left: 4px solid #c53030; }
.banner-link { margin-left: auto; color: inherit; text-decoration: underline; }
</style>
```

Wire it into the main layout — add `<MikanHealthBanner />` at the top of `webui/src/pages/index.vue` (or whichever parent layout holds the main content):

```vue
<div class="layout-content">
  <ab-page-title :title="title" />
  <MikanHealthBanner />
  <!-- rest -->
</div>
```

Commit: `git commit -m "feat(webui): dashboard banner for Mikan health status"`

---

## Task 8: i18n updates

**Files:** `webui/src/i18n/en.json`, `webui/src/i18n/zh-CN.json`

Add keys referenced by the pages. Keep the structure parallel across locales.

- [ ] **Step 1: Draft en.json additions**

```json
{
  "series": {
    "empty": "No series yet.",
    "col": {
      "title": "Title",
      "season": "Season",
      "year": "Year",
      "root": "Root Path",
      "status": "Status"
    },
    "status": {
      "active": "Active",
      "pending": "Pending Review"
    },
    "field": {
      "title": "Canonical Title",
      "root": "Root Path",
      "filter": "Default Filter",
      "season": "Season",
      "year": "Year"
    }
  },
  "pending": {
    "empty": "No pending items.",
    "items": "pending",
    "col": {
      "name": "Torrent Name",
      "attempts": "Attempts",
      "last_error": "Last Error",
      "first_seen": "First Seen"
    },
    "retry": "Retry"
  },
  "merge": {
    "records": "merge records",
    "empty": "No merge history.",
    "col": {
      "when": "Merged At",
      "winner": "Winner ID",
      "loser": "Loser ID",
      "reason": "Reason",
      "by": "By"
    },
    "undo": "Undo",
    "undone": "Undone"
  },
  "health": {
    "down_title": "Mikan unreachable",
    "degraded_title": "Mikan degraded",
    "pending_count": "{n} pending items",
    "view_details": "View details"
  },
  "common": {
    "refresh": "Refresh",
    "actions": "Actions"
  }
}
```

- [ ] **Step 2: zh-CN.json analogs**

```json
{
  "series": {
    "empty": "暂无 Series。",
    "col": {
      "title": "标题",
      "season": "季数",
      "year": "年份",
      "root": "根路径",
      "status": "状态"
    },
    "status": {
      "active": "正常",
      "pending": "待审核"
    },
    "field": {
      "title": "规范标题",
      "root": "根路径",
      "filter": "默认过滤",
      "season": "季数",
      "year": "年份"
    }
  },
  "pending": {
    "empty": "无待解析项目。",
    "items": "待处理",
    "col": {
      "name": "种子名",
      "attempts": "尝试次数",
      "last_error": "最后错误",
      "first_seen": "首次出现"
    },
    "retry": "重试"
  },
  "merge": {
    "records": "合并记录",
    "empty": "无合并历史。",
    "col": {
      "when": "合并时间",
      "winner": "保留 ID",
      "loser": "移除 ID",
      "reason": "原因",
      "by": "操作者"
    },
    "undo": "撤销",
    "undone": "已撤销"
  },
  "health": {
    "down_title": "Mikan 不可达",
    "degraded_title": "Mikan 降级",
    "pending_count": "{n} 个待处理项目",
    "view_details": "查看详情"
  },
  "common": {
    "refresh": "刷新",
    "actions": "操作"
  }
}
```

Merge these into the existing JSON (don't overwrite other keys). If `common` already exists, merge at that level.

- [ ] **Step 3: Commit**

```
git commit -m "feat(webui): i18n keys for series/pending/merge/health"
```

---

## Task 9: Sidebar + nav

**File:** `webui/src/components/ab-sidebar.vue` (or wherever navigation items are defined)

- [ ] **Step 1: Find the nav structure**

```bash
grep -rn "Bangumi\|RSS\|Calendar" webui/src/components/ --include="*.vue" | head -10
```

Locate the file that defines the sidebar menu items.

- [ ] **Step 2: Add three new items**

- `Series` → route name `Series`, path `/series`
- `Pending Resolution` → route name `PendingResolution`, path `/pending-resolution`
- `Merge History` → route name `MergeHistory`, path `/merge-history`

Match the existing item shape (probably an array of `{ to, label, icon }` objects).

For icons, reuse any existing icon naming pattern. If icons are required and no clear equivalent exists, use simple Unicode: 📺, ⏳, 🔀.

- [ ] **Step 3: Commit**

```
git commit -m "feat(webui): sidebar nav for new pages"
```

---

## Task 10: WebUI build sanity

**Files:** None — verification only.

- [ ] **Step 1: Build**

```bash
cd /Users/tk/ws/Auto_Bangumi/webui
pnpm install  # if dependencies changed
pnpm build 2>&1 | tail -20
```

Expected: clean build. No unresolved imports, no type errors. If the project uses `pnpm lint`, also run that:

```bash
pnpm lint 2>&1 | tail -20
```

Fix any issues inline. Common issues:
- Auto-import config needs `defineStore` / `ref` / `computed` imports — if the autoimport config doesn't include them, either add explicit imports or add them to the autoimport config.
- Missing type `ApiSuccess` → import from correct path (check existing files for the pattern)

- [ ] **Step 2: Commit (only if fixes were made)**

```
git commit -m "fix(webui): build/lint warnings from new code"
```

---

## Task 11: Backend cleanup — `_SERIES_MAPPED_KEYS`

**Files:** `backend/src/module/repositories/bangumi.py`

Plan 05 Task 11 left `_SERIES_MAPPED_KEYS` / `_DROPPED_INTERMEDIATES` frozensets in `_apply_update_dict` to serve the legacy `/api/v1/bangumi/update/{id}` path that receives old-schema dicts. With Plan 06 adding a direct series PATCH endpoint and the WebUI calling it for title/season/year edits, the legacy path no longer needs the remap.

But: there may still be non-WebUI callers (tests, internal services) that rely on the remap. Survey before deleting.

- [ ] **Step 1: Inventory callers of `BangumiRepository.update()` / `update_simple()`**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
grep -rn "\.update(\|\.update_simple(" src/ --include="*.py" | grep -v "^.*#" | head -30
```

For each hit, check what dict shape is being passed. If any caller still passes `official_title`, `season`, `year`, `poster_link`, `save_path`:
- Production caller: rewrite to PATCH through `/api/v1/series/{id}` OR call `SeriesRepository` directly.
- Test caller: update to match the new shape or call the series API instead.

- [ ] **Step 2: Remove the remap if callers are clean**

In `repositories/bangumi.py`:
- Delete `_SERIES_MAPPED_KEYS` frozenset
- Delete `_DROPPED_INTERMEDIATES` frozenset
- In `_apply_update_dict`: remove the branches that handle those keys
- At that point, `_apply_update_dict` degenerates to a direct `for k, v: setattr(bangumi, k, v)` — inline it back into `update()` / `update_simple()` and delete the helper

If callers aren't clean, leave a simplified form + a focused `# TODO` and skip the deletion. Don't force this if it'd require reworking lots of tests.

- [ ] **Step 3: Run tests**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
uv run pytest -q 2>&1 | tail -5
```

Full sweep should stay green (1677+). If it drops, revert the deletion — callers still need the remap.

- [ ] **Step 4: Commit**

```
git commit -m "refactor: drop _SERIES_MAPPED_KEYS legacy remap (callers now send series-direct)"
```

If the cleanup didn't land cleanly, skip this commit entirely.

---

## Task 12: Final sanity pass

**Files:** None — verification only.

- [ ] **Step 1: Backend**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
uv run pytest -q 2>&1 | tail -5
uv run alembic check
```

Expected: 1677+ passed / 0 failed, "No new upgrade operations detected."

- [ ] **Step 2: WebUI**

```bash
cd /Users/tk/ws/Auto_Bangumi/webui
pnpm build 2>&1 | tail -10
pnpm test 2>&1 | tail -10  # if any existing vitest suites
```

Expected: clean build. Any pre-existing failing tests OK (not our scope).

- [ ] **Step 3: Manual API surface**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
uv run python -c "
from main import app
for route in app.routes:
    if hasattr(route, 'path') and '/api/v1' in route.path:
        print(route.methods, route.path)
" | sort
```

Spot-check: all expected endpoints present.

---

## Self-Review Checklist (controller runs after Task 12)

1. **WebUI pages present**
   - `/series`, `/series/:id`, `/pending-resolution`, `/merge-history` all navigable from sidebar

2. **Dashboard banner wired**
   - Mounts on layout, polls health endpoint, shows on degraded/down

3. **API clients + stores**
   - Four new API files, three new stores, all typed

4. **i18n parity**
   - Every new `$t('...')` key exists in both en.json and zh-CN.json

5. **Out-of-scope (deferred to Plan 07 if ever)**
   - Visual polish
   - E2E tests for new WebUI pages
   - Rate-limiter degradation indicator UI

6. **Backend cleanup**
   - `_SERIES_MAPPED_KEYS` removed, or if not, a clear reason in the code comment
