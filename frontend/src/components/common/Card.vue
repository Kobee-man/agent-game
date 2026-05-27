<template>
  <div :class="['card', { hoverable, padding: noPadding !== true }]">
    <slot />
  </div>
</template>

<script setup>
defineProps({
  hoverable: Boolean,
  noPadding: Boolean,
})
</script>

<style scoped>
.card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  transition: all var(--transition);
}

.card.padding {
  padding: 24px;
}

.card.hoverable:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-md);
}
</style>
