<template>
  <div class="undercover-game">
    <div v-if="roomState.state === 'WAITING'" class="waiting-state">
      <div class="waiting-content">
        <h3 class="waiting-title">谁是卧底</h3>
        <p class="waiting-hint">等待房主开始游戏</p>

        <div class="player-count-bar">
          <span class="count-label">当前玩家</span>
          <span class="count-value">{{ playerCount }} 人</span>
        </div>

        <p v-if="aiMsg" class="ai-feedback">{{ aiMsg }}</p>

        <div v-if="isHost" class="waiting-actions">
          <Button size="sm" :loading="addingAI" @click="addAI">
            + 添加AI玩家
          </Button>
          <Button size="sm" variant="secondary" :loading="assigningWords" @click="assignWords">
            分配词语并开始
          </Button>
        </div>
        <p v-else class="waiting-hint">等待房主操作...</p>
      </div>
    </div>

    <div v-else-if="!isFinished" class="game-state">
      <div v-if="myWord" class="word-card">
        <span class="word-label">你的词语</span>
        <span class="word-value">{{ myWord }}</span>
        <span v-if="myRole" :class="['role-badge', myRole]">
          {{ myRole === 'undercover' ? '卧底' : '平民' }}
        </span>
      </div>

      <div v-if="ucState.phase === 'describing'" class="phase-section">
        <div class="phase-header">
          <span class="phase-label">描述阶段</span>
          <span class="phase-round">第 {{ ucState.round || 1 }} 轮</span>
        </div>

        <div v-if="isMyTurn" class="my-turn">
          <p class="turn-hint">轮到你描述了！</p>
          <div class="describe-form">
            <input
              v-model="describeInput"
              class="input-field"
              placeholder="输入你的描述..."
              @keydown.enter="submitDescribe"
            />
            <Button size="sm" :disabled="!describeInput.trim()" :loading="describing" @click="submitDescribe">
              提交
            </Button>
          </div>
        </div>
        <p v-else class="turn-hint waiting">
          等待 {{ currentTurnName }} 描述...
        </p>

        <div class="descriptions">
          <div v-for="d in descriptions" :key="d.uid" class="desc-item">
            <span class="desc-name">{{ d.nickname || d.username }}</span>
            <span class="desc-text">{{ d.description }}</span>
          </div>
        </div>
      </div>

      <div v-if="ucState.phase === 'voting'" class="phase-section">
        <div class="phase-header">
          <span class="phase-label">投票阶段</span>
        </div>
        <div class="player-grid">
          <button
            v-for="p in votablePlayers"
            :key="p.uid"
            :class="['vote-btn', { voted: votedTarget === p.uid }]"
            :disabled="hasVoted"
            @click="submitVote(p.uid)"
          >
            <Avatar :name="p.nickname || p.username" :size="32" />
            <span class="vote-name">{{ p.nickname || p.username }}</span>
          </button>
        </div>
      </div>

      <div class="vote-history">
        <div v-for="(vr, i) in voteResults" :key="i" class="vote-result-card">
          <span class="vr-round">第{{ vr.round }}轮</span>
          <span class="vr-eliminated">
            {{ vr.eliminated_name }} 被淘汰 — {{ vr.eliminated_role === 'undercover' ? '卧底' : '平民' }}
            （词语: {{ vr.eliminated_word }}）
          </span>
        </div>
      </div>
    </div>

    <div v-else class="finished-state">
      <div class="finished-content">
        <div :class="['result-icon', gameResult?.winner]">
          {{ gameResult?.winner === 'civilian' ? '平民获胜' : '卧底获胜' }}
        </div>
        <p v-if="gameResult?.undercover_name" class="result-detail">
          卧底是 {{ gameResult.undercover_name }}（词语: {{ gameResult.undercover_word }}）
        </p>
        <p class="result-detail">平民词语: {{ gameResult?.civilian_word }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useAuthStore } from '../../stores/auth.js'
import { api } from '../../utils/api.js'
import Button from '../common/Button.vue'
import Avatar from '../common/Avatar.vue'

const props = defineProps({
  roomState: { type: Object, default: () => ({}) },
  messages: { type: Array, default: () => [] },
})

const emit = defineEmits(['describe', 'vote', 'assign-words'])
const auth = useAuthStore()

const describeInput = ref('')
const addingAI = ref(false)
const assigningWords = ref(false)
const describing = ref(false)
const aiMsg = ref('')

const isHost = computed(() => auth.user?.uid === props.roomState.host_uid)
const playerCount = computed(() => (props.roomState.players || []).length)
const votedTarget = ref('')
const hasVoted = ref(false)
const myWord = ref('')
const myRole = ref('')

const ucState = computed(() => {
  const stateMsg = [...props.messages].reverse().find(m => m.type === 'undercover_state')
  return stateMsg || {}
})

const isMyTurn = computed(() => {
  const turn = ucState.value.current_turn
  if (!turn) return false
  return turn === auth.user?.uid || turn === auth.user?.username
})

