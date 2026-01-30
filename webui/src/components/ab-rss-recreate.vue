<script lang="ts" setup>
import { useDebounceFn } from '@vueuse/core';
import type { BangumiAPI, BangumiRule } from '#/bangumi';
import { ruleTemplate } from '#/bangumi';
import type { RSS } from '#/rss';

const show = defineModel<boolean>('show', { default: false });

const props = withDefaults(
  defineProps<{
    autoDeleteOnCancel?: boolean;
  }>(),
  {
    autoDeleteOnCancel: false,
  }
);

const emit = defineEmits<{
  cancelled: [rssId: number];
  subscribed: [];
}>();

const rssId = ref(0);
const rssItem = ref<RSS | null>(null);

// For single-bangumi mode (non-aggregate RSS)
const bangumi = ref<BangumiRule | null>(null);

// For multi-bangumi mode (aggregate RSS)
const bangumiList = ref<BangumiRule[]>([]);
const isAggregate = computed(() => bangumiList.value.length > 1);

// Track which bangumi is currently expanded for preview (aggregate mode)
const expandedIndex = ref<number | null>(null);

// Track if we're in pending review mode (official_title should be read-only)
const isPendingReview = ref(false);

// Parsing error state (shown as warning in single-bangumi mode)
const parsingError = reactive({
  hasError: false,
  msgEn: '',
  msgZh: '',
});

// Track if subscription was completed
const subscriptionCompleted = ref(false);

const loading = reactive({
  bangumi: false,
  torrents: false,
  collect: false,
  subscribe: false,
});

const deleteFilesDialog = reactive<{
  show: boolean;
  action: 'subscribe' | 'collect';
}>({
  show: false,
  action: 'subscribe',
});

// Request cancellation management
let abortController: AbortController | null = null;

// Torrents for single-bangumi mode
const torrents = ref<
  { name: string; url: string; homepage: string; filter: boolean }[]
>([]);

// Torrents per bangumi for aggregate mode (keyed by index)
const aggregateTorrents = ref<
  Map<
    number,
    { name: string; url: string; homepage: string; filter: boolean }[]
  >
>(new Map());
const aggregateTorrentsLoading = ref<Set<number>>(new Set());

// Unified loading state for preventing accidental close
const isAnyLoading = computed(
  () =>
    loading.bangumi ||
    loading.torrents ||
    loading.collect ||
    loading.subscribe ||
    aggregateTorrentsLoading.value.size > 0
);

// Can close dialog only when not loading
const canClose = computed(() => !isAnyLoading.value);

const torrentsKeep = computed(() => torrents.value.filter((t) => !t.filter));
const torrentsExclude = computed(() => torrents.value.filter((t) => t.filter));

// Get torrents for a specific bangumi in aggregate mode
function getAggregateTorrentsKeep(index: number) {
  const t = aggregateTorrents.value.get(index) || [];
  return t.filter((t) => !t.filter);
}

function getAggregateTorrentsExclude(index: number) {
  const t = aggregateTorrents.value.get(index) || [];
  return t.filter((t) => t.filter);
}

async function getTorrents() {
  if (rssItem.value?.url && bangumi.value?.filter) {
    loading.torrents = true;
    try {
      const res = await apiDownload.analysisTorrents(
        rssItem.value,
        bangumi.value.filter.join(',')
      );
      torrents.value = res;
    } catch (e) {
      console.error(e);
    } finally {
      loading.torrents = false;
    }
  }
}

