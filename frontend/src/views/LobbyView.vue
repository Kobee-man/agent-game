<template>
  <div class="lobby-page">
    <header class="lobby-header">
      <div class="header-left">
        <h1 class="logo">海龟汤</h1>
      </div>
      <div class="header-right">
        <div class="user-info">
          <Avatar :name="auth.user?.nickname || auth.user?.username" :size="32" />
          <span class="user-name">{{ auth.user?.nickname || auth.user?.username }}</span>
        </div>
        <Button variant="ghost" size="sm" @click="auth.logout()">退出</Button>
      </div>
    </header>

    <div v-if="myRoom" class="room-banner">
      <div class="banner-info">
        <span class="banner-label">你正在房间中</span>
        <span class="banner-room">{{ myRoom.game_name }} · {{ myRoom.room_id }}</span>
      </div>
      <div class="banner-actions">
        <Button size="sm" @click="$router.push(`/room/${myRoom.room_id}`)">返回房间</Button>
        <Button size="sm" variant="danger" :loading="leavingRoom" @click="leaveCurrentRoom">离开</Button>
      </div>
    </div>

    <main class="lobby-main">
      <div class="lobby-grid">
        <div class="lobby-left">
          <CreateRoomPanel />
          <JoinRoomPanel />
        </div>
        <div class="lobby-right">
          <RoomList :rooms="rooms" :loading="refreshing" @refresh="fetchRooms" @join="joinRoom" />
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { api } from '../utils/api.js'
import Avatar from '../components/common/Avatar.vue'
import Button from '../components/common/Button.vue'
import CreateRoomPanel from '../components/lobby/CreateRoomPanel.vue'
import JoinRoomPanel from '../components/lobby/JoinRoomPanel.vue'
import RoomList from '../components/lobby/RoomList.vue'

const auth = useAuthStore()
const router = useRouter()
const rooms = ref([])
const myRoom = ref(null)
const refreshing = ref(false)
const leavingRoom = ref(false)
let pollTimer = null

async function fetchRooms() {
  refreshing.value = true
  try {
    const data = await api.getRooms()
    rooms.value = data.rooms || []
  } catch {
    // silent
  } finally {
    refreshing.value = false
  }
}

async function checkMyRoom() {
  try {
    const data = await api.getMyRoom()
    myRoom.value = data.in_room ? data : null
  } catch {
    myRoom.value = null
  }
}

async function joinRoom(roomId) {
  try {
    await api.joinRoom(roomId)
    router.push(`/room/${roomId}`)
  } catch (e) {
    alert(e.message)
  }
}

async function leaveCurrentRoom() {
  leavingRoom.value = true
  try {
    await api.leaveRoom()
    myRoom.value = null
  } catch (e) {
    alert(e.message)
  } finally {
    leavingRoom.value = false
  }
}

onMounted(async () => {
  if (!auth.user) await auth.fetchProfile()
  checkMyRoom()
  fetchRooms()
  pollTimer = setInterval(() => {
    fetchRooms()
    checkMyRoom()
  }, 10000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.lobby-page {
  min-height: 100vh;
  background: var(--bg-primary);
}

.room-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 32px;
  background: var(--accent-subtle);
  border-bottom: 1px solid rgba(99, 102, 241, 0.2);
}

.banner-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.banner-label {
  font-size: 12px;
  color: var(--accent);
  font-weight: 500;
}

.banner-room {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.banner-actions {
  display: flex;
  gap: 8px;
}

.lobby-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 32px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-secondary);
}

.logo {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.3px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
}

.lobby-main {
  max-width: 960px;
  margin: 0 auto;
  padding: 32px 24px;
}

.lobby-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  align-items: start;
}

.lobby-left {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

@media (max-width: 768px) {
  .lobby-grid {
    grid-template-columns: 1fr;
  }

  .lobby-header {
    padding: 12px 16px;
  }

  .lobby-main {
    padding: 16px;
  }
}
</style>
