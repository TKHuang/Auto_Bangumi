<script lang="ts" setup>
import { NSpin } from 'naive-ui';
import { Down } from '@icon-park/vue-next';
import { onClickOutside, useEventListener } from '@vueuse/core';

const props = withDefaults(
  defineProps<{
    type?: 'primary' | 'warn';
    size?: 'big' | 'normal' | 'small';
    link?: string | null;
    loading?: boolean;
    selections: string[];
  }>(),
  {
    type: 'primary',
    size: 'normal',
    link: null,
    loading: false,
  }
);

defineEmits(['click']);

const selected = ref<string>(props.selections[0]);
const showSelections = ref<boolean>(false);

const triggerRef = ref<HTMLElement | null>(null);
const menuRef = ref<HTMLElement | null>(null);

const menuGeometry = reactive({ top: 0, left: 0, width: 0 });

function syncMenuPosition() {
  const el = triggerRef.value;
  if (!el) return;
  const r = el.getBoundingClientRect();
  menuGeometry.top = r.bottom + 6;
  menuGeometry.left = r.left;
  menuGeometry.width = r.width;
}

const menuStyle = computed(() => ({
  position: 'fixed' as const,
  top: `${menuGeometry.top}px`,
  left: `${menuGeometry.left}px`,
  width: `${menuGeometry.width}px`,
  zIndex: 200,
}));

watch(showSelections, (v) => {
  if (v) {
    nextTick(() => syncMenuPosition());
  }
});

useEventListener(() => window, 'resize', () => {
  if (showSelections.value) syncMenuPosition();
});

useEventListener(
  () => window,
  'scroll',
  () => {
    if (showSelections.value) syncMenuPosition();
  },
  { capture: true }
);

onClickOutside(
  triggerRef,
  () => {
    showSelections.value = false;
  },
  { ignore: [menuRef] }
);

const buttonSize = computed(() => {
  switch (props.size) {
    case 'big':
      return 'rounded-10 text-h1 w-276 h-55 text-h1';
    case 'normal':
      return 'rounded-6 w-170 h-36';
    case 'small':
      return 'rounded-6 w-86 h-28 text-main';
  }
});

const loadingSize = computed(() => {
  switch (props.size) {
    case 'big':
      return 'large';
    case 'normal':
      return 'small';
    case 'small':
      return 18;
  }
});

function onSelect(selection: string) {
  selected.value = selection;
  showSelections.value = false;
}

function onMainAction() {
  showSelections.value = false;
}

function toggleSelections() {
  showSelections.value = !showSelections.value;
}
</script>

<template>
  <div ref="triggerRef" :class="buttonSize" f-cer overflow-hidden>
    <Component
      :is="link !== null ? 'a' : 'button'"
      :href="link"
      text-white
      outline-none
      wh-full
      pl-12
      :class="[`type-${type}`]"
      @click="
        () => {
          onMainAction();
          $emit('click', selected);
        }
      "
    >
      <NSpin :show="loading" :size="loadingSize">
        <div text-main>{{ selected }}</div>
      </NSpin>
    </Component>
    <div
      is-btn
      px-12
      h-full
      f-cer
      :class="[`selector-${type}`]"
      @click="toggleSelections"
    >
      <Down fill="white" />
    </div>
  </div>

  <Teleport to="body">
    <Transition name="multi-menu">
      <div
        v-show="showSelections"
        ref="menuRef"
        class="multi-select-menu"
        :class="[`multi-select-menu--${type}`]"
        :style="menuStyle"
      >
        <div
          v-for="item in selections"
          :key="item"
          is-btn
          class="multi-select-item"
          :class="[`type-${type}`]"
          @click="onSelect(item)"
        >
          {{ item }}
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style lang="scss" scoped>
.type {
  &-primary {
    @include bg-mouse-event(#4e3c94, #281e52, #8e8a9c);
  }

  &-warn {
    @include bg-mouse-event(#943c61, #521e2a, #9c8a93);
  }
}
.selector {
  &-primary {
    @include bg-mouse-event(#4e3c94, #281e52, #8e8a9c);
  }

  &-warn {
    @include bg-mouse-event(#943c61, #521e2a, #9c8a93);
  }
}

.multi-select-menu {
  overflow: hidden;
  border-radius: 10px;
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.06),
    0 12px 32px rgba(0, 0, 0, 0.18);

  &--warn {
    box-shadow:
      0 0 0 1px rgba(208, 92, 130, 0.35),
      0 14px 36px rgba(90, 30, 50, 0.28);
  }

  &--primary {
    box-shadow:
      0 0 0 1px rgba(78, 60, 148, 0.25),
      0 14px 36px rgba(40, 25, 90, 0.22);
  }
}

.multi-select-item {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 34px;
  padding: 8px 10px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #fff;
  transition: filter 0.15s ease;

  &:hover {
    filter: brightness(1.08) saturate(1.05);
  }

  & + & {
    border-top: 1px solid rgba(255, 255, 255, 0.14);
  }
}

.multi-menu-enter-active,
.multi-menu-leave-active {
  transition:
    opacity 0.16s ease,
    transform 0.16s ease;
}

.multi-menu-enter-from,
.multi-menu-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