async function getAggregateTorrentsForBangumi(index: number) {
  const b = bangumiList.value[index];
  if (!b) return;

  aggregateTorrentsLoading.value.add(index);
  try {
    // Use the bangumi's season-specific RSS link if available
    // This is the RSS that will actually be used when eps_complete_from_source is enabled
    const bangumiRssUrl = b.rss_link?.[0];

    if (bangumiRssUrl && bangumiRssUrl !== rssItem.value?.url) {
      // Bangumi has a season-specific RSS (different from aggregate RSS)
      // Use it directly without title_raw filtering since it's already specific
      const seasonRss: RSS = {
        ...rssItem.value!,
        url: bangumiRssUrl,
      };
      const res = await apiDownload.analysisTorrents(
        seasonRss,
        b.filter.join(',')
        // No title_raw filter needed - season RSS is already specific to this bangumi
      );
      aggregateTorrents.value.set(index, res);
    } else if (rssItem.value?.url) {
      // Fallback to aggregate RSS with title_raw filter
      const res = await apiDownload.analysisTorrents(
        rssItem.value,
        b.filter.join(','),
        b.title_raw
      );
      aggregateTorrents.value.set(index, res);
    }
  } catch (e) {
    console.error(e);
  } finally {
    aggregateTorrentsLoading.value.delete(index);
  }
}

const debouncedGetTorrents = useDebounceFn(getTorrents, 300);

// Create debounced functions per bangumi
const debouncedGetAggregateTorrents = new Map<number, () => void>();

function getDebouncedAggregateTorrents(index: number) {
  if (!debouncedGetAggregateTorrents.has(index)) {
    debouncedGetAggregateTorrents.set(
      index,
      useDebounceFn(() => getAggregateTorrentsForBangumi(index), 300)
    );
  }
  return debouncedGetAggregateTorrents.get(index)!;
}

watch(
  () => bangumi.value?.filter,
  () => {
    debouncedGetTorrents();
  },
  { deep: true }
);

// Watch for filter changes in aggregate mode
watch(
  () => bangumiList.value.map((b) => b.filter),
  (newFilters, oldFilters) => {
    if (!isAggregate.value) return;

    // Find which bangumi's filter changed
    newFilters.forEach((filter, index) => {
      if (JSON.stringify(filter) !== JSON.stringify(oldFilters?.[index])) {
        getDebouncedAggregateTorrents(index)();
      }
    });
  },
  { deep: true }
);

const { t, returnUserLangText } = useMyI18n();
const message = useMessage();
const { getAll } = useBangumiStore();

// Error type guard for parsing failures
interface BangumiParsingFailedError {
  status: boolean;
  status_code: number;
  error_type: string;
  msg_en: string;
  msg_zh: string;
  partial_data: {
    raw_title: string;
    group: string | null;
    season: number | null;
    resolution: string | null;
    subtitle: string | null;
  };
}

function isBangumiParsingFailedError(
  err: unknown
): err is BangumiParsingFailedError {
  return (
    typeof err === 'object' &&
    err !== null &&
    'error_type' in err &&
    (err as BangumiParsingFailedError).error_type === 'bangumi_parsing_failed'
  );
}

function handleParsingFailedError(
  err: BangumiParsingFailedError,
  pendingBangumi: BangumiAPI[]
) {
  // Store error info for display
  parsingError.hasError = true;
  parsingError.msgEn = err.msg_en;
  parsingError.msgZh = err.msg_zh;

  // Create skeleton BangumiRule from partial data - show in ab-rule form directly
  const partial = err.partial_data;

  // If there's a pending bangumi, use its official_title (read-only)
  let officialTitle = '';
  if (pendingBangumi.length > 0) {
    officialTitle = pendingBangumi[0].official_title;
    isPendingReview.value = true;
  }

  bangumi.value = {
    ...ruleTemplate,
    rss_id: rssId.value,
    official_title: officialTitle, // Prefill from pending if exists, otherwise empty
    title_raw: partial.raw_title || '',
    season: partial.season ?? 1,
    group_name: partial.group || '',
    dpi: partial.resolution || '',
    subtitle: partial.subtitle || '',
    filter: [], // Empty filter - user can adjust
    rss_link: rssItem.value?.url ? [rssItem.value.url] : [],
  };

  // Load torrents for preview (may show all since no filter)
  getTorrents();
}

