<template>
  <div class="input-group">
    <label v-if="label" class="input-label" :for="id">{{ label }}</label>
    <div class="input-wrapper">
      <input
        :id="id"
        :type="showPassword ? 'text' : type"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        class="input-field"
        @input="$emit('update:modelValue', $event.target.value)"
        @keyup.enter="$emit('enter')"
      />
      <button
        v-if="type === 'password'"
        type="button"
        class="toggle-pw"
        @click="showPassword = !showPassword"
      >
        {{ showPassword ? '隐藏' : '显示' }}
      </button>
    </div>
    <p v-if="error" class="input-error">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: String,
  type: { type: String, default: 'text' },
  placeholder: String,
  disabled: Boolean,
  error: String,
  id: { type: String, default: () => `input-${Math.random().toString(36).slice(2, 8)}` },
})

defineEmits(['update:modelValue', 'enter'])

const showPassword = ref(false)
</script>

<style scoped>
.input-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.input-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-field {
  width: 100%;
  padding: 10px 14px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 14px;
  transition: all var(--transition);
  outline: none;
}

.input-field::placeholder {
  color: var(--text-muted);
}

.input-field:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-subtle);
}

.input-field:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toggle-pw {
  position: absolute;
  right: 12px;
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
  background: none;
  border: none;
  padding: 4px;
}

.toggle-pw:hover {
  color: var(--text-secondary);
}

.input-error {
  font-size: 12px;
  color: var(--danger);
}
</style>
