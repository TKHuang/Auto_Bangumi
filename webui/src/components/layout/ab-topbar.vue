<script lang="ts" setup>
import {
  Caution,
  Format,
  Me,
  Pause,
  PlayOne,
  Power,
  Refresh,
} from '@icon-park/vue-next';
import { NPopover } from 'naive-ui';
import {
  type PendingReviewSource,
  getPendingReviewInteraction,
} from './pending-review';
import { ruleTemplate } from '#/bangumi';
import type { BangumiRule } from '#/bangumi';
import AbRssRecreate from '@/components/ab-rss-recreate.vue';
import AbArManage from '@/components/ab-ar-manage.vue';

const { t, changeLocale } = useMyI18n();
const { running, onUpdate, offUpdate } = useAppInfo();

const showAccount = ref(false);
const showAddRSS = ref(false);
const showRecreate = ref(false);
const showPendingSources = ref(false);
const showPendingManage = ref(false);
const pendingManageRssId = ref(0);
const pendingManageRssName = ref('');
const searchRule = ref<BangumiRule>();

// Track RSS ID for auto-delete on cancel
const pendingRssId = ref<number | null>(null);

// Ref for ab-rss-recreate component
const recreateDialogRef = ref<InstanceType<typeof AbRssRecreate>>();
const pendingReviewDialogRef = ref<InstanceType<typeof AbRssRecreate>>();

const { start, pause, shutdown, restart, resetRule } = useProgramStore();
const { refreshPoster } = useBangumiStore();
const rssStore = useRSSStore();
const { pendingReviewSources, pendingReviewTotal } = storeToRefs(rssStore);
const { getAll: getRSS, refreshPendingCounts } = rssStore;

const items = [
  {
    id: 1,
    label: () => t('topbar.start'),
    icon: PlayOne,
    handle: start,
  },
  {
    id: 2,
    label: () => t('topbar.pause'),
    icon: Pause,
    handle: pause,
  },
  {
    id: 3,
    label: () => t('topbar.restart'),
    icon: Refresh,
    handle: restart,
  },
  {
    id: 4,
    label: () => t('topbar.shutdown'),
    icon: Power,
    handle: shutdown,
  },
  {
    id: 5,
    label: () => t('topbar.refresh_poster'),
    icon: Refresh,
    handle: refreshPoster,
  },
  {
    id: 6,
    label: () => t('topbar.reset_rule'),
    icon: Format,
    handle: resetRule,
  },
  {
    id: 7,
    label: () => t('topbar.profile.title'),
    icon: Me,
    handle: () => {
      showAccount.value = true;
    },
  },
];

const onSearchFocus = ref(false);

function addSearchResult(bangumi: BangumiRule) {
  showAddRSS.value = true;
  searchRule.value = bangumi;
  console.log('searchRule', searchRule.value);
}

// Handle rss-created event from ab-add-rss
function handleRssCreated(payload: { rssId: number; aggregate: boolean }) {
  console.log('[Topbar] RSS created:', payload);
  pendingRssId.value = payload.rssId;
  // Open the recreate dialog to show rule review
  recreateDialogRef.value?.open(payload.rssId);
}

// Handle cancelled event from ab-rss-recreate (auto-delete orphan RSS)
async function handleRecreateCancel(rssId: number) {
  console.log('[Topbar] Recreate cancelled, deleting RSS:', rssId);
  if (pendingRssId.value === rssId) {
    try {
      await apiRSS.delete(rssId);
      console.log('[Topbar] Orphan RSS deleted:', rssId);
    } catch (e) {
      console.error('[Topbar] Failed to delete orphan RSS:', e);
      // Fire-and-forget - don't block UI
    }
    pendingRssId.value = null;
  }
}

// Handle subscribed event from ab-rss-recreate
async function handleRecreateSubscribed() {
  console.log('[Topbar] Subscription completed');
  pendingRssId.value = null;
  // Refresh RSS list to show the new entry
  await getRSS();
  await refreshPendingCounts(true);
}

async function refreshPendingReviews() {
  await getRSS();
  await refreshPendingCounts(true);
}

const refreshPendingCountsAfterReview = () => refreshPendingCounts(true);

function openPendingReview(source: PendingReviewSource) {
  showPendingSources.value = false;
  if (source.rss.aggregate) {
    pendingManageRssId.value = source.rss.id;
    pendingManageRssName.value = source.rss.name;
    showPendingManage.value = true;
    return;
  }

  pendingReviewDialogRef.value?.open(source.rss.id);
}

function handlePendingReviewClick() {
  const interaction = getPendingReviewInteraction(
    pendingReviewSources.value.length
  );
  if (interaction === 'direct') {
    openPendingReview(pendingReviewSources.value[0]);
    return;
  }
  if (interaction === 'choose') {
    showPendingSources.value = !showPendingSources.value;
  }
}

watch(
  () => pendingReviewSources.value.length,
  (sourceCount) => {
    if (sourceCount < 2) showPendingSources.value = false;
  }
);

watch(showAddRSS, (val) => {
  if (!val) {
    searchRule.value = { ...ruleTemplate };
    setTimeout(() => {
      onSearchFocus.value = false;
    }, 300);
  }
});

onBeforeMount(() => {
  onUpdate();
});

let pendingReviewTimer: number | undefined;

function refreshPendingReviewsSafely() {
  refreshPendingReviews().catch((error) => {
    console.error('[Topbar] Failed to refresh pending reviews:', error);
  });
}

function refreshPendingCountsSafely() {
  refreshPendingCounts().catch((error) => {
    console.error('[Topbar] Failed to refresh pending review counts:', error);
  });
}