// Cleanup function to reset state and cancel pending requests
function cleanupState() {
  // Cancel any pending requests
  if (abortController) {
    abortController.abort();
    abortController = null;
  }

  // Reset data
  bangumi.value = null;
  bangumiList.value = [];
  torrents.value = [];
  aggregateTorrents.value.clear();
  debouncedGetAggregateTorrents.clear();
  expandedIndex.value = null;

  // Reset parsing error state
  parsingError.hasError = false;
  parsingError.msgEn = '';
  parsingError.msgZh = '';

  // Reset pending review state
  isPendingReview.value = false;

  // Reset loading states
  loading.bangumi = false;
  loading.torrents = false;
  loading.collect = false;
  loading.subscribe = false;
  aggregateTorrentsLoading.value.clear();
}

// Watch for dialog close to cleanup
watch(show, (visible) => {
  if (!visible) {
    // If dialog is closing without subscription and autoDeleteOnCancel is true
    if (props.autoDeleteOnCancel && !subscriptionCompleted.value && rssId.value) {
      emit('cancelled', rssId.value);
    }
    cleanupState();
  }
});

defineExpose({
  async open(id: number) {
    // Cleanup any previous state first
    cleanupState();

    subscriptionCompleted.value = false;
    rssId.value = id;
    loading.bangumi = true;
    show.value = true;

    // Create new abort controller for this session
    abortController = new AbortController();

    await loadBangumi();
  },
});

async function loadBangumi() {
  loading.bangumi = true;
  bangumi.value = null;
  bangumiList.value = [];
  expandedIndex.value = null;
  aggregateTorrents.value.clear();
  debouncedGetAggregateTorrents.clear();
  parsingError.hasError = false;
  isPendingReview.value = false;

  // Fetch pending bangumi first (outside inner try-catch so it's available in error handling)
  let pendingBangumi: BangumiAPI[] = [];

  try {
    const rss = await apiRSS.get();
    rssItem.value = rss.find((r) => r.id === rssId.value) || null;

    // Check if there are existing pending bangumi for this RSS
    // If so, we'll use their official_title (read-only) to prevent duplicates
    try {
      pendingBangumi = await apiRSS.getPendingBangumi(rssId.value);
    } catch {
      // Ignore errors - proceed with fresh parse
    }

    const data = await apiRSS.recreate(rssId.value);

    if (data && data.length > 0) {
      if (data.length === 1) {
        // Single bangumi - use original behavior (non-aggregate RSS)
        const first = data[0];

        // If there's a pending bangumi, use its official_title (read-only)
        let officialTitle = first.official_title;
        if (pendingBangumi.length > 0) {
          officialTitle = pendingBangumi[0].official_title;
          isPendingReview.value = true;
        }

        bangumi.value = {
          ...first,
          official_title: officialTitle,
          filter: first.filter.split(','),
          rss_link: first.rss_link.split(','),
        };
        getTorrents();
      } else {
        // Multiple bangumi - aggregate RSS mode
        // For aggregate RSS, also check pending and apply read-only official_title
        const pendingByTitleRaw = new Map(
          pendingBangumi.map((b) => [b.title_raw, b])
        );
        const hasPending = pendingBangumi.length > 0;

        bangumiList.value = data.map((b) => {
          // If this bangumi has a pending version, use its official_title
          const pendingMatch = pendingByTitleRaw.get(b.title_raw);
          return {
            ...b,
            official_title: pendingMatch?.official_title || b.official_title,
            filter: b.filter.split(','),
            rss_link: b.rss_link.split(','),
          };
        });

        if (hasPending) {
          isPendingReview.value = true;
        }

        // Load torrents for all bangumi in parallel
        await Promise.all(
          bangumiList.value.map((_, index) =>
            getAggregateTorrentsForBangumi(index)
          )
        );

        // Expand first bangumi by default
        if (bangumiList.value.length > 0) {
          expandedIndex.value = 0;
        }
      }
    } else {
      message.info(t('rss.no_new_rules'));
      show.value = false;
    }
  } catch (e) {
    // Check if this is a bangumi parsing failed error
    if (isBangumiParsingFailedError(e)) {
      handleParsingFailedError(e, pendingBangumi);
    } else {
      message.error(t('notify.update_failed'));
      show.value = false;
    }
  } finally {
    loading.bangumi = false;
  }
}

