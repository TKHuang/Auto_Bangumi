<script lang="ts" setup>
import { useDebounceFn } from '@vueuse/core';
import { NCheckbox, NDynamicTags } from 'naive-ui';
import type { BangumiAPI } from '#/bangumi';
import type { RSS } from '#/rss';

interface PendingBangumi extends BangumiAPI {
  global_filter_matches: string[];
}

interface PendingResponse {
  bangumi: PendingBangumi[];
  pending_count: number;
  active_count: number;
}

interface TorrentPreview {
  name: string;
  url: string;
  homepage: string;
  filter: boolean;
}

const props = defineProps<{
  rssId: number;
  rssName: string;
}>();

// Emit when bangumi are activated (to refresh parent data)
const emit = defineEmits<{
  (e: 'activated', count: number): void;
}>();

const show = defineModel<boolean>('show', { default: false });

const loading = ref(false);
const pendingBangumi = ref<PendingBangumi[]>([]);
const pendingCount = ref(0);
const activeCount = ref(0);

// RSS item for torrent analysis
const rssItem = ref<RSS | null>(null);

// Track selected bangumi for batch operations
const selectedIds = ref<Set<number>>(new Set());

// Track expanded bangumi row (only one at a time)
const expandedId = ref<number | null>(null);

// Local filter edits - Map<bangumi_id, filter_array>
const localFilters = ref<Map<number, string[]>>(new Map());

// Torrent preview data - Map<bangumi_id, torrents[]>
const torrentPreviews = ref<Map<number, TorrentPreview[]>>(new Map());
const torrentPreviewLoading = ref<Set<number>>(new Set());

const { t } = useMyI18n();
const message = useMessage();

// Track activation state
const activating = ref(false);

// Computed: check if all bangumi are selected
const isAllSelected = computed(() => {
  if (pendingBangumi.value.length === 0) return false;
  return pendingBangumi.value.every((b) => selectedIds.value.has(b.id));
});

// Computed: check if some (but not all) bangumi are selected
const isSomeSelected = computed(() => {
  if (pendingBangumi.value.length === 0) return false;
  const selectedCount = pendingBangumi.value.filter((b) =>
    selectedIds.value.has(b.id)
  ).length;
  return selectedCount > 0 && selectedCount < pendingBangumi.value.length;
});

// Computed: count of selected bangumi
const selectedCount = computed(() => selectedIds.value.size);

// Toggle all selection
function toggleAll() {
  if (isAllSelected.value) {
    // Deselect all
    selectedIds.value = new Set();
  } else {
    // Select all
    selectedIds.value = new Set(pendingBangumi.value.map((b) => b.id));
  }
}

// Select all
function selectAll() {
  selectedIds.value = new Set(pendingBangumi.value.map((b) => b.id));
}

// Check if a bangumi is selected
function isSelected(id: number): boolean {
  return selectedIds.value.has(id);
}

// Toggle selection for a single bangumi
function toggleSelection(id: number) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id);
  } else {
    selectedIds.value.add(id);
  }
  // Force reactivity
  selectedIds.value = new Set(selectedIds.value);
}

// Check if a row is expanded
function isExpanded(id: number): boolean {
  return expandedId.value === id;
}

// Toggle row expansion
function toggleExpand(id: number) {
  if (expandedId.value === id) {
    expandedId.value = null;
  } else {
    expandedId.value = id;
    // Initialize local filter if not already set
    if (!localFilters.value.has(id)) {
      const bangumi = pendingBangumi.value.find((b) => b.id === id);
      if (bangumi) {
        // Start with the global filter matches as default
        localFilters.value.set(id, [...(bangumi.global_filter_matches || [])]);
      }
    }
    // Fetch torrent preview when expanding
    fetchTorrentPreview(id);
  }
}

// Get local filter for a bangumi
function getLocalFilter(id: number): string[] {
  return localFilters.value.get(id) || [];
}

