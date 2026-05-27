<template>
  <div class="avatar" :style="{ width: size + 'px', height: size + 'px' }">
    <img v-if="src" :src="src" :alt="name" class="avatar-img" />
    <span v-else class="avatar-text">{{ initial }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  src: String,
  name: { type: String, default: '' },
  size: { type: Number, default: 36 },
})

const initial = computed(() => (props.name ? props.name[0].toUpperCase() : '?'))
</script>

<style scoped>
.avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--accent-subtle);
  flex-shrink: 0;
  overflow: hidden;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-text {
  font-weight: 600;
  color: var(--accent);
  font-size: 0.45em;
}
</style>
