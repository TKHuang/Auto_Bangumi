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

const props = withDefaults(
  defineProps<{
    renameInProgress?: boolean;
  }>(),
  {
    renameInProgress: false,
  }
);

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
const renameInProgress = computed(() => props.renameInProgress);

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
  if (renameInProgress.value) return;
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
    :escape-close="!renameInProgress"
    :show-progress="renameInProgress"
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

      <div v-if="renameInProgress" class="rename-progress">
        <span class="rename-progress-icon" animate-spin>
          <Refresh theme="outline" size="15" :stroke-width="3" />
        </span>
        <span>{{ $t('homepage.rule.retrigger_rename_progress') }}</span>
      </div>

      <div class="action-section">
        <div class="action-grid">
          <ab-button
            size="small"
            class="action-btn action-btn--rename"
            :loading="renameInProgress"
            @click="emitRetriggerRename"
          >
            <div class="action-btn-inner">
              <span class="action-icon">
                <Refresh theme="outline" size="14" :stroke-width="3" />
              </span>
              <span class="action-label">
                {{ $t('homepage.rule.retrigger_rename') }}
              </span>
            </div>
          </ab-button>
          <ab-button
            size="small"
            class="action-btn action-btn--backfill"
            @click="emitBackfillSource"
          >
            <div class="action-btn-inner">
              <span class="action-icon">
                <DownloadFour theme="outline" size="14" :stroke-width="3" />
              </span>
              <span class="action-label">
                {{ $t('homepage.rule.backfill_source') }}
              </span>
            </div>
          </ab-button>
          <ab-button
            size="small"
            class="action-btn action-btn--torrents"
            @click="() => (showTorrents = true)"
          >
            <div class="action-btn-inner">
              <span class="action-icon">
                <UnorderedList theme="outline" size="14" :stroke-width="3" />
              </span>
              <span class="action-label">
                {{ $t('rss.torrents') }}
              </span>
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
              <span class="apply-icon">
                <CheckOne theme="outline" size="15" :stroke-width="4" />
              </span>
              <span class="apply-label">{{ $t('homepage.rule.apply') }}</span>
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
  --action-primary: #4e3c94;
  --action-primary-deep: #281e52;
  --action-primary-soft: #f2eefb;
  --action-primary-border: rgba(78, 60, 148, 0.16);
  --action-warn: #943c61;
  --action-warn-deep: #521e2a;
  --action-warn-soft: rgba(148, 60, 97, 0.1);
  --action-apply: #5f4bb2;
  --action-apply-deep: #3f3180;

  position: relative;
  margin-top: 1.1rem;
  padding: 1rem 0 0;
  border-top: 1px solid rgba(78, 60, 148, 0.12);
  border-radius: 0;
  background:
    linear-gradient(180deg, rgba(247, 244, 255, 0.78), rgba(255, 255, 255, 0));
}

.rename-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 8px 10px;
  border: 1px solid rgba(78, 60, 148, 0.16);
  border-radius: 8px;
  color: #4e3c94;
  background: rgba(242, 238, 251, 0.78);
  font-size: 12px;
  font-weight: 700;
}

.rename-progress-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.action-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid rgba(78, 60, 148, 0.1);
}

.action-btn-inner,
.apply-inner {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  width: 100%;
  padding: 0 12px;
}

.apply-inner {
  gap: 10px;
  padding: 0 14px;
}

.action-icon,
.apply-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 999px;
}

.action-icon {
  width: 26px;
  height: 26px;
  background: rgba(255, 255, 255, 0.18);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.22),
    0 4px 10px rgba(78, 60, 148, 0.12);
}

.apply-icon {
  width: 28px;
  height: 28px;
  background: rgba(255, 255, 255, 0.18);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.24),
    0 4px 10px rgba(63, 49, 128, 0.18);
}

.action-label,
.apply-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.action-btn) {
  min-width: 0;
  width: 100% !important;
  height: 44px !important;
  border-radius: 12px !important;
  border: 1px solid var(--action-primary-border);
  color: var(--action-primary) !important;
  font-weight: 700;
  font-size: 12px;
  letter-spacing: 0.02em;
  position: relative;
  overflow: hidden;
  transition:
    transform 0.18s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.8),
    0 8px 18px rgba(78, 60, 148, 0.08);
}

:deep(.action-btn::before) {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.58), transparent 60%);
  opacity: 0.8;
}

