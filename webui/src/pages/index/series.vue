<script lang="ts" setup>
import type { SeriesItem } from '@/api/series';

definePage({ name: 'Series' });

const { t } = useMyI18n();
const router = useRouter();
const route = useRoute();

const seriesStore = useSeriesStore();

// Detail panel state
const selectedId = computed(() => {
  const id = route.query.id;
  return id ? Number(id) : null;
});

const detail = ref<SeriesItem | null>(null);
const detailLoading = ref(false);

async function loadDetail(id: number) {
  detailLoading.value = true;
  try {
    detail.value = await apiSeries.get(id);
  } finally {
    detailLoading.value = false;
  }
}

function openDetail(id: number) {
  router.push({ path: '/series', query: { id } });
}

function closeDetail() {
  detail.value = null;
  router.push({ path: '/series' });
}

async function patchField(key: keyof import('@/api/series').SeriesPatch, value: string) {
  if (!detail.value) return;
  const patch: import('@/api/series').SeriesPatch = {};
  if (key === 'default_offset') {
    patch[key] = Number(value);
  } else {
    (patch as Record<string, string>)[key] = value;
  }
  detail.value = await apiSeries.patch(detail.value.id, patch);
  seriesStore.updateSeries(detail.value.id, patch);
}

watch(
  selectedId,
  (id) => {
    if (id !== null && !isNaN(id)) {
      loadDetail(id);
    } else {
      detail.value = null;
    }
  },
  { immediate: true }
);

onMounted(() => seriesStore.refresh());
</script>

<template>
  <div class="series-page">
    <!-- List panel -->
    <div class="series-list" :class="[{ 'has-detail': selectedId !== null }]">
      <div v-if="seriesStore.loading" class="loading">
        {{ t('series.loading') }}
      </div>
      <div v-else-if="seriesStore.items.length === 0" class="empty">
        {{ t('series.empty') }}
      </div>
      <table v-else class="series-table">
        <thead>
          <tr>
            <th>{{ t('series.col.title') }}</th>
            <th>{{ t('series.col.season') }}</th>
            <th>{{ t('series.col.year') }}</th>
            <th class="hide-mobile">{{ t('series.col.root') }}</th>
            <th>{{ t('series.col.status') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in seriesStore.items"
            :key="s.id"
            class="series-row" :class="[{ active: selectedId === s.id }]"
            @click="openDetail(s.id)"
          >
            <td>{{ s.canonical_title }}</td>
            <td>{{ s.season }}</td>
            <td>{{ s.year ?? '-' }}</td>
            <td class="mono hide-mobile">{{ s.root_path }}</td>
            <td>
              <span v-if="s.pending_review" class="badge badge-warn">
                {{ t('series.status.pending') }}
              </span>
              <span v-else class="badge badge-ok">
                {{ t('series.status.active') }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Detail panel -->
    <div v-if="selectedId !== null" class="series-detail">
      <div class="detail-header">
        <h3>{{ t('series.detail.title') }}</h3>
        <button class="btn-close" @click="closeDetail">✕</button>
      </div>

      <div v-if="detailLoading" class="loading">{{ t('series.loading') }}</div>

      <template v-else-if="detail">
        <div class="field-group">
          <label>{{ t('series.field.title') }}</label>
          <input
            :value="detail.canonical_title"
            @change="patchField('canonical_title', ($event.target as HTMLInputElement).value)"
          />
        </div>

        <div class="field-group">
          <label>{{ t('series.field.root') }}</label>
          <input
            :value="detail.root_path"
            @change="patchField('root_path', ($event.target as HTMLInputElement).value)"
          />
        </div>

        <div class="field-group">
          <label>{{ t('series.field.filter') }}</label>
          <input
            :value="detail.default_filter ?? ''"
            @change="patchField('default_filter', ($event.target as HTMLInputElement).value)"
          />
        </div>

        <div class="field-group">
          <label>{{ t('series.field.offset') }}</label>
          <input
            type="number"
            :value="detail.default_offset ?? 0"
            @change="patchField('default_offset', ($event.target as HTMLInputElement).value)"
          />
        </div>

        <div class="meta">
          <div><strong>{{ t('series.field.season') }}:</strong> {{ detail.season }}</div>
          <div><strong>{{ t('series.field.year') }}:</strong> {{ detail.year ?? '-' }}</div>
          <img v-if="detail.poster_url" :src="detail.poster_url" class="poster" />
        </div>
      </template>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.series-page {
  display: flex;
  gap: 16px;
  padding: 12px;
  height: 100%;
}

.series-list {
  flex: 1;
  overflow-x: auto;

  &.has-detail {
    max-width: 65%;
  }
}

.series-table {
  width: 100%;
  border-collapse: collapse;

  th,
  td {
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  }

  th {
    font-size: 12px;
    color: #888;
    font-weight: 600;
    text-transform: uppercase;
  }
}

.series-row {
  cursor: pointer;
  transition: background 120ms;

  &:hover {
    background: rgba(0, 0, 0, 0.04);
  }

  &.active {
    background: rgba(66, 153, 225, 0.08);
  }
}

.mono {
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  color: #555;
}

.hide-mobile {
  @media (max-width: 640px) {
    display: none;
  }
}

.badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.badge-ok {
  background: #c6f6d5;
  color: #22543d;
}

.badge-warn {
  background: #fefcbf;
  color: #744210;
}

.loading,
.empty {
  text-align: center;
  padding: 40px;
  color: #888;
}

// Detail panel
.series-detail {
  width: 340px;
  flex-shrink: 0;
  border-left: 1px solid rgba(0, 0, 0, 0.08);
  padding-left: 16px;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;

  h3 {
    margin: 0;
    font-size: 15px;
  }
}

.btn-close {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
  color: #888;
  padding: 2px 6px;

  &:hover {
    color: #333;
  }
}

.field-group {
  margin-bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;

  label {
    font-size: 11px;
    color: #888;
    text-transform: uppercase;
    font-weight: 600;
  }

  input {
    padding: 6px 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 13px;
    width: 100%;
    box-sizing: border-box;

    &:focus {
      outline: none;
      border-color: #4299e1;
    }
  }
}

.meta {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
  color: #555;
}

.poster {
  max-width: 160px;
  border-radius: 4px;
  margin-top: 10px;
}
</style>
