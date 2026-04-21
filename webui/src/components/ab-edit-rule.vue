<script lang="ts" setup>
import {
  Refresh,
  DownloadFour,
  UnorderedList,
  CheckOne,
} from '@icon-park/vue-next';
import type { BangumiRule } from '#/bangumi';

const emit = defineEmits<{
  (e: 'apply', rule: BangumiRule): void;
  (e: 'enable', id: number): void;
  (e: 'retriggerRename', id: number): void;
  (e: 'backfillSource', id: number): void;
  (
    e: 'deleteFile',
    type: 'disable' | 'delete',
    opts: { id: number; deleteFile: boolean }
  ): void;
}>();

const { t } = useMyI18n();

const show = defineModel('show', { default: false });
const rule = defineModel<BangumiRule>('rule', {
  required: true,
});

const deleteFileDialog = reactive<{
  show: boolean;
  type: 'disable' | 'delete';
}>({
  show: false,
  type: 'disable',
});

const showTorrents = ref(false);

watch(show, (val) => {
  if (!val) {
    deleteFileDialog.show = false;
  }
});

function showDeleteFileDialog(type: String) {
  deleteFileDialog.show = true;
  if (type === 'disable' || type === '禁用') {
    deleteFileDialog.type = 'disable';
  } else {
    deleteFileDialog.type = 'delete';
  }
}

const close = () => (show.value = false);

function emitdeleteFile(deleteFile: boolean) {
  emit('deleteFile', deleteFileDialog.type, {
    id: rule.value.id,
    deleteFile,
  });
}

function emitApply() {
  emit('apply', rule.value);
}

function emitEnable() {
  emit('enable', rule.value.id);
}

function emitRetriggerRename() {
  emit('retriggerRename', rule.value.id);
}

function emitBackfillSource() {
  emit('backfillSource', rule.value.id);
}

const popupTitle = computed(() => {
  if (rule.value.deleted) {
    return t('homepage.rule.enable_rule');
  } else {
    return t('homepage.rule.edit_rule');
  }
});

const boxSize = computed(() => {
  if (rule.value.deleted) {
    return 'w-300';
  } else {
    return 'w-380';
  }
});
</script>

<template>
  <ab-popup
    v-model:show="show"
    :title="popupTitle"
    :css="`${boxSize} max-w-90vw`"
  >
    <div v-if="rule.deleted">
      <div>{{ $t('homepage.rule.enable_hit') }}</div>

      <div line my-8></div>

      <div f-cer gap-x-10>
        <ab-button size="small" type="warn" @click="() => emitEnable()">
          {{ $t('homepage.rule.yes_btn') }}
        </ab-button>
        <ab-button size="small" @click="() => close()">
          {{ $t('homepage.rule.no_btn') }}
        </ab-button>
      </div>
    </div>

    <div v-else space-y-12>
      <ab-rule v-model:rule="rule"></ab-rule>

      <div mt-4 pt-6 class="action-section">
        <div flex gap-8>
          <ab-button
            size="small"
            class="action-btn"
            @click="emitRetriggerRename"
          >
            <div flex items-center gap-x-4>
              <Refresh theme="outline" size="13" :stroke-width="3" />
              <span>{{ $t('homepage.rule.retrigger_rename') }}</span>
            </div>
          </ab-button>
          <ab-button
            size="small"
            class="action-btn"
            @click="emitBackfillSource"
          >
            <div flex items-center gap-x-4>
              <DownloadFour theme="outline" size="13" :stroke-width="3" />
              <span>{{ $t('homepage.rule.backfill_source') }}</span>
            </div>
          </ab-button>
          <ab-button
            size="small"
            class="action-btn"
            @click="() => (showTorrents = true)"
          >
            <div flex items-center gap-x-4>
              <UnorderedList theme="outline" size="13" :stroke-width="3" />
              <span>{{ $t('rss.torrents') }}</span>
            </div>
          </ab-button>
        </div>

        <div flex justify-between items-center mt-14>
          <ab-button-multi
            size="small"
            type="warn"
            class="delete-accent"
            :selections="[t('homepage.rule.delete'), t('homepage.rule.disable')]"
            @click="showDeleteFileDialog"
          />

          <ab-button size="small" class="apply-accent" @click="emitApply">
            <div flex items-center gap-x-5>
              <CheckOne theme="outline" size="14" :stroke-width="4" />
              <span>{{ $t('homepage.rule.apply') }}</span>
            </div>
          </ab-button>
        </div>
      </div>
    </div>

    <ab-bangumi-torrents
      v-model:show="showTorrents"
      :bangumi-id="rule.id"
    ></ab-bangumi-torrents>

    <ab-popup
      v-model:show="deleteFileDialog.show"
      :title="$t('homepage.rule.delete')"
    >
      <div>{{ $t('homepage.rule.delete_hit') }}</div>
      <div line my-8></div>

      <div f-cer gap-x-10>
        <ab-button size="small" type="warn" @click="() => emitdeleteFile(true)">
          {{ $t('homepage.rule.yes_btn') }}
        </ab-button>
        <ab-button size="small" @click="() => emitdeleteFile(false)">
          {{ $t('homepage.rule.no_btn') }}
        </ab-button>
      </div>
    </ab-popup>
  </ab-popup>