const currentTurnName = computed(() => {
  const turn = ucState.value.current_turn
  if (!turn) return ''
  const p = (props.roomState.players || []).find(
    pl => pl.uid === turn || pl.username === turn
  )
  return p?.nickname || p?.username || turn
})

const descriptions = computed(() =>
  props.messages.filter(m => m.type === 'player_described')
)

const votablePlayers = computed(() => {
  return (props.roomState.players || []).filter(
    p => p.uid !== auth.user?.uid && p.username !== auth.user?.username
  )
})

const voteResults = computed(() =>
  props.messages.filter(m => m.type === 'vote_result')
)

const gameResult = computed(() =>
  [...props.messages].reverse().find(m => m.type === 'game_over')
)

const isFinished = computed(() => gameResult.value != null)

watch(() => props.messages.length, () => {
  const last = props.messages[props.messages.length - 1]
  if (last?.type === 'word_assigned') {
    myWord.value = last.word
    myRole.value = last.role
  }
  if (last?.type === 'vote_result') {
    hasVoted.value = false
    votedTarget.value = ''
  }
  if (last?.type === 'undercover_state') {
    hasVoted.value = false
    votedTarget.value = ''
  }
})

async function addAI() {
  addingAI.value = true
  aiMsg.value = ''
  try {
    const res = await api.addAI(props.roomState.room_id, 1)
    aiMsg.value = `已添加 ${res.added?.length || 1} 个AI玩家`
    setTimeout(() => { aiMsg.value = '' }, 3000)
  } catch (e) {
    aiMsg.value = e.message
  } finally {
    addingAI.value = false
  }
}

async function assignWords() {
  assigningWords.value = true
  try {
    emit('assign-words')
  } finally {
    assigningWords.value = false
  }
}

async function submitDescribe() {
  const desc = describeInput.value.trim()
  if (!desc) return
  describing.value = true
  try {
    await api.describeUndercover(props.roomState.room_id, desc)
    describeInput.value = ''
  } catch (e) {
    alert(e.message)
  } finally {
    describing.value = false
  }
}

async function submitVote(targetUid) {
  if (hasVoted.value) return
  hasVoted.value = true
  votedTarget.value = targetUid
  try {
    await api.voteUndercover(props.roomState.room_id, targetUid)
  } catch (e) {
    alert(e.message)
    hasVoted.value = false
    votedTarget.value = ''
  }
}
</script>

<style scoped>
.undercover-game {
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

.waiting-content {
  text-align: center;
}

.waiting-title {
  font-size: 20px;
  font-weight: 600;
}

.waiting-hint {
  font-size: 14px;
  color: var(--text-muted);
  margin-top: 8px;
}

.player-count-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  margin-top: 16px;
}

.count-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.count-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.ai-feedback {
  font-size: 13px;
  color: var(--success);
  margin-top: 8px;
}

.waiting-actions {
  display: flex;
  gap: 8px;
  margin-top: 24px;
  justify-content: center;
}

.game-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: 20px;
  gap: 16px;
}

.word-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
}

.word-label {
  font-size: 12px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.word-value {
  font-size: 28px;
  font-weight: 700;
  margin-top: 8px;
  letter-spacing: 2px;
}

.role-badge {
  margin-top: 8px;
  font-size: 12px;
  font-weight: 500;
  padding: 3px 12px;
  border-radius: 12px;
}

.role-badge.civilian {
  background: var(--accent-subtle);
  color: var(--accent);
}

.role-badge.undercover {
  background: var(--danger-subtle);
  color: var(--danger);
}

.phase-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.phase-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.phase-label {
  font-size: 14px;
  font-weight: 600;
}

.phase-round {
  font-size: 12px;
  color: var(--text-muted);
}

.turn-hint {
  font-size: 13px;
  color: var(--accent);
  font-weight: 500;
}

.turn-hint.waiting {
  color: var(--text-muted);
}

.describe-form {
  display: flex;
  gap: 8px;
  margin-top: 8px;
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

.descriptions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.desc-item {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  font-size: 13px;
}

.desc-name {
  color: var(--text-secondary);
  font-weight: 500;
  flex-shrink: 0;
}

.desc-text {
  color: var(--text-primary);
}

.player-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 8px;
}

.vote-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 8px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  transition: all var(--transition);
}

.vote-btn:hover:not(:disabled) {
  border-color: var(--accent);
  background: var(--accent-subtle);
}

.vote-btn.voted {
  border-color: var(--accent);
  background: var(--accent-subtle);
}

.vote-btn:disabled {
  opacity: 0.5;
}

.vote-name {
  font-size: 12px;
  font-weight: 500;
}

.vote-history {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.vote-result-card {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  font-size: 13px;
}

.vr-round {
  font-weight: 500;
  color: var(--text-muted);
  flex-shrink: 0;
}

.vr-eliminated {
  color: var(--text-secondary);
}

.finished-content {
  text-align: center;
}

.result-icon {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 16px;
}

.result-icon.civilian { color: var(--success); }
.result-icon.undercover { color: var(--danger); }

.result-detail {
  font-size: 14px;
  color: var(--text-secondary);
  margin-top: 4px;
}
</style>