// Update local filter for a bangumi
function updateLocalFilter(id: number, filters: string[]) {
  localFilters.value.set(id, filters);
  // Force reactivity
  localFilters.value = new Map(localFilters.value);
  // Trigger debounced torrent preview update
  debouncedFetchTorrentPreview(id);
}

// Clear filter for a bangumi
function clearFilter(id: number) {
  localFilters.value.set(id, []);
  localFilters.value = new Map(localFilters.value);
  // Trigger debounced torrent preview update
  debouncedFetchTorrentPreview(id);
}

// Reset to global filter for a bangumi
function resetToGlobal(id: number) {
  const bangumi = pendingBangumi.value.find((b) => b.id === id);
  if (bangumi) {
    localFilters.value.set(id, [...(bangumi.global_filter_matches || [])]);
    localFilters.value = new Map(localFilters.value);
    // Trigger debounced torrent preview update
    debouncedFetchTorrentPreview(id);
  }
}

// Get torrents that will be kept (not filtered out)
function getTorrentsKeep(id: number): TorrentPreview[] {
  const torrents = torrentPreviews.value.get(id) || [];
  return torrents.filter((t) => !t.filter);
}

// Get torrents that will be excluded (filtered out)
function getTorrentsExclude(id: number): TorrentPreview[] {
  const torrents = torrentPreviews.value.get(id) || [];
  return torrents.filter((t) => t.filter);
}

// Fetch torrent preview for a specific bangumi
async function fetchTorrentPreview(id: number) {
  if (!rssItem.value?.url) return;

  const bangumi = pendingBangumi.value.find((b) => b.id === id);
  if (!bangumi) return;

  const filters = localFilters.value.get(id) || [];
  const filterStr = filters.join(',');

  torrentPreviewLoading.value.add(id);
  torrentPreviewLoading.value = new Set(torrentPreviewLoading.value);

  try {
    const res = await apiDownload.analysisTorrents(
      rssItem.value,
      filterStr,
      bangumi.title_raw
    );
    torrentPreviews.value.set(id, res);
    torrentPreviews.value = new Map(torrentPreviews.value);
  } catch (e) {
    console.error('Failed to fetch torrent preview:', e);
  } finally {
    torrentPreviewLoading.value.delete(id);
    torrentPreviewLoading.value = new Set(torrentPreviewLoading.value);
  }
}

// Debounced version for filter changes
const debouncedFetchTorrentPreview = useDebounceFn(fetchTorrentPreview, 500);

async function fetchPendingBangumi() {
  if (!props.rssId) return;

  loading.value = true;
  pendingBangumi.value = [];
  pendingCount.value = 0;
  activeCount.value = 0;
  rssItem.value = null;

  try {
    // Fetch RSS list to get the RSS item for torrent analysis
    const rssList = await apiRSS.get();
    rssItem.value = rssList.find((r) => r.id === props.rssId) || null;

    const { data } = await axios.get<PendingResponse>(
      `api/v1/rss/aggregate/pending/${props.rssId}`
    );
    if (data) {
      pendingBangumi.value = data.bangumi;
      pendingCount.value = data.pending_count;
      activeCount.value = data.active_count;
    }
  } catch (e: any) {
    const errorMsg = e.response?.data?.detail || t('notify.update_failed');
    message.error(errorMsg);
    show.value = false;
  } finally {
    loading.value = false;
  }
}

// Activate selected bangumi
async function activateSelected() {
  if (selectedIds.value.size === 0) {
    message.warning(t('rss.no_bangumi_selected'));
    return;
  }

  activating.value = true;
  let successCount = 0;
  let failCount = 0;

  for (const id of selectedIds.value) {
    try {
      // Get the local filter for this bangumi (if edited) or empty string
      const filters = localFilters.value.get(id) || [];
      const filterStr = filters.join(',');
      await apiBangumi.activatePending(id, filterStr);
      successCount++;
    } catch (e) {
      console.error(`Failed to activate bangumi ${id}:`, e);
      failCount++;
    }
  }

  activating.value = false;

  if (successCount > 0) {
    message.success(t('rss.activated_success_count', { count: successCount }));
    emit('activated', successCount);
    show.value = false;
  }

  if (failCount > 0) {
    message.error(`${t('rss.activation_failed')}: ${failCount}`);
  }
}

