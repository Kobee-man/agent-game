<template>
  <button
    :class="['btn', variant, size, { loading, block }]"
    :disabled="disabled || loading"
    :type="type"
  >
    <span v-if="loading" class="spinner" />
    <slot />
  </button>
</template>

<script setup>
defineProps({
  variant: { type: String, default: 'primary' },
  size: { type: String, default: 'md' },
  type: { type: String, default: 'button' },
  disabled: Boolean,
  loading: Boolean,
  block: Boolean,
})
</script>

<style scoped>
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-weight: 500;
  border-radius: var(--radius-md);
  transition: all var(--transition);
  white-space: nowrap;
  user-select: none;
  touch-action: manipulation;
  min-height: 44px;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn.sm { padding: 6px 16px; font-size: 13px; min-height: 36px; }
.btn.md { padding: 10px 24px; font-size: 14px; }
.btn.lg { padding: 14px 32px; font-size: 16px; }

.btn.primary {
  background: var(--accent);
  color: #fff;
}
.btn.primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

.btn.secondary {
  background: var(--bg-tertiary);
  color: var(--text-primary);
  border: 1px solid var(--border);
}
.btn.secondary:hover:not(:disabled) {
  background: var(--bg-elevated);
  border-color: var(--border-hover);
}

.btn.ghost {
  background: transparent;
  color: var(--text-secondary);
}
.btn.ghost:hover:not(:disabled) {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.btn.danger {
  background: var(--danger);
  color: #fff;
}
.btn.danger:hover:not(:disabled) {
  background: #dc2626;
}

.btn.block { width: 100%; }

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid transparent;
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
