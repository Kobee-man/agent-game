<template>
  <Card class="room-list-card">
    <div class="list-header">
      <h3 class="panel-title">房间列表</h3>
      <Button variant="ghost" size="sm" :loading="loading" @click="$emit('refresh')">
        刷新
      </Button>
    </div>

    <div v-if="rooms.length === 0" class="empty">
      <p class="empty-text">暂无房间</p>
      <p class="empty-hint">创建一个房间开始游戏吧</p>
    </div>

    <div v-else class="rooms">
      <div
        v-for="room in rooms"
        :key="room.room_id"
        class="room-item"
        @click="$emit('join', room.room_id)"
      >
        <div class="room-info">
          <div class="room-top">
            <span class="room-game">{{ room.game_name || gameLabel(room.game_type) }}</span>
            <span :class="['room-state', room.state]">{{ stateLabel(room.state) }}</span>
          </div>
          <div class="room-id">{{ room.room_id }}</div>
        </div>
        <div class="room-meta">
          <span class="room-players">{{ (room.players || []).length }}人</span>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" class="arrow">
            <path d="M6 3l5 5-5 5" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" />
          </svg>
        </div>
      </div>
    </div>
  </Card>
</template>

<script setup>
import Card from '../common/Card.vue'
import Button from '../common/Button.vue'

defineProps({
  rooms: { type: Array, default: () => [] },
  loading: Boolean,
})

defineEmits(['refresh', 'join'])

function gameLabel(type) {
  return { turtle_soup: '海龟汤', undercover: '谁是卧底' }[type] || type
}

function stateLabel(state) {
  return { WAITING: '等待中', RUNNING: '游戏中', FINISHED: '已结束' }[state] || state
}
</script>

<style scoped>
.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
}

.empty {
  text-align: center;
  padding: 32px 0;
}

.empty-text {
  font-size: 14px;
  color: var(--text-secondary);
}

.empty-hint {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}

.rooms {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.room-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition);
}

.room-item:hover {
  background: var(--bg-tertiary);
}

.room-top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.room-game {
  font-size: 14px;
  font-weight: 500;
}

.room-state {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 4px;
}

.room-state.WAITING {
  background: var(--accent-subtle);
  color: var(--accent);
}

.room-state.RUNNING {
  background: var(--warning-subtle);
  color: var(--warning);
}

.room-state.FINISHED {
  background: var(--bg-elevated);
  color: var(--text-muted);
}

.room-id {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.room-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
}

.room-players {
  font-size: 13px;
}

.arrow {
  opacity: 0;
  transition: opacity var(--transition);
}

.room-item:hover .arrow {
  opacity: 1;
}
</style>
