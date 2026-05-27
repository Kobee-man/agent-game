<template>
  <Card class="create-panel">
    <h3 class="panel-title">创建房间</h3>
    <div class="form-fields">
      <div class="field">
        <label class="field-label">游戏类型</label>
        <div class="game-select">
          <button
            v-for="g in games"
            :key="g.key"
            :class="['game-option', { active: selectedGame === g.key }]"
            @click="selectedGame = g.key"
          >
            <span class="game-name">{{ g.name }}</span>
            <span class="game-desc">{{ g.desc }}</span>
          </button>
        </div>
      </div>
      <div class="field">
        <label class="field-label">难度</label>
        <div class="chip-group">
          <button
            v-for="d in difficulties"
            :key="d.value"
            :class="['chip', { active: selectedDifficulty === d.value }]"
            @click="selectedDifficulty = d.value"
          >
            {{ d.label }}
          </button>
        </div>
      </div>
      <div class="row">
        <div class="field">
          <label class="field-label">最多提问数</label>
          <input v-model.number="maxQuestions" type="number" class="num-input" min="5" max="50" />
        </div>
        <div class="field">
          <label class="field-label">最大人数</label>
          <input v-model.number="maxPlayers" type="number" class="num-input" min="1" max="10" />
        </div>
      </div>
    </div>
    <Button block :loading="loading" @click="handleCreate">创建房间</Button>
  </Card>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../../utils/api.js'
import Card from '../common/Card.vue'
import Button from '../common/Button.vue'

const router = useRouter()
const loading = ref(false)

const games = [
  { key: 'turtle_soup', name: '海龟汤', desc: '推理猜谜' },
  { key: 'undercover', name: '谁是卧底', desc: '语言博弈' },
]

const difficulties = [
  { value: 'easy', label: '简单' },
  { value: 'medium', label: '中等' },
  { value: 'hard', label: '困难' },
]

const selectedGame = ref('turtle_soup')
const selectedDifficulty = ref('medium')
const maxQuestions = ref(20)
const maxPlayers = ref(4)

async function handleCreate() {
  loading.value = true
  try {
    const data = await api.createRoom({
      game_type: selectedGame.value,
      difficulty: selectedDifficulty.value,
      max_questions: maxQuestions.value,
      max_players: maxPlayers.value,
    })
    router.push(`/room/${data.room_id}`)
  } catch (e) {
    alert(e.message)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.panel-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 20px;
}

.form-fields {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 20px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.game-select {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.game-option {
  display: flex;
  flex-direction: column;
  padding: 12px 16px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  text-align: left;
  transition: all var(--transition);
}

.game-option:hover {
  border-color: var(--border-hover);
}

.game-option.active {
  border-color: var(--accent);
  background: var(--accent-subtle);
}

.game-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.game-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

.chip-group {
  display: flex;
  gap: 8px;
}

.chip {
  flex: 1;
  padding: 8px 0;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  text-align: center;
  transition: all var(--transition);
}

.chip:hover {
  border-color: var(--border-hover);
}

.chip.active {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-subtle);
}

.num-input {
  width: 100%;
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  text-align: center;
  transition: border-color var(--transition);
}

.num-input:focus {
  border-color: var(--accent);
}
</style>
