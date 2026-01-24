<script lang="ts" setup>
import { useDebounceFn } from '@vueuse/core';
import type { BangumiRule } from '#/bangumi';
import type { RSS } from '#/rss';
import { rssTemplate } from '#/rss';
import { ruleTemplate } from '#/bangumi';

/** v-model show */
const show = defineModel('show', { default: false });

const message = useMessage();
const { getAll } = useBangumiStore();
const { getAll: getRSS } = useRSSStore();
const { t, returnUserLangText } = useMyI18n();

const rssModel = defineModel<RSS>('rss');
const rss = ref<RSS>({ ...rssTemplate });
const rule = defineModel<BangumiRule>('rule', { default: ruleTemplate });
const parserType = ['mikan', 'tmdb', 'parser'];

// Manual input mode state (when parsing fails)
const manualInputMode = ref(false);
const manualInputError = reactive({
  msgEn: '',
  msgZh: '',
});
const manualInputPartialData = reactive({
  rawTitle: '',
  group: '',
  season: 1,
  resolution: '',
  subtitle: '',
});
const manualInputForm = reactive({
  officialTitle: '',
  season: 1,
  groupName: '',
});

// Sync from model to local when model changes (for edit mode)
watch(
  rssModel,
  (val) => {
    if (val) {
      rss.value = { ...val };
    }
  },
  { immediate: true }
);

// Sync back to model when local changes (for edit mode)
watch(
  rss,
  (val) => {
    if (rssModel.value !== undefined) {
      Object.assign(rssModel.value, val);
    }
  },
  { deep: true }
);

const windowState = reactive({
  loading: false,
  rule: false,
  next: false,
});
const loading = reactive({
  collect: false,
  subscribe: false,
  torrents: false,
});

const torrents = ref<
  { name: string; url: string; homepage: string; filter: boolean }[]
>([]);

const torrentsKeep = computed(() => torrents.value.filter((t) => !t.filter));
const torrentsExclude = computed(() => torrents.value.filter((t) => t.filter));

async function getTorrents() {
  // Use rss.value.url if set, otherwise fallback to rule.rss_link (for search results)
  const rssUrl = rss.value.url || (rule.value.rss_link?.[0] ?? '');
  if (rssUrl && rule.value.filter) {
    loading.torrents = true;
    try {
      // Create RSS object with the resolved URL for API call
      const rssForApi = rss.value.url
        ? rss.value
        : { ...rss.value, url: rssUrl };
      const res = await apiDownload.analysisTorrents(
        rssForApi,
        rule.value.filter.join(','),
        rule.value.title_raw // Pass title_raw for aggregate RSS filtering
      );
      torrents.value = res;
    } catch (e) {
      console.error(e);
    } finally {
      loading.torrents = false;
    }
  }
}

const debouncedGetTorrents = useDebounceFn(getTorrents, 300);

watch(
  () => rule.value.filter,
  () => {
    if (windowState.rule) {
      debouncedGetTorrents();
    }
  },
  { deep: true }
);

watch(
  () => windowState.rule,
  (val) => {
    if (val) {
      getTorrents();
    }
  }
);

watch(show, (val) => {
  if (!val) {
    rss.value = { ...rssTemplate };
    rule.value = { ...ruleTemplate };
    // Reset manual input mode
    manualInputMode.value = false;
    manualInputError.msgEn = '';
    manualInputError.msgZh = '';
    manualInputPartialData.rawTitle = '';
    manualInputPartialData.group = '';
    manualInputPartialData.season = 1;
    manualInputPartialData.resolution = '';
    manualInputPartialData.subtitle = '';
    manualInputForm.officialTitle = '';
    manualInputForm.season = 1;
    manualInputForm.groupName = '';
    setTimeout(() => {
      windowState.next = false;
      windowState.rule = false;
    }, 300);
  } else if (val && rule.value.official_title !== '') {
    windowState.next = true;
    windowState.rule = true;
  }
});

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