:deep(.action-btn--rename) {
  background: linear-gradient(180deg, #e7dbff 0%, #cfbbf7 100%) !important;
  border-color: rgba(88, 66, 173, 0.3);
}

:deep(.action-btn--rename .action-icon) {
  color: #4e369f;
  background: rgba(78, 54, 159, 0.16);
}

:deep(.action-btn--backfill) {
  background: linear-gradient(180deg, #dfd0ff 0%, #c5aff1 100%) !important;
  border-color: rgba(95, 68, 181, 0.3);
  color: #573aa9 !important;
}

:deep(.action-btn--backfill .action-icon) {
  color: #5e3fb4;
  background: rgba(94, 63, 180, 0.16);
}

:deep(.action-btn--torrents) {
  grid-column: 1 / -1;
  background: linear-gradient(180deg, #cfbcf7 0%, #ae90e4 100%) !important;
  border-color: rgba(80, 56, 163, 0.34);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.74),
    0 10px 18px rgba(78, 60, 148, 0.18);
}

:deep(.action-btn--torrents .action-icon) {
  color: #4b31a1;
  background: rgba(75, 49, 161, 0.18);
}

:deep(.action-btn:hover) {
  transform: translateY(-1px);
  border-color: rgba(78, 60, 148, 0.3);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.82),
    0 10px 18px rgba(78, 60, 148, 0.16);
}

:deep(.action-btn:active) {
  transform: translateY(0);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.72),
    0 4px 10px rgba(78, 60, 148, 0.08);
}

:deep(.apply-accent) {
  flex-shrink: 0;
  width: 136px !important;
  height: 44px !important;
  border-radius: 12px !important;
  border: 1px solid rgba(79, 57, 168, 0.4);
  background: linear-gradient(180deg, #b191ef 0%, #7655cb 100%) !important;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.22),
    0 12px 24px rgba(78, 60, 148, 0.22);
  font-weight: 800;
  font-size: 12px;
  letter-spacing: 0.03em;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.18);
  transition:
    transform 0.18s ease,
    box-shadow 0.22s ease,
    filter 0.22s ease;
}

:deep(.apply-accent:hover) {
  filter: brightness(1.05) saturate(1.05);
  transform: translateY(-1px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.24),
    0 14px 26px rgba(78, 60, 148, 0.26);
}

:deep(.apply-accent:active) {
  transform: translateY(0);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 7px 14px rgba(78, 60, 148, 0.18);
}

.delete-wrap {
  flex-shrink: 0;
}

// ab-button-multi trigger row (split button)
.delete-wrap :deep(> div:first-child) {
  width: 136px !important;
  height: 44px !important;
  border-radius: 12px !important;
  overflow: hidden;
  border: 1px solid rgba(145, 65, 112, 0.38);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.2),
    0 12px 24px rgba(120, 45, 73, 0.2);
  transition:
    transform 0.18s ease,
    box-shadow 0.22s ease,
    filter 0.22s ease;
}

.delete-wrap :deep(> div:first-child:hover) {
  transform: translateY(-1px);
  filter: brightness(1.05) saturate(1.05);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.22),
    0 14px 26px rgba(120, 45, 73, 0.24);
}

.delete-wrap :deep(> div:first-child:active) {
  transform: translateY(0);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.16),
    0 7px 14px rgba(120, 45, 73, 0.16);
}

.delete-wrap :deep(.type-warn),
.delete-wrap :deep(.selector-warn) {
  background: linear-gradient(180deg, #be7aa2 0%, #94476d 100%) !important;
  font-weight: 800;
  font-size: 12px;
  letter-spacing: 0.03em;
  text-shadow: 0 1px 0 rgba(88, 31, 60, 0.2);
}

.delete-wrap :deep(.selector-warn) {
  border-left: 1px solid rgba(255, 255, 255, 0.16);
}

.delete-wrap :deep(.type-warn) {
  padding-left: 14px !important;
}

.delete-wrap :deep(.selector-warn) {
  min-width: 38px;
}

@media (max-width: 640px) {
  .action-grid {
    grid-template-columns: 1fr;
  }

  .action-footer {
    flex-direction: column;
    align-items: stretch;
  }

  :deep(.apply-accent),
  .delete-wrap,
  .delete-wrap :deep(> div:first-child) {
    width: 100% !important;
  }
}
</style>
