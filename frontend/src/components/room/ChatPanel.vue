<template>
  <div class="chat-panel">
    <div ref="messagesRef" class="messages">
      <div
        v-for="(msg, i) in messages"
        :key="i"
        :class="['msg', msg.type]"
      >
        <template v-if="msg.type === 'system'">
          <span class="system-text">{{ msg.content }}</span>
        </template>
        <template v-else>
          <Avatar :name="msg.nickname || msg.username" :size="28" />
          <div class="msg-body">
            <div class="msg-header">
              <span class="msg-name">{{ msg.nickname || msg.username }}</span>
              <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
            </div>
            <p class="msg-content">{{ msg.content }}</p>
          </div>
        </template>
      </div>
    </div>

    <div class="chat-input">
      <input
        ref="inputRef"
        v-model="inputText"
        class="input-field"
        placeholder="发送消息..."
        @keydown.enter="send"
      />
      <button class="send-btn" :disabled="!inputText.trim()" @click="send">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="22" y1="2" x2="11" y2="13" />
          <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'
import Avatar from '../common/Avatar.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
})

const emit = defineEmits(['send'])

const inputText = ref('')
const messagesRef = ref(null)
const inputRef = ref(null)

function send() {
  const text = inputText.value.trim()
  if (!text) return
  emit('send', text)
  inputText.value = ''
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

watch(() => props.messages.length, () => {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
})
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.msg {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.msg.system {
  justify-content: center;
  padding: 4px 0;
}

.system-text {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-tertiary);
  padding: 4px 12px;
  border-radius: 12px;
}

.msg.judgment,
.msg.answer_result,
.msg.ai_reply {
  padding-left: 0;
}

.msg-body {
  flex: 1;
  min-width: 0;
}

.msg-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 2px;
}

.msg-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

.msg-time {
  font-size: 11px;
  color: var(--text-muted);
}

.msg-content {
  font-size: 14px;
  color: var(--text-primary);
  word-break: break-word;
  line-height: 1.5;
}

.chat-input {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}

.input-field {
  flex: 1;
  padding: 10px 14px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  transition: border-color var(--transition);
}

.input-field:focus {
  border-color: var(--accent);
}

.input-field::placeholder {
  color: var(--text-muted);
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  background: var(--accent);
  color: #fff;
  border-radius: var(--radius-md);
  transition: background var(--transition);
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
