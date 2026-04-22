<script lang="ts" setup>
import {
  CheckOne,
  CloseOne,
  DeleteOne,
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
        <div class="action-row">
          <button class="action-tile action-tile--rename" @click="emitRetriggerRename">
            <span class="tile-icon tile-icon--rename">
              <Refresh theme="outline" size="15" :stroke-width="3" />
            </span>
            <span class="tile-label">{{ $t('homepage.rule.retrigger_rename') }}</span>
          </button>

          <button class="action-tile action-tile--backfill" @click="emitBackfillSource">
            <span class="tile-icon tile-icon--backfill">
              <DownloadFour theme="outline" size="15" :stroke-width="3" />
            </span>
            <span class="tile-label">{{ $t('homepage.rule.backfill_source') }}</span>
          </button>

          <button class="action-tile action-tile--torrents" @click="() => (showTorrents = true)">
            <span class="tile-icon tile-icon--torrents">
              <UnorderedList theme="outline" size="15" :stroke-width="3" />
            </span>
            <span class="tile-label">{{ $t('rss.torrents') }}</span>
          </button>
        </div>

        <div class="action-footer">
          <button class="footer-btn footer-btn--disable" @click="showDeleteFileDialog('disable')">
            <CloseOne theme="outline" size="14" :stroke-width="3" />
            <span>{{ $t('homepage.rule.disable') }}</span>
          </button>

          <button class="footer-btn footer-btn--danger" @click="showDeleteFileDialog('delete')">
            <DeleteOne theme="outline" size="14" :stroke-width="3" />
            <span>{{ $t('homepage.rule.delete') }}</span>
          </button>

          <button class="footer-btn footer-btn--apply" @click="emitApply">
            <CheckOne theme="outline" size="15" :stroke-width="3" />
            <span>{{ $t('homepage.rule.apply') }}</span>
          </button>
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
  position: relative;
  margin-top: 1rem;
  padding-top: 0.875rem;
  border-top: 1px solid rgba(78, 60, 148, 0.08);
}

.action-row {
  display: flex;
  gap: 8px;
}

.action-tile {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 4px 8px;
  border: none;
  border-radius: 12px;
  background: rgba(78, 60, 148, 0.06);
  cursor: pointer;
  outline: none;
  transition:
    background 0.2s ease,
    transform 0.15s ease,
    box-shadow 0.2s ease;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(78, 60, 148, 0.1);
  }

  &:active {
    transform: translateY(0) scale(0.97);
    box-shadow: none;
  }
}

.action-tile--rename:hover {
  background: rgba(99, 91, 255, 0.1);
}

.action-tile--backfill:hover {
  background: rgba(45, 156, 180, 0.1);
}

.action-tile--torrents:hover {
  background: rgba(124, 77, 200, 0.1);
}

.tile-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  transition: box-shadow 0.2s ease;
}

.tile-icon--rename {
  background: linear-gradient(135deg, #e8e0ff, #d4c6f9);
  color: #5b4cad;
  box-shadow: 0 2px 6px rgba(91, 76, 173, 0.15);
}

.tile-icon--backfill {
  background: linear-gradient(135deg, #d6f0f5, #b8e4ee);
  color: #2d7d8f;
  box-shadow: 0 2px 6px rgba(45, 125, 143, 0.15);
}

.tile-icon--torrents {
  background: linear-gradient(135deg, #ece0ff, #d9c5fa);
  color: #6b42b8;
  box-shadow: 0 2px 6px rgba(107, 66, 184, 0.15);
}

.tile-label {
  font-size: 11px;
  font-weight: 600;
  color: #52476b;
  letter-spacing: 0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.action-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
}

.footer-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 36px;
  padding: 0 14px;
  border: none;
  border-radius: 9px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  cursor: pointer;
  outline: none;
  white-space: nowrap;
  transition:
    background 0.2s ease,
    transform 0.15s ease,
    box-shadow 0.2s ease,
    opacity 0.2s ease;

  &:hover {
    transform: translateY(-1px);
  }

  &:active {
    transform: translateY(0) scale(0.98);
  }
}

.footer-btn--disable {
  background: rgba(120, 100, 160, 0.08);
  color: #756a8f;

  &:hover {
    background: rgba(120, 100, 160, 0.14);
    box-shadow: 0 4px 12px rgba(120, 100, 160, 0.1);
  }

  &:active {
    background: rgba(120, 100, 160, 0.18);
  }
}

.footer-btn--danger {
  background: rgba(180, 60, 90, 0.08);
  color: #a0405e;

  &:hover {
    background: rgba(180, 60, 90, 0.14);
    box-shadow: 0 4px 12px rgba(180, 60, 90, 0.1);
  }

  &:active {
    background: rgba(180, 60, 90, 0.18);
  }
}

.footer-btn--apply {
  flex: 1;
  background: #5b46b2;
  color: #fff;
  box-shadow: 0 2px 8px rgba(91, 70, 178, 0.25);

  &:hover {
    background: #5040a5;
    box-shadow: 0 6px 16px rgba(91, 70, 178, 0.3);
  }

  &:active {
    background: #483a96;
    box-shadow: 0 2px 6px rgba(91, 70, 178, 0.2);
  }
}

@media (max-width: 640px) {
  .action-row {
    flex-wrap: wrap;
  }

  .action-tile {
    min-width: calc(33.33% - 6px);
  }

  .action-footer {
    flex-direction: column-reverse;
  }

  .footer-btn {
    width: 100%;
  }
}
</style>