function toggleExpand(index: number) {
  if (expandedIndex.value === index) {
    expandedIndex.value = null;
  } else {
    expandedIndex.value = index;
    // Reload torrents when expanding
    getAggregateTorrentsForBangumi(index);
  }
}

function showDeleteFilesDialog(action: 'subscribe' | 'collect') {
  deleteFilesDialog.action = action;
  deleteFilesDialog.show = true;
}

async function confirmDeleteFiles(deleteFiles: boolean) {
  deleteFilesDialog.show = false;
  
  if (deleteFilesDialog.action === 'subscribe') {
    await doSubscribe(deleteFiles);
  } else {
    await doCollect(deleteFiles);
  }
}

async function subscribe() {
  if (props.autoDeleteOnCancel) {
    await doSubscribe(false);
  } else {
    showDeleteFilesDialog('subscribe');
  }
}

async function doSubscribe(deleteFiles: boolean) {
  if (!rssItem.value) return;

  if (isAggregate.value) {
    loading.subscribe = true;
    try {
      await apiDownload.subscribeBatch(bangumiList.value, rssItem.value, deleteFiles);
      message.success(
        t('rss.subscribe_success_count', { count: bangumiList.value.length })
      );
      subscriptionCompleted.value = true;
      emit('subscribed');
      getAll();
      show.value = false;
    } catch (e) {
      console.error('Batch subscribe failed:', e);
      message.error(t('notify.update_failed'));
    } finally {
      loading.subscribe = false;
    }
  } else {
    if (!bangumi.value) return;

    loading.subscribe = true;
    try {
      await apiDownload.subscribe(bangumi.value, rssItem.value, deleteFiles);
      message.success(t('notify.update_success'));
      subscriptionCompleted.value = true;
      emit('subscribed');
      getAll();
      show.value = false;
    } catch (e) {
      message.error(t('notify.update_failed'));
    } finally {
      loading.subscribe = false;
    }
  }
}

async function collect() {
  if (props.autoDeleteOnCancel) {
    await doCollect(false);
  } else {
    showDeleteFilesDialog('collect');
  }
}

async function doCollect(_deleteFiles: boolean) {
  if (isAggregate.value) {
    loading.collect = true;
    try {
      let successCount = 0;
      for (const b of bangumiList.value) {
        try {
          await apiDownload.collection(b);
          successCount++;
        } catch (e) {
          console.error(`Failed to collect ${b.official_title}:`, e);
        }
      }

      if (successCount > 0) {
        message.success(
          t('rss.collect_success_count', { count: successCount })
        );
        subscriptionCompleted.value = true;
        emit('subscribed');
        getAll();
        show.value = false;
      } else {
        message.error(t('notify.update_failed'));
      }
    } catch (e) {
      message.error(t('notify.update_failed'));
    } finally {
      loading.collect = false;
    }
  } else {
    if (!bangumi.value) return;

    loading.collect = true;
    try {
      await apiDownload.collection(bangumi.value);
      message.success(t('notify.update_success'));
      subscriptionCompleted.value = true;
      emit('subscribed');
      getAll();
      show.value = false;
    } catch (e) {
      message.error(t('notify.update_failed'));
    } finally {
      loading.collect = false;
    }
  }
}
</script>

