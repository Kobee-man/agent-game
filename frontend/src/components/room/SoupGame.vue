<template>
  <div class="soup-game">
    <div v-if="roomState.state === 'WAITING'" class="waiting-state">
      <div class="waiting-content">
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none" class="waiting-icon">
          <circle cx="24" cy="24" r="20" stroke="var(--accent)" stroke-width="2" stroke-dasharray="4 4" />
          <circle cx="24" cy="24" r="3" fill="var(--accent)" />
        </svg>
        <h3 class="waiting-title">等待开始</h3>
        <p class="waiting-hint">房主点击"开始游戏"后，AI将生成谜题</p>
      </div>
    </div>

    <div v-else-if="roomState.state === 'RUNNING'" class="running-state">
      <div v-if="roomState.puzzle_title" class="puzzle-header">
        <h3 class="puzzle-title">{{ roomState.puzzle_title }}</h3>
        <span class="question-counter">
          {{ roomState.question_count || 0 }} / {{ roomState.max_questions || 20 }} 提问
        </span>
      </div>

      <div ref="historyRef" class="history">
        <div
          v-for="(msg, i) in gameMessages"
          :key="i"
          :class="['history-item', msg.type]"
        >
          <template v-if="msg.type === 'judgment'">
            <div class="judgment-card">
              <div class="judgment-q">Q: {{ msg.question }}</div>
              <div :class="['judgment-a', msg.answer]">
                <span class="judgment-label">{{ answerLabel(msg.answer) }}</span>
                <span v-if="msg.reason" class="judgment-reason">{{ msg.reason }}</span>
              </div>
            </div>
          </template>
          <template v-else-if="msg.type === 'answer_result'">
            <div :class="['answer-card', msg.correct ? 'correct' : 'wrong']">
              <span class="answer-label">{{ msg.correct ? '回答正确！' : '回答错误' }}</span>
              <span class="answer-content">{{ msg.content }}</span>
            </div>
          </template>
          <template v-else-if="msg.type === 'system'">
            <span class="system-text">{{ msg.content }}</span>
          </template>
        </div>
      </div>

      <div class="action-bar">
        <div class="action-row">
          <input
            v-model="questionInput"
            class="input-field"
            placeholder="提出一个是/否问题..."
            @keydown.enter="askQuestion"
          />
          <Button size="sm" :disabled="!questionInput.trim() || atLimit" @click="askQuestion">
            提问
          </Button>
        </div>
        <div class="action-row">
          <input
            v-model="answerInput"
            class="input-field"
            placeholder="输入你的最终答案..."
            @keydown.enter="submitAnswer"
          />
          <Button variant="secondary" size="sm" :disabled="!answerInput.trim()" @click="submitAnswer">
            答题
          </Button>
          <Button variant="ghost" size="sm" @click="$emit('hint')">
            提示
          </Button>
        </div>
      </div>
    </div>

    <div v-else-if="roomState.state === 'FINISHED'" class="finished-state">
      <div class="finished-content">
        <div class="finished-icon">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
            <circle cx="24" cy="24" r="20" stroke="var(--success)" stroke-width="2.5" />
            <path d="M16 24l5 5 11-11" stroke="var(--success)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </div>
        <h3 class="finished-title">游戏结束</h3>
        <p v-if="winnerName" class="finished-winner">{{ winnerName }} 找到了答案！</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import Button from '../common/Button.vue'

const props = defineProps({
  roomState: { type: Object, default: () => ({}) },
  messages: { type: Array, default: () => [] },
})

const emit = defineEmits(['ask', 'answer', 'hint'])

const questionInput = ref('')
const answerInput = ref('')
const historyRef = ref(null)

const gameMessages = computed(() =>
  props.messages.filter(m => ['judgment', 'answer_result', 'game_over', 'system'].includes(m.type))
)

const atLimit = computed(() => {
  const { question_count = 0, max_questions = 20 } = props.roomState
  return question_count >= max_questions
})

const winnerName = computed(() => {
  const last = [...props.messages].reverse().find(m => m.type === 'game_over')
  return last?.winner_name || ''
})

function answerLabel(a) {
  return { yes: '是', no: '否', irrelevant: '无关' }[a] || a
}

function askQuestion() {
  const q = questionInput.value.trim()
  if (!q || atLimit.value) return
  emit('ask', q)
  questionInput.value = ''
}

function submitAnswer() {
  const a = answerInput.value.trim()
  if (!a) return
  emit('answer', a)
  answerInput.value = ''
}

watch(() => gameMessages.value.length, () => {
  nextTick(() => {
    if (historyRef.value) {
      historyRef.value.scrollTop = historyRef.value.scrollHeight
    }
  })
})
</script>

<style scoped>
.soup-game {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.waiting-state,
.finished-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.waiting-content,
.finished-content {
  text-align: center;
}

.waiting-icon {
  animation: spin 8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.waiting-title,
.finished-title {
  font-size: 18px;
  font-weight: 600;
  margin-top: 16px;
}

.waiting-hint {
  font-size: 14px;
  color: var(--text-muted);
  margin-top: 8px;
}

.finished-winner {
  font-size: 14px;
  color: var(--success);
  margin-top: 8px;
}

.running-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.puzzle-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.puzzle-title {
  font-size: 16px;
  font-weight: 600;
}

.question-counter {
  font-size: 13px;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.history {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item.system {
  text-align: center;
}

.system-text {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-tertiary);
  padding: 4px 12px;
  border-radius: 12px;
  display: inline-block;
}

.judgment-card {
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  padding: 12px 16px;
}

.judgment-q {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.judgment-a {
  display: flex;
  align-items: center;
  gap: 8px;
}

.judgment-label {
  font-size: 13px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
}

.judgment-a.yes .judgment-label { background: var(--success-subtle); color: var(--success); }
.judgment-a.no .judgment-label { background: var(--danger-subtle); color: var(--danger); }
.judgment-a.irrelevant .judgment-label { background: var(--bg-elevated); color: var(--text-muted); }

.judgment-reason {
  font-size: 12px;
  color: var(--text-muted);
}

.answer-card {
  padding: 12px 16px;
  border-radius: var(--radius-md);
}

.answer-card.correct {
  background: var(--success-subtle);
}

.answer-card.wrong {
  background: var(--danger-subtle);
}

.answer-label {
  font-size: 13px;
  font-weight: 600;
  display: block;
  margin-bottom: 4px;
}

.answer-card.correct .answer-label { color: var(--success); }
.answer-card.wrong .answer-label { color: var(--danger); }

.answer-content {
  font-size: 13px;
  color: var(--text-secondary);
}

.action-bar {
  padding: 16px 20px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.action-row {
  display: flex;
  gap: 8px;
}

.input-field {
  flex: 1;
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: border-color var(--transition);
}

.input-field:focus {
  border-color: var(--accent);
}

.input-field::placeholder {
  color: var(--text-muted);
}
</style>
