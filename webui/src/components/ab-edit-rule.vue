<script lang="ts" setup>
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

      <div mt-4 pt-2 space-y-10>
        <div
          grid="~ cols-3"
          gap-10
          justify-items-center
        >
          <ab-button size="small" @click="emitRetriggerRename">
            {{ $t('homepage.rule.retrigger_rename') }}
          </ab-button>
          <ab-button size="small" @click="emitBackfillSource">
            {{ $t('homepage.rule.backfill_source') }}
          </ab-button>
          <ab-button size="small" @click="() => (showTorrents = true)">
            {{ $t('rss.torrents') }}
          </ab-button>
        </div>

        <div grid="~ cols-3" gap-10 justify-items-center pt-2>
          <ab-button-multi
            size="small"
            type="warn"
            :selections="[t('homepage.rule.delete'), t('homepage.rule.disable')]"
            @click="showDeleteFileDialog"
          />
          <div></div>

          <ab-button size="small" class="apply-accent" @click="emitApply">
            {{ $t('homepage.rule.apply') }}
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
:deep(.apply-accent) {
  background: linear-gradient(135deg, #7c68e8 0%, #5a46b8 100%);
  box-shadow:
    0 0 0 1px rgba(154, 137, 255, 0.45),
    0 8px 18px rgba(90, 70, 184, 0.22);
  font-weight: 800;
  letter-spacing: 0.01em;
  text-shadow: 0 1px 0 rgba(39, 25, 95, 0.18);
}

:deep(.apply-accent:hover) {
  filter: brightness(1.06) saturate(1.05);
  box-shadow:
    0 0 0 1px rgba(154, 137, 255, 0.55),
    0 10px 22px rgba(90, 70, 184, 0.26);
}
</style>
