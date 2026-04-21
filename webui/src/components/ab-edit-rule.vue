<script lang="ts" setup>
import {
  CheckOne,
  DownloadFour,
  Refresh,
  UnorderedList,
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

      <div class="action-section">
        <div class="action-grid">
          <ab-button
            size="small"
            class="action-btn"
            @click="emitRetriggerRename"
          >
            <div class="action-btn-inner">
              <Refresh theme="outline" size="14" :stroke-width="3" />
              <span>{{ $t('homepage.rule.retrigger_rename') }}</span>
            </div>
          </ab-button>
          <ab-button
            size="small"
            class="action-btn"
            @click="emitBackfillSource"
          >
            <div class="action-btn-inner">
              <DownloadFour theme="outline" size="14" :stroke-width="3" />
              <span>{{ $t('homepage.rule.backfill_source') }}</span>
            </div>
          </ab-button>
          <ab-button
            size="small"
            class="action-btn"
            @click="() => (showTorrents = true)"
          >
            <div class="action-btn-inner">
              <UnorderedList theme="outline" size="14" :stroke-width="3" />
              <span>{{ $t('rss.torrents') }}</span>
            </div>
          </ab-button>
        </div>

        <div class="action-footer">
          <div class="delete-wrap">
            <ab-button-multi
              size="small"
              type="warn"
              :selections="[t('homepage.rule.delete'), t('homepage.rule.disable')]"
              @click="showDeleteFileDialog"
            />
          </div>

          <ab-button size="small" class="apply-accent" @click="emitApply">
            <div class="apply-inner">
              <CheckOne theme="outline" size="15" :stroke-width="4" />
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
  margin-top: 1rem;
  padding-top: 1.1rem;
  border-top: 1px solid rgba(78, 60, 148, 0.12);
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.action-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
}

.action-btn-inner,
.apply-inner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
}

.apply-inner {
  gap: 5px;
}

:deep(.action-btn) {
  min-width: 0;
  width: 100% !important;
  height: 36px !important;
  border-radius: 9px !important;
  font-weight: 600;
  font-size: 12px;
  letter-spacing: 0.02em;
  transition:
    transform 0.15s ease,
    box-shadow 0.2s ease,
    filter 0.2s ease;

  span {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

:deep(.action-btn:hover) {
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(78, 60, 148, 0.2);
  filter: brightness(1.04);
}

:deep(.action-btn:active) {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(78, 60, 148, 0.16);
}

:deep(.apply-accent) {
  flex-shrink: 0;
  width: 122px !important;
  height: 36px !important;
  border-radius: 10px !important;
  background: linear-gradient(135deg, #7c68e8 0%, #5a46b8 100%);
  box-shadow:
    0 0 0 1px rgba(154, 137, 255, 0.45),
    0 8px 20px rgba(90, 70, 184, 0.24);
  font-weight: 800;
  font-size: 12px;
  letter-spacing: 0.03em;
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
    0 12px 26px rgba(90, 70, 184, 0.32);
}

:deep(.apply-accent:active) {
  transform: translateY(0);
  box-shadow:
    0 0 0 1px rgba(154, 137, 255, 0.45),
    0 4px 12px rgba(90, 70, 184, 0.22);
}

.delete-wrap {
  flex-shrink: 0;
}

// ab-button-multi trigger row (split button)
.delete-wrap :deep(> div:first-child) {
  width: 122px !important;
  height: 36px !important;
  border-radius: 10px !important;
  overflow: hidden;
  box-shadow:
    0 0 0 1px rgba(208, 92, 130, 0.42),
    0 8px 20px rgba(138, 47, 78, 0.22);
  transition:
    transform 0.15s ease,
    box-shadow 0.2s ease,
    filter 0.2s ease;
}

.delete-wrap :deep(> div:first-child:hover) {
  transform: translateY(-1px);
  filter: brightness(1.06) saturate(1.04);
  box-shadow:
    0 0 0 1px rgba(208, 92, 130, 0.52),
    0 12px 26px rgba(138, 47, 78, 0.28);
}

.delete-wrap :deep(> div:first-child:active) {
  transform: translateY(0);
  box-shadow:
    0 0 0 1px rgba(208, 92, 130, 0.42),
    0 4px 12px rgba(138, 47, 78, 0.2);
}

.delete-wrap :deep(.type-warn),
.delete-wrap :deep(.selector-warn) {
  background: linear-gradient(135deg, #d05c82 0%, #8a2f4e 100%) !important;
  font-weight: 800;
  font-size: 12px;
  letter-spacing: 0.02em;
  text-shadow: 0 1px 0 rgba(80, 20, 40, 0.2);
}

.delete-wrap :deep(.selector-warn) {
  border-left: 1px solid rgba(255, 255, 255, 0.2);
}
</style>
