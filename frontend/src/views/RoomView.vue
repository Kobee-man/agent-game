<template>
  <div class="room-page">
    <header class="room-header">
      <button class="back-btn" @click="goBack">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
      </button>
      <span class="room-title">{{ roomState.game_name || '游戏房间' }}</span>
      <span class="room-id-badge">{{ route.params.id }}</span>
      <div class="header-spacer" />
      <span :class="['conn-status', connected ? 'online' : 'offline']">
        {{ connected ? '已连接' : '连接中...' }}
      </span>
    </header>

    <div class="room-body">
      <aside class="room-sidebar">
        <RoomSidebar
          :room-state="roomState"
          :starting="starting"
          @start="startGame"
          @leave="leaveRoom"
          @destroy="destroyRoom"
        />
      </aside>

      <main class="room-main">
        <div class="game-area">
          <SoupGame
            v-if="gameType === 'turtle_soup'"
            :room-state="roomState"
            :messages="messages"
            @ask="sendAsk"
            @answer="sendAnswer"
            @hint="sendHint"
          />
          <UndercoverGame
            v-else-if="gameType === 'undercover'"
            :room-state="roomState"
            :messages="messages"
            @assign-words="sendAssignWords"
          />
        </div>

        <div class="chat-area">
          <ChatPanel :messages="chatMessages" @send="sendChat" />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { api, getWsUrl } from '../utils/api.js'
import RoomSidebar from '../components/room/RoomSidebar.vue'
import ChatPanel from '../components/room/ChatPanel.vue'
import SoupGame from '../components/room/SoupGame.vue'
import UndercoverGame from '../components/room/UndercoverGame.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const messages = ref([])
const roomState = ref({})
const connected = ref(false)
const starting = ref(false)
let ws = null

const gameType = computed(() => roomState.value.game_type || 'turtle_soup')

const chatMessages = computed(() =>
  messages.value.filter(m => ['message', 'system', 'ai_reply'].includes(m.type))
)

function connect() {
  const token = localStorage.getItem('token')
  const roomId = route.params.id
  ws = new WebSocket(getWsUrl(`/api/room/ws/${roomId}/${token}`))

  ws.onopen = () => { connected.value = true }

  ws.onmessage = (e) => {
    const data = JSON.parse(e.data)
    if (data.type === 'room_state') {
      const wsPlayers = data.players || []
      const existingPlayers = roomState.value.players || []
      const mergedPlayers = wsPlayers.map((p, i) => {
        if (typeof p === 'string') {
          const match = existingPlayers.find(ep => ep.username === p || ep.nickname === p)
          return match || { uid: p, username: p, nickname: p }
        }
        return p
      })
      roomState.value = {
        ...roomState.value,
        state: data.state,
        puzzle_title: data.puzzle_title,
        players: mergedPlayers,
        question_count: data.question_count,
        max_questions: data.max_questions,
        room_id: roomId,
      }
    } else {
      messages.value.push(data)
      if (data.type === 'error') {
        // errors shown inline in game components
      }
    }
  }

  ws.onclose = () => { connected.value = false }
  ws.onerror = () => { connected.value = false }
}

function sendWs(data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data))
  }
}

function sendChat(content) {
  sendWs({ action: 'chat', content })
}

function sendAsk(question) {
  sendWs({ action: 'ask', content: question })
}

function sendAnswer(answer) {
  sendWs({ action: 'answer', content: answer })
}

function sendHint() {
  sendWs({ action: 'hint', content: 'hint' })
}

function sendAssignWords() {
  sendWs({ action: 'assign-words' })
}

async function startGame() {
  starting.value = true
  try {
    await api.startRoom(route.params.id)
  } catch (e) {
    alert(e.message)
  } finally {
    starting.value = false
  }
}

async function leaveRoom() {
  try {
    await api.leaveRoom()
  } catch {
    // ignore
  }
  if (ws) ws.close()
  router.push('/lobby')
}

async function destroyRoom() {
  if (!confirm('确定要解散房间吗？所有玩家将被移除。')) return
  try {
    await api.destroyRoom()
  } catch (e) {
    alert(e.message)
    return
  }
  if (ws) ws.close()
  router.push('/lobby')
}

function goBack() {
  if (ws) ws.close()
  router.push('/lobby')
}

onMounted(async () => {
  if (!auth.user) await auth.fetchProfile()
  try {
    const status = await api.getRoomStatus(route.params.id)
    roomState.value = status
  } catch {
    // room might not exist yet
  }
  connect()
})

onUnmounted(() => {
  if (ws) ws.close()
})
</script>

<style scoped>
.room-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-primary);
}

.room-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-secondary);
  flex-shrink: 0;
}

.back-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  transition: all var(--transition);
}

.back-btn:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.room-title {
  font-size: 15px;
  font-weight: 600;
}

.room-id-badge {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-tertiary);
  padding: 3px 8px;
  border-radius: 6px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.header-spacer {
  flex: 1;
}

.conn-status {
  font-size: 12px;
  font-weight: 500;
}

.conn-status.online { color: var(--success); }
.conn-status.offline { color: var(--danger); }

.room-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

.room-sidebar {
  width: 240px;
  border-right: 1px solid var(--border);
  background: var(--bg-secondary);
  flex-shrink: 0;
  overflow-y: auto;
}

.room-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.game-area {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-area {
  height: 240px;
  border-top: 1px solid var(--border);
  background: var(--bg-secondary);
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .room-body {
    flex-direction: column;
  }

  .room-sidebar {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid var(--border);
    max-height: 200px;
  }

  .chat-area {
    height: 180px;
  }
}
</style>