// Watch for dialog open
watch(show, (visible) => {
  if (visible) {
    fetchPendingBangumi();
  } else {
    // Cleanup on close
    pendingBangumi.value = [];
    pendingCount.value = 0;
    activeCount.value = 0;
    rssItem.value = null;
    selectedIds.value = new Set();
    expandedId.value = null;
    localFilters.value = new Map();
    torrentPreviews.value = new Map();
    torrentPreviewLoading.value = new Set();
  }
});
</script>

<template>
  <ab-popup
    v-model:show="show"
    :title="`${$t('rss.manage_bangumi')} - ${rssName}`"
    css="max-w-900"
    :show-progress="loading"
  >
    <!-- Loading State -->
    <div v-if="loading" class="loading-container">
      <div class="loading-spinner">
        <div i-carbon-renew class="animate-spin text-24 text-blue-500" />
      </div>
      <span class="text-14 text-gray-500">{{ $t('rss.loading_pending') }}</span>
    </div>

    <!-- Empty State -->
    <div v-else-if="pendingBangumi.length === 0" f-cer h-200>
      <n-empty :description="$t('rss.no_pending_bangumi')" />
    </div>

    <!-- Content -->
    <div v-else class="content-container">
      <!-- Summary Header with Batch Selection Controls -->
      <div class="summary-header" flex="~ items-center justify-between">
        <div flex="~ items-center gap-x-12">
          <!-- Select All Checkbox -->
          <NCheckbox
            :checked="isAllSelected"
            :indeterminate="isSomeSelected"
            @update:checked="toggleAll"
          />
          <span class="text-14 text-gray-700 dark:text-gray-300">
            {{ $t('rss.pending_review_count', { count: pendingCount }) }}
          </span>
        </div>

        <div flex="~ items-center gap-x-12">
          <!-- Selected Count -->
          <span v-if="selectedCount > 0" text="14 blue-600 dark:blue-400">
            {{ $t('rss.selected_count', { count: selectedCount }) }}
          </span>

          <!-- Select All Button -->
          <n-button size="small" @click="selectAll">
            {{ $t('rss.select_all') }}
          </n-button>
        </div>
      </div>

      <!-- Pending Bangumi List -->
      <div class="bangumi-list" max-h-60vh overflow-y-auto>
        <div
          v-for="item in pendingBangumi"
          :key="item.id"
          class="bangumi-item"
          border-b="1 solid gray-100 dark:gray-700"
        >
          <!-- Main Row -->
          <div
            class="bangumi-row"
            :class="{
              expanded: isExpanded(item.id),
              selected: isSelected(item.id),
            }"
            flex="~ items-center gap-x-12"
            py-12
            px-12
            cursor-pointer
            rounded-8
            @click="toggleExpand(item.id)"
          >
            <!-- Checkbox -->
            <NCheckbox
              :checked="isSelected(item.id)"
              @update:checked="toggleSelection(item.id)"
              @click.stop
            />

            <!-- Title -->
            <div flex="~ col" flex-1 min-w-0>
              <div flex="~ items-center gap-x-8">
                <span
                  text="14 gray-800 dark:gray-200"
                  font-medium
                  class="truncate"
                >
                  {{ item.official_title }}
                </span>
              </div>

              <!-- Season and Group -->
              <div flex="~ items-center gap-x-8" mt-4>
                <span text="12 gray-500">
                  {{ $t('homepage.rule.season') }} {{ item.season }}
                </span>
                <span v-if="item.group_name" text="12 gray-400">·</span>
                <span v-if="item.group_name" text="12 gray-500">
                  {{ item.group_name }}
                </span>
              </div>

              <!-- Global Filter Matches -->
              <div
                v-if="item.global_filter_matches?.length > 0"
                flex="~ items-center gap-x-4 wrap"
                mt-6
              >
                <span text="11 gray-400">{{ $t('rss.matched_filters') }}:</span>
                <n-tag
                  v-for="pattern in item.global_filter_matches"
                  :key="pattern"
                  size="tiny"
                  type="error"
                  :bordered="false"
                >
                  {{ pattern }}
                </n-tag>
              </div>
            </div>

            <!-- Expand Indicator -->
            <div
              class="expand-icon"
              :class="{ rotated: isExpanded(item.id) }"
              i-carbon-chevron-down
              text="16 gray-400"
            />
          </div>

          <!-- Expanded Edit Panel -->
          <div
            v-if="isExpanded(item.id)"
            class="edit-panel"
            px-8
            py-12
            bg="gray-50 dark:gray-800"
          >
            <div flex="~ gap-x-16">
              <!-- Left Side: Filter Editor -->
              <div class="filter-section" flex="~ col" w-320 shrink-0>
                <!-- Matched from global info -->
                <div v-if="item.global_filter_matches?.length > 0" mb-12>
                  <span text="12 gray-500">
                    {{
                      $t('rss.matched_from_global', {
                        patterns: item.global_filter_matches.join(', '),
                      })
                    }}
                  </span>
                </div>

                <!-- Filter Tags Editor -->
                <div flex="~ col gap-y-8">
                  <span text="12 gray-600 dark:gray-400" font-medium>
                    {{ $t('rss.edit_filter') }}
                  </span>
                  <div class="filter-editor" max-w-full overflow-x-auto pb-1>
                    <NDynamicTags
                      :value="getLocalFilter(item.id)"
                      size="small"
                      @update:value="(val: string[]) => updateLocalFilter(item.id, val)"
                    />
                  </div>
                </div>

                <!-- Action Buttons -->
                <div flex="~ items-center gap-x-8" mt-12>
                  <n-button size="small" @click.stop="clearFilter(item.id)">
                    {{ $t('rss.clear_filter') }}
                  </n-button>
                  <n-button size="small" @click.stop="resetToGlobal(item.id)">
                    {{ $t('rss.reset_to_global') }}
                  </n-button>
                </div>
              </div>

              <!-- Right Side: Torrent Preview -->
              <div flex="~ col" flex-1 overflow-hidden min-w-0>
                <div
                  text="14 gray-500"
                  mb-8
                  flex="~ justify-between items-center"
                >
                  <span>{{ $t('rss.torrent_preview') }}</span>
                  <span
                    v-if="torrentPreviewLoading.has(item.id)"
                    class="animate-spin"
                  >
                    <div i-carbon-renew text="16 blue-500" />
                  </span>
                </div>

                <div flex="~ gap-x-8" flex-1 overflow-hidden>
                  <!-- Keep List -->
                  <div flex="~ col" flex-1 overflow-hidden>
                    <div text="12 gray-400" mb-4 px-4>
                      {{ $t('rss.keep') }} ({{
                        getTorrentsKeep(item.id).length
                      }})
                    </div>
                    <div
                      flex-1
                      overflow-y-auto
                      rounded-8
                      bg="green-50 dark:green-900/20"
                      p-8
                      space-y-4
                      max-h-200
                    >
                      <div
                        v-for="torrent in getTorrentsKeep(item.id)"
                        :key="torrent.url"
                        text="11 green-700 dark:green-300"
                        p-4
                        rounded-4
                      >
                        {{ torrent.name }}
                      </div>
                      <div
                        v-if="
                          getTorrentsKeep(item.id).length === 0 &&
                          !torrentPreviewLoading.has(item.id)
                        "
                        text="12 gray-400 center"
                        py-20
                      >
                        {{ $t('rss.no_torrents') }}
                      </div>
                    </div>
                  </div>

                  <!-- Exclude List -->
                  <div flex="~ col" flex-1 overflow-hidden>
                    <div text="12 gray-400" mb-4 px-4>
                      {{ $t('rss.exclude') }} ({{
                        getTorrentsExclude(item.id).length
                      }})
                    </div>
                    <div
                      flex-1
                      overflow-y-auto
                      rounded-8
                      bg="red-50 dark:red-900/20"
                      p-8
                      space-y-4
                      max-h-200
                    >
                      <div
                        v-for="torrent in getTorrentsExclude(item.id)"
                        :key="torrent.url"
                        text="11 red-700 dark:red-300"
                        p-4
                        rounded-4
                        class="opacity-60 line-through"
                      >
                        {{ torrent.name }}
                      </div>
                      <div
                        v-if="
                          getTorrentsExclude(item.id).length === 0 &&
                          !torrentPreviewLoading.has(item.id)
                        "
                        text="12 gray-400 center"
                        py-20
                      >
                        {{ $t('rss.no_torrents') }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Action Footer -->
      <div
        class="action-footer"
        flex="~ items-center justify-end gap-x-10"
        mt-16
        pt-12
      >
        <div text="12 gray-500" flex-1 flex="~ items-center">
          {{
            selectedCount > 0
              ? $t('rss.selected_count', { count: selectedCount })
              : ''
          }}
        </div>
        <ab-button
          size="small"
          class="!w-auto whitespace-nowrap px-16"
          :loading="activating"
          :disabled="selectedCount === 0"
          @click="activateSelected"
        >
          {{ $t('rss.apply_activate') }}
        </ab-button>
      </div>
    </div>
  </ab-popup>
</template>

<style scoped>
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  gap: 16px;
}

