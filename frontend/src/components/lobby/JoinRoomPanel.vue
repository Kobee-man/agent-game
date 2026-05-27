<template>
  <Card class="join-panel">
    <h3 class="panel-title">加入房间</h3>
    <div class="join-form">
      <Input
        v-model="roomId"
        placeholder="输入房间号"
        @enter="handleJoin"
      />
      <Button :loading="loading" @click="handleJoin">加入</Button>
    </div>
    <p v-if="error" class="join-error">{{ error }}</p>
  </Card>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../../utils/api.js'
import Card from '../common/Card.vue'
import Input from '../common/Input.vue'
import Button from '../common/Button.vue'

const router = useRouter()
const roomId = ref('')
const loading = ref(false)
const error = ref('')

async function handleJoin() {
  const id = roomId.value.trim()
  if (!id) { error.value = '请输入房间号'; return }
  error.value = ''
  loading.value = true
  try {
    await api.joinRoom(id)
    router.push(`/room/${id}`)
  } catch (e) {
    error.value = e.message || '加入失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.panel-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
}

.join-form {
  display: flex;
  gap: 8px;
}

.join-form :deep(.input-group) {
  flex: 1;
}

.join-error {
  margin-top: 8px;
  font-size: 12px;
  color: var(--danger);
}
</style>
