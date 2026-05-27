<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="modelValue" class="overlay" @click.self="close">
        <div class="modal">
          <div class="modal-header">
            <h3 class="modal-title">{{ title }}</h3>
            <button class="close-btn" @click="close">&times;</button>
          </div>
          <div class="modal-body">
            <slot />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
defineProps({
  modelValue: Boolean,
  title: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

function close() {
  emit('update:modelValue', false)
}
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 16px;
}

.modal {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 440px;
  box-shadow: var(--shadow-md);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 0;
}

.modal-title {
  font-size: 16px;
  font-weight: 600;
}

.close-btn {
  font-size: 20px;
  color: var(--text-muted);
  line-height: 1;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
}

.close-btn:hover {
  color: var(--text-primary);
  background: var(--bg-tertiary);
}

.modal-body {
  padding: 20px 24px 24px;
}
</style>