<template>
  <ab-popup
    v-model:show="show"
    :title="$t('rss.review_rules')"
    :css="bangumi || isAggregate ? 'max-w-1000' : 'w-360'"
    :escape-close="canClose"
    :show-progress="isAnyLoading"
  >
    <!-- Loading State with Skeleton -->
    <div v-if="loading.bangumi" class="skeleton-container">
      <div class="skeleton-header">
        <span class="text-14 text-gray-500">{{
          $t('rss.parsing_torrents')
        }}</span>
      </div>
      <div class="skeleton-grid">
        <ab-skeleton-card
          v-for="n in 3"
          :key="n"
          :show-poster="true"
          :lines="3"
          :style="{ animationDelay: `${(n - 1) * 100}ms` }"
        />
      </div>
    </div>

    <!-- Empty State -->
    <div v-else-if="!bangumi && !isAggregate" f-cer h-200>
      <n-empty />
    </div>

    <!-- Single Bangumi Mode (Non-Aggregate RSS) -->
    <div v-else-if="bangumi && !isAggregate" flex="~ col gap-y-12">
      <!-- Parsing Error Warning -->
      <div
        v-if="parsingError.hasError"
        rounded-8
        bg="amber-50 dark:amber-900/20"
        p-12
        border="~ amber-200 dark:amber-700"
      >
        <div flex="~ items-start gap-x-8">
          <div i-carbon-warning-alt text="amber-500" text-18 mt-2 shrink-0></div>
          <div>
            <div text="14 amber-700 dark:amber-300" font-medium mb-4>
              {{
                $t('rss.manual_input.parsing_failed_title') || 'Parsing Failed'
              }}
            </div>
            <div text="13 amber-600 dark:amber-400">
              {{
                returnUserLangText({
                  en: parsingError.msgEn,
                  'zh-CN': parsingError.msgZh,
                })
              }}
            </div>
          </div>
        </div>
      </div>

      <div flex="~ gap-x-12">
        <div class="w-360" space-y-12>
          <ab-rule v-model:rule="bangumi" :readonly-official-title="isPendingReview"></ab-rule>
          <div flex="~ justify-end gap-x-10" mt-16>
            <ab-button size="small" :loading="loading.collect" @click="collect">
              {{ $t('topbar.add.collect') }}
            </ab-button>
            <ab-button
              size="small"
              :loading="loading.subscribe"
              @click="subscribe"
            >
              {{ $t('topbar.add.subscribe') }}
            </ab-button>
          </div>
        </div>

      <div class="w-500" flex="~ col">
        <div text="14 gray-500" mb-8 flex="~ justify-between items-center">
          <span>{{ $t('rss.torrent_list') || 'Torrent List' }}</span>
          <span v-if="loading.torrents" animate-spin>
            <div i-carbon-renew></div>
          </span>
        </div>

        <div flex="~ gap-x-8" flex-1 overflow-hidden>
          <!-- Keep List -->
          <div flex="~ col" flex-1 overflow-hidden>
            <div text="12 gray-400" mb-4 px-4>
              {{ $t('rss.keep') || 'Keep' }} ({{ torrentsKeep.length }})
            </div>
            <div
              flex-1
              overflow-y-auto
              rounded-8
              bg="green-50 dark:green-900/20"
              p-8
              space-y-4
              max-h-400
            >
              <div
                v-for="torrent in torrentsKeep"
                :key="torrent.url"
                text="12 green-700 dark:green-300"
                p-4
                rounded-4
              >
                {{ torrent.name }}
              </div>
              <div
                v-if="torrentsKeep.length === 0 && !loading.torrents"
                text="12 gray-400 center"
                py-20
              >
                {{ $t('rss.no_torrents') || 'No torrents found' }}
              </div>
            </div>
          </div>

          <!-- Exclude List -->
          <div flex="~ col" flex-1 overflow-hidden>
            <div text="12 gray-400" mb-4 px-4>
              {{ $t('rss.exclude') || 'Exclude' }} ({{
                torrentsExclude.length
              }})
            </div>
            <div
              flex-1
              overflow-y-auto
              rounded-8
              bg="red-50 dark:red-900/20"
              p-8
              space-y-4
              max-h-400
            >
              <div
                v-for="torrent in torrentsExclude"
                :key="torrent.url"
                text="12 red-700 dark:red-300"
                p-4
                rounded-4
                class="opacity-60 line-through"
              >
                {{ torrent.name }}
              </div>
              <div
                v-if="torrentsExclude.length === 0 && !loading.torrents"
                text="12 gray-400 center"
                py-20
              >
                {{ $t('rss.no_torrents') || 'No torrents found' }}
              </div>
            </div>
          </div>
        </div>
      </div>
      </div>
    </div>

    <!-- Multi-Bangumi Mode (Aggregate RSS) -->
    <div v-else-if="isAggregate" class="w-full" space-y-16>
      <!-- Header -->
      <div flex="~ justify-between items-center" px-8>
        <div text="14 gray-700 dark:gray-300" font-medium>
          {{ $t('rss.found_bangumi_count', { count: bangumiList.length }) }}
        </div>
      </div>

      <!-- Bangumi List with Preview -->
      <div space-y-16 max-h-600 overflow-y-auto px-8 pb-8>
        <div
          v-for="(b, index) in bangumiList"
          :key="index"
          class="bangumi-card"
          :class="{ expanded: expandedIndex === index }"
        >
          <!-- Card Header -->
          <div
            flex="~ items-center justify-between gap-x-16"
            mb-12
            pb-12
            border-b="1 solid gray-100 dark:gray-700"
            cursor-pointer
            @click="toggleExpand(index)"
          >
            <div flex="~ items-center gap-x-12">
              <div
                class="expand-icon"
                :class="{ rotated: expandedIndex === index }"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  class="w-16 h-16"
                >
                  <polyline points="9 18 15 12 9 6"></polyline>
                </svg>
              </div>
              <div text="14 gray-700 dark:gray-300" font-medium>
                {{ b.official_title || `${$t('rss.bangumi')} #${index + 1}` }}
              </div>
            </div>
            <div text="12 gray-500">
              {{ getAggregateTorrentsKeep(index).length }}
              {{ $t('rss.torrents_will_download') || 'torrents' }}
            </div>
          </div>

          <!-- Expandable Content -->
          <div v-show="expandedIndex === index" class="bangumi-content">
            <div flex="~ gap-x-16">
              <!-- Edit Form (Left) -->
              <div class="w-320 shrink-0">
                <ab-rule v-model:rule="bangumiList[index]" :readonly-official-title="isPendingReview"></ab-rule>
              </div>

              <!-- Torrent Preview (Right) -->
              <div flex="~ col" flex-1 overflow-hidden min-w-0>
                <div
                  text="14 gray-500"
                  mb-8
                  flex="~ justify-between items-center"
                >
                  <span>{{ $t('rss.torrent_list') || 'Torrent List' }}</span>
                  <span v-if="aggregateTorrentsLoading.has(index)" animate-spin>
                    <div i-carbon-renew></div>
                  </span>
                </div>

                <div flex="~ gap-x-8" flex-1 overflow-hidden>
                  <!-- Keep List -->
                  <div flex="~ col" flex-1 overflow-hidden>
                    <div text="12 gray-400" mb-4 px-4>
                      {{ $t('rss.keep') || 'Keep' }} ({{
                        getAggregateTorrentsKeep(index).length
                      }})
                    </div>
                    <div
                      flex-1
                      overflow-y-auto
                      rounded-8
                      bg="green-50 dark:green-900/20"
                      p-8
                      space-y-4
                      max-h-300
                    >
                      <div
                        v-for="torrent in getAggregateTorrentsKeep(index)"
                        :key="torrent.url"
                        text="11 green-700 dark:green-300"
                        p-4
                        rounded-4
                      >
                        {{ torrent.name }}
                      </div>
                      <div
                        v-if="
                          getAggregateTorrentsKeep(index).length === 0 &&
                          !aggregateTorrentsLoading.has(index)
                        "
                        text="12 gray-400 center"
                        py-20
                      >
                        {{ $t('rss.no_torrents') || 'No torrents found' }}
                      </div>
                    </div>
                  </div>

                  <!-- Exclude List -->
                  <div flex="~ col" flex-1 overflow-hidden>
                    <div text="12 gray-400" mb-4 px-4>
                      {{ $t('rss.exclude') || 'Exclude' }} ({{
                        getAggregateTorrentsExclude(index).length
                      }})
                    </div>
                    <div
                      flex-1
                      overflow-y-auto
                      rounded-8
                      bg="red-50 dark:red-900/20"
                      p-8
                      space-y-4
                      max-h-300
                    >
                      <div
                        v-for="torrent in getAggregateTorrentsExclude(index)"
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
                          getAggregateTorrentsExclude(index).length === 0 &&
                          !aggregateTorrentsLoading.has(index)
                        "
                        text="12 gray-400 center"
                        py-20
                      >
                        {{ $t('rss.no_torrents') || 'No torrents found' }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Action Buttons -->
      <div
        flex="~ justify-end gap-x-10"
        px-8
        pt-8
        border-t="1 solid gray-200 dark:gray-700"
      >
        <div text="12 gray-500" flex-1 flex="~ items-center">
          {{
            $t('rss.will_subscribe_count', { count: bangumiList.length }) ||
            `Will subscribe ${bangumiList.length} bangumi`
          }}
        </div>
        <ab-button size="small" :loading="loading.collect" @click="collect">
          {{ $t('topbar.add.collect') }}
        </ab-button>
        <ab-button size="small" :loading="loading.subscribe" @click="subscribe">
          {{ $t('topbar.add.subscribe') }}
        </ab-button>
      </div>
    </div>

    <ab-popup
      v-model:show="deleteFilesDialog.show"
      :title="$t('rss.delete_files_title')"
    >
      <div>{{ $t('rss.delete_files_message') }}</div>
      <div line my-8></div>
      <div f-cer gap-x-10>
        <ab-button size="small" type="warn" @click="() => confirmDeleteFiles(true)">
          {{ $t('rss.delete_files_yes') }}
        </ab-button>
        <ab-button size="small" @click="() => confirmDeleteFiles(false)">
          {{ $t('rss.delete_files_no') }}
        </ab-button>
      </div>
    </ab-popup>
  </ab-popup>
</template>

<style scoped>
/* Skeleton Loading Styles */
.skeleton-container {
  min-height: 200px;
  padding: 16px;
}

.skeleton-header {
  text-align: center;
  margin-bottom: 16px;
}

.skeleton-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Content reveal animation */
.content-reveal {
  animation: revealContent 0.3s ease-out;
}

@keyframes revealContent {
  from {
    opacity: 0;
    transform: scale(0.98);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.bangumi-card {
  @apply rounded-xl border bg-white dark:bg-gray-800 transition-all duration-200;
  border: 2px solid rgb(229, 231, 235);
  padding: 16px 20px;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
}

.dark .bangumi-card {
  border-color: rgb(55, 65, 81);
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.3), 0 1px 2px 0 rgba(0, 0, 0, 0.2);
}

.bangumi-card.expanded {
  border-color: rgb(59, 130, 246);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12),
    0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

.dark .bangumi-card.expanded {
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2),
    0 4px 6px -1px rgba(0, 0, 0, 0.3);
}

.bangumi-card:hover {
  border-color: rgb(156, 163, 175);
}

.dark .bangumi-card:hover {
  border-color: rgb(107, 114, 128);
}

.bangumi-card.expanded:hover {
  border-color: rgb(59, 130, 246);
}

.bangumi-content {
  padding-top: 12px;
  animation: slideDown 0.2s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.expand-icon {
  transition: transform 0.2s ease;
  color: rgb(107, 114, 128);
}

.expand-icon.rotated {
  transform: rotate(90deg);
}
</style>
