<template>
  <div class="sidebar">
    <div class="sidebar-section">
      <h4 class="section-title">房间信息</h4>
      <div class="info-row">
        <span class="info-label">房间号</span>
        <span class="info-value mono">{{ roomState.room_id }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">游戏</span>
        <span class="info-value">{{ gameName }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">状态</span>
        <span :class="['info-value', 'state', roomState.state]">{{ stateLabel }}</span>
      </div>
      <div v-if="roomState.puzzle_title" class="info-row">
        <span class="info-label">谜题</span>
        <span class="info-value">{{ roomState.puzzle_title }}</span>
      </div>
      <div v-if="roomState.max_questions" class="info-row">
        <span class="info-label">提问</span>
        <span class="info-value">{{ roomState.question_count || 0 }} / {{ roomState.max_questions }}</span>
      </div>
    </div>

    <div class="sidebar-section">
      <h4 class="section-title">玩家 ({{ players.length }})</h4>
      <div class="player-list">
        <div v-for="p in players" :key="p.uid" class="player-item">
          <Avatar :name="p.nickname || p.username" :size="28" />
          <span class="player-name">{{ p.nickname || p.username }}</span>
          <span v-if="p.uid === roomState.host_uid" class="host-badge">房主</span>
        </div>
      </div>
    </div>

    <div class="sidebar-actions">
      <Button
        v-if="isHost && roomState.state === 'WAITING'"
        size="sm"
        block
        :loading="starting"
        @click="$emit('start')"
      >
        开始游戏
      </Button>
      <Button
        v-if="isHost"
        variant="danger"
        size="sm"
        block
        @click="$emit('destroy')"
      >
        解散房间
      </Button>
      <Button variant="secondary" size="sm" block @click="$emit('leave')">
        离开房间
      </Button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAuthStore } from '../../stores/auth.js'
import Avatar from '../common/Avatar.vue'
import Button from '../common/Button.vue'

const props = defineProps({
  roomState: { type: Object, default: () => ({}) },
  starting: Boolean,
})

defineEmits(['start', 'leave', 'destroy'])

const auth = useAuthStore()

const players = computed(() => {
  return (props.roomState.players || []).map((p, i) => {
    if (typeof p === 'string') {
      return { uid: `player-${i}`, username: p, nickname: p }
    }
    return { uid: p.uid || p.username || `player-${i}`, ...p }
  })
})

const isHost = computed(() => {
  return auth.user?.uid === props.roomState.host_uid
})

const gameName = computed(() => {
  const map = { turtle_soup: '海龟汤', undercover: '谁是卧底' }
  return map[props.roomState.game_type] || props.roomState.game_type || '-'
})

const stateLabel = computed(() => {
  const map = { WAITING: '等待中', RUNNING: '游戏中', PROCESSING: '处理中', FINISHED: '已结束' }
  return map[props.roomState.state] || props.roomState.state
})
</script>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 20px;
  gap: 20px;
  overflow-y: auto;
}

.sidebar-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}

.info-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}

.info-label {
  color: var(--text-muted);
}

.info-value {
  color: var(--text-primary);
}

.info-value.mono {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
}

.state.WAITING { color: var(--accent); }
.state.RUNNING { color: var(--warning); }
.state.FINISHED { color: var(--text-muted); }

.player-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.player-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
}

.player-item:hover {
  background: var(--bg-tertiary);
}

.player-name {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
}

.host-badge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--warning-subtle);
  color: var(--warning);
  font-weight: 500;
}

.sidebar-actions {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
