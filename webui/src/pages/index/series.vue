<script lang="ts" setup>
import type { SeriesItem, SeriesPatch } from '@/api/series';

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

// Editable form — decoupled from `detail` so typo+blur doesn't mutate
// anything until the user explicitly clicks Save.
interface FormState {
  canonical_title: string;
  root_path: string;
  default_filter: string;
  default_offset: number;
}

const form = ref<FormState | null>(null);
const saving = ref(false);
const saveError = ref<string | null>(null);
const showRootConfirm = ref(false);

function snapshotForm(src: SeriesItem): FormState {
  return {
    canonical_title: src.canonical_title,
    root_path: src.root_path,
    default_filter: src.default_filter ?? '',
    default_offset: src.default_offset ?? 0,
  };
}

async function loadDetail(id: number) {
  detailLoading.value = true;
  saveError.value = null;
  try {
    detail.value = await apiSeries.get(id);
    form.value = snapshotForm(detail.value);
  } finally {
    detailLoading.value = false;
  }
}

function openDetail(id: number) {
  router.push({ path: '/series', query: { id } });
}

function closeDetail() {
  detail.value = null;
  form.value = null;
  saveError.value = null;
  router.push({ path: '/series' });
}

const isDirty = computed(() => {
  if (!detail.value || !form.value) return false;
  return (
    form.value.canonical_title !== detail.value.canonical_title ||
    form.value.root_path !== detail.value.root_path ||
    form.value.default_filter !== (detail.value.default_filter ?? '') ||
    form.value.default_offset !== (detail.value.default_offset ?? 0)
  );
});

const rootChanged = computed(() => {
  if (!detail.value || !form.value) return false;
  return form.value.root_path !== detail.value.root_path;
});

function buildPatch(): SeriesPatch {
  if (!detail.value || !form.value) return {};
  const patch: SeriesPatch = {};
  if (form.value.canonical_title !== detail.value.canonical_title) {
    patch.canonical_title = form.value.canonical_title;
  }
  if (form.value.root_path !== detail.value.root_path) {
    patch.root_path = form.value.root_path;
  }
  if (form.value.default_filter !== (detail.value.default_filter ?? '')) {
    patch.default_filter = form.value.default_filter;
  }
  if (form.value.default_offset !== (detail.value.default_offset ?? 0)) {
    patch.default_offset = form.value.default_offset;
  }
  return patch;
}

function cancelEdit() {
  if (!detail.value) return;
  form.value = snapshotForm(detail.value);
  saveError.value = null;
}

async function commitSave() {
  if (!detail.value || !form.value) return;
  const patch = buildPatch();
  if (Object.keys(patch).length === 0) return;

  saving.value = true;
  saveError.value = null;
  try {
    const updated = await apiSeries.patch(detail.value.id, patch);
    detail.value = updated;
    form.value = snapshotForm(updated);
    seriesStore.updateSeries(updated.id, patch);
  } catch (err: unknown) {
    saveError.value = err instanceof Error ? err.message : t('series.save_failed');
  } finally {
    saving.value = false;
    showRootConfirm.value = false;
  }
}

async function onSaveClick() {
  if (!isDirty.value) return;
  if (rootChanged.value) {
    showRootConfirm.value = true;
    return;
  }
  await commitSave();
}

watch(
  selectedId,
  (id) => {
    if (id !== null && !isNaN(id)) {
      loadDetail(id);
    } else {
      detail.value = null;
      form.value = null;
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

      <template v-else-if="detail && form">
        <div class="field-group">
          <label>{{ t('series.field.title') }}</label>
          <input v-model="form.canonical_title" />
        </div>

        <div class="field-group">
          <label>{{ t('series.field.root') }}</label>
          <input v-model="form.root_path" />
        </div>

        <div class="field-group">
          <label>{{ t('series.field.filter') }}</label>
          <input v-model="form.default_filter" />
        </div>

        <div class="field-group">
          <label>{{ t('series.field.offset') }}</label>
          <input v-model.number="form.default_offset" type="number" />
        </div>

        <div v-if="saveError" class="save-error">{{ saveError }}</div>

        <div class="form-footer">
          <button
            class="btn-secondary"
            :disabled="!isDirty || saving"
            @click="cancelEdit"
          >
            {{ t('series.cancel') }}
          </button>
          <button
            class="btn-primary"
            :disabled="!isDirty || saving"
            @click="onSaveClick"
          >
            {{ saving ? t('series.saving') : t('series.save') }}
          </button>
        </div>

        <div class="meta">
          <div><strong>{{ t('series.field.season') }}:</strong> {{ detail.season }}</div>
          <div><strong>{{ t('series.field.year') }}:</strong> {{ detail.year ?? '-' }}</div>
          <img v-if="detail.poster_url" :src="detail.poster_url" class="poster" />
        </div>
      </template>
    </div>

    <!-- Root-path change confirmation -->
    <div v-if="showRootConfirm" class="modal-backdrop" @click.self="showRootConfirm = false">
      <div class="modal">
        <h4>{{ t('series.confirm_root_title') }}</h4>
        <p>{{ t('series.confirm_root_body') }}</p>
        <div class="modal-footer">
          <button class="btn-secondary" :disabled="saving" @click="showRootConfirm = false">
            {{ t('series.cancel') }}
          </button>
          <button class="btn-danger" :disabled="saving" @click="commitSave">
            {{ saving ? t('series.saving') : t('series.confirm') }}
          </button>
        </div>
      </div>
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

.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.save-error {
  margin-top: 8px;
  padding: 8px 10px;
  background: #fed7d7;
  color: #822727;
  border-radius: 4px;
  font-size: 12px;
}

.btn-primary,
.btn-secondary,
.btn-danger {
  padding: 6px 14px;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 120ms, border-color 120ms;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.btn-primary {
  background: #4299e1;
  color: white;

  &:not(:disabled):hover {
    background: #3182ce;
  }
}

.btn-secondary {
  background: #f7fafc;
  color: #2d3748;
  border-color: #cbd5e0;

  &:not(:disabled):hover {
    background: #edf2f7;
  }
}

.btn-danger {
  background: #e53e3e;
  color: white;

  &:not(:disabled):hover {
    background: #c53030;
  }
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: white;
  border-radius: 6px;
  padding: 24px;
  max-width: 440px;
  width: 90%;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);

  h4 {
    margin: 0 0 12px;
    font-size: 16px;
  }

  p {
    margin: 0 0 20px;
    font-size: 14px;
    line-height: 1.5;
    color: #4a5568;
  }
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