interface DuplicateError {
  status: boolean;
  status_code: number;
  error_type: 'duplicate_official_title' | 'duplicate_rss_link';
  msg_en: string;
  msg_zh: string;
  existing_bangumi: {
    id: number;
    official_title: string;
    season: number;
    group_name: string;
    rss_link?: string;
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

function isDuplicateError(err: unknown): err is DuplicateError {
  return (
    typeof err === 'object' &&
    err !== null &&
    'error_type' in err &&
    ((err as DuplicateError).error_type === 'duplicate_official_title' ||
      (err as DuplicateError).error_type === 'duplicate_rss_link')
  );
}

function handleDuplicateError(err: DuplicateError) {
  const isRssLinkDuplicate = err.error_type === 'duplicate_rss_link';

  if (isRssLinkDuplicate) {
    // For rss_link duplicate, show error message only (can't override rss_link)
    message.error(
      returnUserLangText({
        en: err.msg_en,
        'zh-CN': err.msg_zh,
      })
    );
    return;
  }

  // For official_title duplicate, transition to manual input mode
  manualInputMode.value = true;
  windowState.next = true;

  // Store error messages
  manualInputError.msgEn = err.msg_en;
  manualInputError.msgZh = err.msg_zh;

  // Pre-fill form with existing data suggestion
  manualInputForm.officialTitle = '';
  manualInputForm.season = 1;
  manualInputForm.groupName = '';

  message.warning(
    returnUserLangText({
      en: `Title "${err.existing_bangumi.official_title}" already exists. Please enter a different title.`,
      'zh-CN': `标题「${err.existing_bangumi.official_title}」已存在。请输入不同的标题。`,
    })
  );
}

function handleParsingFailedError(err: BangumiParsingFailedError) {
  // Transition to manual input mode
  manualInputMode.value = true;
  windowState.next = true;

  // Store error messages
  manualInputError.msgEn = err.msg_en;
  manualInputError.msgZh = err.msg_zh;

  // Store partial data
  manualInputPartialData.rawTitle = err.partial_data.raw_title || '';
  manualInputPartialData.group = err.partial_data.group || '';
  manualInputPartialData.season = err.partial_data.season ?? 1;
  manualInputPartialData.resolution = err.partial_data.resolution || '';
  manualInputPartialData.subtitle = err.partial_data.subtitle || '';

  // Pre-fill form with partial data
  manualInputForm.officialTitle = '';
  manualInputForm.season = manualInputPartialData.season;
  manualInputForm.groupName = manualInputPartialData.group;
}

function addRss() {
  if (rss.value.url === '') {
    message.error(t('notify.please_enter', [t('notify.rss_link')]));
  } else if (rss.value.id !== 0) {
    useApi(apiRSS.update, {
      showMessage: true,
      onBeforeExecute() {
        windowState.loading = true;
      },
      onSuccess() {
        show.value = false;
        getRSS();
      },
      onFinally() {
        windowState.loading = false;
      },
    }).execute(rss.value.id, rss.value);
  } else if (rss.value.aggregate) {
    useApi(apiRSS.add, {
      showMessage: true,
      onBeforeExecute() {
        windowState.loading = true;
      },
      onSuccess() {
        show.value = false;
        getRSS();
      },
      onFinally() {
        windowState.loading = false;
      },
    }).execute(rss.value);
  } else {
    useApi(apiRSS.add, {
      showMessage: false,
      onBeforeExecute() {
        windowState.loading = true;
      },
      onSuccess() {
        // RSS added and parsed successfully
        show.value = false;
        getRSS();
        message.success(
          returnUserLangText({
            en: 'RSS added successfully',
            'zh-CN': 'RSS 添加成功',
          })
        );
      },
      onError(err) {
        // Check if this is a bangumi parsing failed error
        if (isBangumiParsingFailedError(err)) {
          handleParsingFailedError(err);
        } else if (isDuplicateError(err)) {
          handleDuplicateError(err);
        }
        // Other errors are handled by axios interceptor
      },
      onFinally() {
        windowState.loading = false;
      },
    }).execute(rss.value);
  }
}

function collect() {
  if (rule.value) {
    useApi(apiDownload.collection, {
      showMessage: true,
      onBeforeExecute() {
        loading.collect = true;
      },
      onSuccess() {
        getAll();
        show.value = false;
      },
      onFinally() {
        loading.collect = false;
      },
    }).execute(rule.value);
  }
}

function subscribe() {
  if (rule.value) {
    useApi(apiDownload.subscribe, {
      showMessage: true,
      onBeforeExecute() {
        loading.subscribe = true;
      },
      onSuccess() {
        getAll();
        show.value = false;
      },
      onFinally() {
        loading.subscribe = false;
      },
    }).execute(rule.value, rss.value);
  }
}

function submitManualInput() {
  // Validation
  if (!manualInputForm.officialTitle.trim()) {
    message.error(
      t('notify.please_enter', [t('rss.manual_input.official_title') || 'Official Title'])
    );
    return;
  }
  if (!manualInputForm.season || manualInputForm.season < 1) {
    message.error(
      t('notify.please_enter', [t('rss.manual_input.season') || 'Season'])
    );
    return;
  }

  // Submit with manual override parameters
  useApi(apiRSS.add, {
    showMessage: true,
    onBeforeExecute() {
      windowState.loading = true;
    },
    onSuccess() {
      show.value = false;
      getRSS();
      message.success(
        returnUserLangText({
          en: 'RSS added successfully with manual input',
          'zh-CN': 'RSS 已通过手动输入成功添加',
        })
      );
    },
    onFinally() {
      windowState.loading = false;
    },
  }).execute(rss.value, {
    officialTitle: manualInputForm.officialTitle.trim(),
    season: manualInputForm.season,
    groupName: manualInputForm.groupName.trim() || undefined,
  });
}
</script>

<template>
  <ab-popup
    v-model:show="show"
    :title="
      rss.id !== 0 ? $t('rss.edit_title') || 'Edit RSS' : $t('topbar.add.title')
    "
    :css="windowState.rule ? 'max-w-900' : manualInputMode ? 'w-480' : 'w-360'"
  >
    <div v-if="!windowState.next" space-y-12>
      <ab-setting
        v-model:data="rss.url"
        :label="$t('topbar.add.rss_link')"
        type="input"
        :prop="{
          placeholder: $t('topbar.add.placeholder_link'),
        }"
      ></ab-setting>