onMounted(() => {
  pendingReviewTimer = window.setInterval(refreshPendingCountsSafely, 30_000);
  refreshPendingReviewsSafely();
});

onUnmounted(() => {
  offUpdate();
  if (pendingReviewTimer !== undefined) {
    window.clearInterval(pendingReviewTimer);
  }
});
</script>

<template>
  <div
    h="pc:60 50"
    bg-theme-row
    text-white
    rounded="pc:16 10"
    fx-cer
    px="pc:24 15"
  >
    <div flex="~ gap-x-16">
      <div fx-cer gap-x="pc:16 10">
        <img src="/images/logo-light.svg" alt="favicon" wh="pc:24 20" />
        <img
          v-show="onSearchFocus === false"
          src="/images/AutoBangumi.svg"
          alt="AutoBangumi"
          rel
          h="18 pc:24"
          pc:top-2
        />
      </div>
    </div>

    <div ml-auto fx-cer>
      <NPopover
        v-if="pendingReviewTotal > 0"
        :show="showPendingSources"
        trigger="manual"
        placement="bottom-end"
        :show-arrow="false"
        raw
        @clickoutside="showPendingSources = false"
      >
        <template #trigger>
          <button
            type="button"
            class="pending-review-trigger"
            :aria-label="
              $t('rss.pending_review_count', { count: pendingReviewTotal })
            "
            :aria-haspopup="
              pendingReviewSources.length > 1 ? 'menu' : undefined
            "
            :aria-expanded="
              pendingReviewSources.length > 1 ? showPendingSources : undefined
            "
            @click="handlePendingReviewClick"
          >
            <Caution :size="16" />
            <span class="pending-review-label">
              {{ $t('topbar.pending_review', { count: pendingReviewTotal }) }}
            </span>
            <span class="pending-review-count">{{ pendingReviewTotal }}</span>
          </button>
        </template>

        <div class="pending-review-menu" role="menu">
          <div class="pending-review-menu-title">
            {{ $t('topbar.pending_review_title') }}
          </div>
          <button
            v-for="source in pendingReviewSources"
            :key="source.rss.id"
            type="button"
            class="pending-review-source"
            role="menuitem"
            @click="openPendingReview(source)"
          >
            <span class="pending-review-source-name">{{
              source.rss.name
            }}</span>
            <span class="pending-review-source-count">{{ source.count }}</span>
            <span aria-hidden="true" class="pending-review-source-arrow"
              >›</span
            >
          </button>
        </div>
      </NPopover>

      <ab-search-bar mr="pc:16 10" fx-cer @add-bangumi="addSearchResult" />

      <ab-status-bar
        :items="items"
        :running="running"
        @click-add="() => (showAddRSS = true)"
        @change-lang="changeLocale"
      />
    </div>
  </div>

  <ab-change-account v-model:show="showAccount"></ab-change-account>
  <ab-add-rss
    v-model:show="showAddRSS"
    v-model:rule="searchRule"
    @rss-created="handleRssCreated"
  ></ab-add-rss>
  <AbRssRecreate
    ref="recreateDialogRef"
    v-model:show="showRecreate"
    :auto-delete-on-cancel="true"
    @cancelled="handleRecreateCancel"
    @subscribed="handleRecreateSubscribed"
  />
  <AbRssRecreate
    ref="pendingReviewDialogRef"
    @subscribed="refreshPendingReviews"
  />
  <AbArManage
    v-model:show="showPendingManage"
    :rss-id="pendingManageRssId"
    :rss-name="pendingManageRssName"
    @activated="refreshPendingCountsAfterReview"
  />
</template>

<style lang="scss" scoped>
.pending-review-trigger {
  height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-right: 16px;
  padding: 0 11px;
  border: 1px solid rgba(255, 211, 107, 0.72);
  border-radius: 7px;
  background: rgba(40, 18, 58, 0.22);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
  transition: background-color 150ms ease, border-color 150ms ease;

  :deep(.i-icon) {
    color: #ffd36b;
  }

  &:hover {
    background: rgba(40, 18, 58, 0.38);
    border-color: #ffd36b;
  }

  &:focus-visible {
    outline: 2px solid #fff;
    outline-offset: 2px;
  }
}

.pending-review-count {
  display: none;
}

.pending-review-menu {
  width: 260px;
  padding: 6px;
  color: #2a1c52;
  background: #fff;
  border: 1px solid #e5e1e8;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(42, 28, 82, 0.14);
}

.pending-review-menu-title {
  padding: 7px 9px 8px;
  color: #706879;
  font-size: 12px;
  font-weight: 600;
  border-bottom: 1px solid #eeeaf0;
}

.pending-review-source {
  width: 100%;
  min-height: 38px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 8px;
  padding: 7px 9px;
  color: #2a1c52;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 150ms ease;

  &:hover,
  &:focus-visible {
    background: #f3f0f6;
    outline: none;
  }
}

.pending-review-source-name {
  overflow: hidden;
  font-size: 13px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pending-review-source-count {
  color: #9a6300;
  font-size: 12px;
  font-weight: 700;
}

.pending-review-source-arrow {
  color: #8b8490;
  font-size: 18px;
  line-height: 1;
}

@media (max-width: 767px) {
  .pending-review-trigger {
    height: 32px;
    gap: 4px;
    margin-right: 10px;
    padding: 0 8px;
  }

  .pending-review-label {
    display: none;
  }

  .pending-review-count {
    display: inline;
  }
}
</style>