</template>

<style scoped lang="scss">
.action-section {
  border-top: 1px solid rgba(78, 60, 148, 0.1);
}

:deep(.action-btn) {
  flex: 1 1 0;
  min-width: 0;
  width: 100% !important;
  height: 32px !important;
  border-radius: 8px !important;
  font-weight: 600;
  letter-spacing: 0.01em;
  transition:
    transform 0.15s ease,
    box-shadow 0.2s ease,
    filter 0.2s ease;

  span {
    white-space: nowrap;
  }
}

:deep(.action-btn:hover) {
  transform: translateY(-1px);
  box-shadow: 0 6px 14px rgba(78, 60, 148, 0.22);
  filter: brightness(1.05);
}

:deep(.action-btn:active) {
  transform: translateY(0);
  box-shadow: 0 2px 6px rgba(78, 60, 148, 0.18);
}

:deep(.apply-accent) {
  width: 118px !important;
  height: 34px !important;
  border-radius: 10px !important;
  background: linear-gradient(135deg, #7c68e8 0%, #5a46b8 100%);
  box-shadow:
    0 0 0 1px rgba(154, 137, 255, 0.45),
    0 8px 18px rgba(90, 70, 184, 0.22);
  font-weight: 800;
  letter-spacing: 0.02em;
  text-shadow: 0 1px 0 rgba(39, 25, 95, 0.18);
  transition:
    transform 0.15s ease,
    box-shadow 0.2s ease,
    filter 0.2s ease;
}

:deep(.apply-accent:hover) {
  filter: brightness(1.08) saturate(1.05);
  transform: translateY(-1px);
  box-shadow:
    0 0 0 1px rgba(154, 137, 255, 0.55),
    0 12px 24px rgba(90, 70, 184, 0.3);
}

:deep(.apply-accent:active) {
  transform: translateY(0);
  box-shadow:
    0 0 0 1px rgba(154, 137, 255, 0.45),
    0 4px 10px rgba(90, 70, 184, 0.22);
}

.delete-accent {
  :deep(> div:first-child) {
    height: 34px !important;
    border-radius: 10px !important;
    overflow: hidden;
    box-shadow:
      0 0 0 1px rgba(148, 60, 97, 0.35),
      0 6px 14px rgba(148, 60, 97, 0.18);
    transition:
      transform 0.15s ease,
      box-shadow 0.2s ease,
      filter 0.2s ease;
  }

  :deep(> div:first-child:hover) {
    transform: translateY(-1px);
    filter: brightness(1.05);
    box-shadow:
      0 0 0 1px rgba(148, 60, 97, 0.5),
      0 10px 20px rgba(148, 60, 97, 0.24);
  }

  :deep(> div:first-child:active) {
    transform: translateY(0);
    box-shadow:
      0 0 0 1px rgba(148, 60, 97, 0.4),
      0 3px 8px rgba(148, 60, 97, 0.2);
  }
}
</style>
