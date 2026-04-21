<script lang="ts" setup>
import type { PendingItem } from '@/api/pendingResolution';

definePage({ name: 'PendingResolution' });

const { t } = useMyI18n();

const items = ref<PendingItem[]>([]);
const total = ref(0);
const loading = ref(false);

const showResolve = ref(false);
const resolveTarget = ref<PendingItem | null>(null);
const resolveUrl = ref('');
const resolveTitle = ref('');
const resolveSeason = ref(1);
const resolveError = ref<string | null>(null);
const resolveSubmitting = ref(false);

async function refresh() {
  loading.value = true;
  try {
    const data = await apiPendingResolution.list(200, 0);
    items.value = data.items;
    total.value = data.total;
  } finally {
    loading.value = false;
  }
}

async function retryOne(infoHash: string) {
  await apiPendingResolution.retry(infoHash);
  await refresh();
}

function openResolve(item: PendingItem) {
  resolveTarget.value = item;
  resolveUrl.value = '';
  resolveTitle.value = '';
  resolveSeason.value = 1;
  resolveError.value = null;
  showResolve.value = true;
}

function closeResolve() {
  showResolve.value = false;
  resolveTarget.value = null;
}

async function submitResolve() {
  if (!resolveTarget.value) return;
  const urlPattern = /\/Home\/Bangumi\/\d+#\d+/;
  if (!urlPattern.test(resolveUrl.value.trim())) {
    resolveError.value = t('pending.resolve.error_invalid_url');
    return;
  }
  if (!resolveTitle.value.trim()) {
    resolveError.value = t('pending.resolve.error_empty_title');
    return;
  }
  resolveSubmitting.value = true;
  resolveError.value = null;
  try {
    await apiPendingResolution.resolve(resolveTarget.value.info_hash, {
      mikan_bangumi_url: resolveUrl.value.trim(),
      title: resolveTitle.value.trim(),
      season: resolveSeason.value,
    });
    closeResolve();
    await refresh();
  } catch (e: unknown) {
    const detail =
      (e as { response?: { data?: { detail?: string } } })?.response?.data
        ?.detail ?? t('pending.resolve.error_generic');
    resolveError.value = detail;
  } finally {
    resolveSubmitting.value = false;
  }
}

onMounted(refresh);

const timer = window.setInterval(refresh, 30_000);
onBeforeUnmount(() => window.clearInterval(timer));
</script>

<template>
  <div class="pending-page">
    <div class="toolbar">
      <button class="btn" :disabled="loading" @click="refresh">
        {{ t('common.refresh') }}
      </button>
      <span class="count">{{ total }} {{ t('pending.items') }}</span>
    </div>

    <div v-if="loading && items.length === 0" class="loading">
      {{ t('pending.loading') }}
    </div>

    <div v-else-if="items.length === 0" class="empty">
      {{ t('pending.empty') }}
    </div>

    <table v-else class="pending-table">
      <thead>
        <tr>
          <th>{{ t('pending.col.name') }}</th>
          <th>{{ t('pending.col.attempts') }}</th>
          <th>{{ t('pending.col.last_error') }}</th>
          <th>{{ t('pending.col.first_seen') }}</th>
          <th>{{ t('common.actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.info_hash">
          <td class="name" :title="item.raw_name">
            <a
              v-if="item.homepage"
              :href="item.homepage"
              target="_blank"
              rel="noopener noreferrer"
              class="name-link"
            >
              {{ item.raw_name }}
            </a>
            <template v-else>{{ item.raw_name }}</template>
          </td>
          <td>{{ item.attempt_count }}</td>
          <td class="err">{{ item.last_error || '-' }}</td>
          <td class="date">{{ item.first_seen_at ?? '-' }}</td>
          <td class="actions">
            <button class="btn btn-sm" @click="retryOne(item.info_hash)">
              {{ t('pending.retry') }}
            </button>
            <button
              class="btn btn-sm btn-primary"
              @click="openResolve(item)"
            >
              {{ t('pending.resolve.action') }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="showResolve" class="modal-overlay" @click.self="closeResolve">
      <div class="modal">
        <h3>{{ t('pending.resolve.title') }}</h3>
        <p class="hint" :title="resolveTarget?.raw_name">
          {{ resolveTarget?.raw_name }}
        </p>

        <label class="field">
          <span>{{ t('pending.resolve.url_label') }}</span>
          <input
            v-model="resolveUrl"
            type="text"
            placeholder="https://mikanani.me/Home/Bangumi/3901#1243"
            :disabled="resolveSubmitting"
          />
          <small class="help">{{ t('pending.resolve.url_help') }}</small>
        </label>

        <label class="field">
          <span>{{ t('pending.resolve.title_label') }}</span>
          <input
            v-model="resolveTitle"
            type="text"
            :disabled="resolveSubmitting"
          />
        </label>

        <label class="field">
          <span>{{ t('pending.resolve.season_label') }}</span>
          <input
            v-model.number="resolveSeason"
            type="number"
            min="1"
            :disabled="resolveSubmitting"
          />
        </label>

        <div v-if="resolveError" class="err-banner">{{ resolveError }}</div>

        <div class="modal-actions">
          <button
            class="btn"
            :disabled="resolveSubmitting"
            @click="closeResolve"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            class="btn btn-primary"
            :disabled="resolveSubmitting"
            @click="submitResolve"
          >
            {{
              resolveSubmitting
                ? t('pending.resolve.submitting')
                : t('pending.resolve.submit')
            }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.pending-page {
  padding: 12px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.count {
  color: #666;
  font-size: 13px;
}

.pending-table {
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

.name {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.err {
  color: #c05621;
  font-size: 12px;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.date {
  font-size: 12px;
  color: #666;
  white-space: nowrap;
}

.loading,
.empty {
  text-align: center;
  padding: 40px;
  color: #888;
}

.btn {
  padding: 4px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;

  &:hover:not(:disabled) {
    background: #f5f5f5;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.btn-sm {
  padding: 2px 8px;
  font-size: 12px;
}

.btn-primary {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;

  &:hover:not(:disabled) {
    background: #1d4ed8;
  }
}

.name-link {
  color: inherit;
  text-decoration: none;
  border-bottom: 1px dotted rgba(0, 0, 0, 0.2);

  &:hover {
    color: #2563eb;
    border-bottom-color: #2563eb;
  }
}

.actions {
  display: flex;
  gap: 6px;
  white-space: nowrap;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.modal {
  width: 480px;
  max-width: 92vw;
  background: #fff;
  border-radius: 8px;
  padding: 20px 24px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);

  h3 {
    margin: 0 0 8px;
    font-size: 16px;
  }
}

.hint {
  color: #666;
  font-size: 12px;
  margin: 0 0 16px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.field {
  display: block;
  margin-bottom: 12px;

  span {
    display: block;
    font-size: 12px;
    font-weight: 600;
    color: #444;
    margin-bottom: 4px;
  }

  input {
    width: 100%;
    padding: 6px 10px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 13px;
  }
}

.help {
  display: block;
  font-size: 11px;
  color: #888;
  margin-top: 4px;
}

.err-banner {
  background: #fef2f2;
  color: #b91c1c;
  padding: 8px 10px;
  border-radius: 4px;
  font-size: 12px;
  margin-bottom: 12px;
}

.modal-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 8px;
}
</style>
