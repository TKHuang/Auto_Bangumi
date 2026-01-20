<script lang="ts" setup>
const props = withDefaults(
  defineProps<{
    label: string | (() => string);
  }>(),
  {
    label: '',
  }
);

const abLabel = computed(() => {
  if (typeof props.label === 'function') return props.label();
  else return props.label;
});
</script>

<template>
  <div flex="~ items-start justify-between" style="gap: 3rem;">
    <div class="label-text" flex-shrink-0 style="min-width: 110px;">{{ abLabel }}</div>

    <slot></slot>
  </div>
</template>

<style scoped>
.label-text {
  padding-top: 2px;
}
</style>