      <ab-setting
        v-model:data="rss.name"
        :label="$t('topbar.add.name')"
        type="input"
        :prop="{
          placeholder: $t('topbar.add.placeholder_name'),
        }"
      ></ab-setting>

      <ab-setting
        v-model:data="rss.aggregate"
        :label="$t('topbar.add.aggregate')"
        type="switch"
      ></ab-setting>

      <ab-setting
        v-model:data="rss.parser"
        :label="$t('topbar.add.parser')"
        type="select"
        :prop="{
          items: parserType,
        }"
        :bottom-line="true"
      ></ab-setting>

      <div flex="~ justify-end">
        <ab-button size="small" :loading="windowState.loading" @click="addRss">
          {{
            rss.id !== 0
              ? $t('rss.edit_button') || 'Update'
              : $t('topbar.add.button')
          }}
        </ab-button>
      </div>
    </div>

    <!-- Manual Input Mode (when parsing failed) -->
    <div v-else-if="manualInputMode" space-y-16>
      <!-- Error Message -->
      <div
        rounded-8
        bg="amber-50 dark:amber-900/20"
        p-12
        border="~ amber-200 dark:amber-700"
      >
        <div flex="~ items-start gap-x-8">
          <div i-carbon-warning-alt text="amber-500" text-18 mt-2></div>
          <div>
            <div text="14 amber-700 dark:amber-300" font-medium mb-4>
              {{
                $t('rss.manual_input.parsing_failed_title') || 'Parsing Failed'
              }}
            </div>
            <div text="13 amber-600 dark:amber-400">
              {{
                returnUserLangText({
                  en: manualInputError.msgEn,
                  'zh-CN': manualInputError.msgZh,
                })
              }}
            </div>
          </div>
        </div>
      </div>

      <!-- Original Torrent Name (read-only with text selection) -->
      <div>
        <ab-label
          :label="$t('rss.manual_input.original_torrent') || 'Original Torrent'"
        >
          <textarea
            :value="manualInputPartialData.rawTitle"
            readonly
            ab-input
            class="w-full min-h-60 resize-none"
            style="user-select: text; cursor: text"
          ></textarea>
        </ab-label>
      </div>

      <!-- RSS URL Reference -->
      <div>
        <ab-label :label="$t('rss.manual_input.rss_url') || 'RSS URL'">
          <input :value="rss.url" readonly ab-input class="w-full opacity-70" />
        </ab-label>
      </div>

      <!-- Manual Input Form -->
      <div line my-12></div>

      <ab-setting
        v-model:data="manualInputForm.officialTitle"
        :label="$t('rss.manual_input.official_title') || 'Official Title'"
        type="input"
        :prop="{
          placeholder:
            $t('rss.manual_input.official_title_placeholder') ||
            'Enter bangumi official title (required)',
        }"
      ></ab-setting>

      <ab-setting
        v-model:data="manualInputForm.season"
        :label="$t('rss.manual_input.season') || 'Season'"
        type="input"
        :prop="{
          type: 'number',
          min: 1,
          placeholder: '1',
        }"
      ></ab-setting>

      <ab-setting
        v-model:data="manualInputForm.groupName"
        :label="$t('rss.manual_input.group_name') || 'Group Name'"
        type="input"
        :prop="{
          placeholder: $t('rss.manual_input.group_placeholder') || 'Optional',
        }"
      ></ab-setting>

      <!-- Detected Info (read-only) -->
      <div
        v-if="
          manualInputPartialData.resolution || manualInputPartialData.subtitle
        "
      >
        <div line my-12></div>
        <div text="13 gray-500" mb-8>
          {{ $t('rss.manual_input.detected_info') || 'Detected Info' }}
        </div>
        <div flex="~ gap-x-16" text="13 gray-600 dark:gray-400">
          <div v-if="manualInputPartialData.resolution">
            <span text="gray-400"
              >{{ $t('rss.manual_input.resolution') || 'Resolution' }}:</span
            >
            <span ml-4>{{ manualInputPartialData.resolution }}</span>
          </div>
          <div v-if="manualInputPartialData.subtitle">
            <span text="gray-400"
              >{{ $t('rss.manual_input.subtitle') || 'Subtitle' }}:</span
            >
            <span ml-4>{{ manualInputPartialData.subtitle }}</span>
          </div>
        </div>
      </div>

      <div line my-12></div>

      <div flex="~ justify-between">
        <ab-button
          size="small"
          @click="
            manualInputMode = false;
            windowState.next = false;
          "
        >
          {{ $t('rss.cancel') || 'Cancel' }}
        </ab-button>
        <ab-button
          size="small"
          :loading="windowState.loading"
          @click="submitManualInput"
        >
          {{ $t('topbar.add.subscribe') || 'Subscribe' }}
        </ab-button>
      </div>
    </div>

    <div v-else-if="windowState.rule" flex="~ gap-x-12">
      <div class="w-360" space-y-12>
        <ab-rule v-model:rule="rule"></ab-rule>
        <div flex="~ justify-end gap-x-10">
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
  </ab-popup>
</template>