.loading-spinner {
  display: flex;
  align-items: center;
  justify-content: center;
}

.content-container {
  min-height: 200px;
}

.summary-header {
  margin-bottom: 16px;
  padding: 12px 16px;
  background: linear-gradient(
    135deg,
    rgba(99, 102, 241, 0.08),
    rgba(168, 85, 247, 0.08)
  );
  border-radius: 10px;
  border: 1px solid rgba(99, 102, 241, 0.15);
}

.dark .summary-header {
  background: linear-gradient(
    135deg,
    rgba(99, 102, 241, 0.12),
    rgba(168, 85, 247, 0.12)
  );
  border-color: rgba(99, 102, 241, 0.25);
}

.bangumi-list {
  background: rgba(0, 0, 0, 0.02);
  border-radius: 12px;
  padding: 8px;
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.dark .bangumi-list {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.08);
}

.bangumi-item {
  border-radius: 8px;
}

.bangumi-item:last-child {
  border-bottom: none;
}

.bangumi-row {
  transition: background-color 0.15s ease, border-color 0.15s ease;
  border: 1px solid transparent;
  margin: 4px 0;
}

.bangumi-row:hover {
  background: rgba(0, 0, 0, 0.03);
}

.dark .bangumi-row:hover {
  background: rgba(255, 255, 255, 0.04);
}

.bangumi-row.selected {
  background: rgba(99, 102, 241, 0.08);
  border-color: rgba(99, 102, 241, 0.3);
}

.dark .bangumi-row.selected {
  background: rgba(99, 102, 241, 0.15);
  border-color: rgba(99, 102, 241, 0.4);
}

.bangumi-row.expanded {
  background: rgba(0, 0, 0, 0.03);
}

.dark .bangumi-row.expanded {
  background: rgba(255, 255, 255, 0.04);
}

.bangumi-row.selected.expanded {
  background: rgba(99, 102, 241, 0.12);
}

.dark .bangumi-row.selected.expanded {
  background: rgba(99, 102, 241, 0.18);
}

.expand-icon {
  transition: transform 0.2s ease;
  flex-shrink: 0;
}

.expand-icon.rotated {
  transform: rotate(180deg);
}

.edit-panel {
  border-top: 1px solid rgba(0, 0, 0, 0.05);
}

.dark .edit-panel {
  border-top-color: rgba(255, 255, 255, 0.08);
}

.filter-editor {
  min-height: 32px;
}

.action-footer {
  border-top: 1px solid rgb(229, 231, 235);
}

.dark .action-footer {
  border-top-color: rgb(55, 65, 81);
}
</style>
