<template>
  <form @submit.prevent="handleReset">
    <div class="form-fields">
      <Input
        v-model="username"
        label="用户名"
        placeholder="请输入你的用户名"
        :error="errors.username"
      />
      <Input
        v-model="newPassword"
        label="新密码"
        type="password"
        placeholder="至少6位"
        :error="errors.newPassword"
      />
      <Input
        v-model="confirmPassword"
        label="确认新密码"
        type="password"
        placeholder="再次输入新密码"
        :error="errors.confirmPassword"
        @enter="handleReset"
      />
    </div>
    <p v-if="message" :class="['form-message', success ? 'success' : 'error']">{{ message }}</p>
    <Button type="submit" block :loading="auth.loading" class="submit-btn">
      重置密码
    </Button>
    <div class="form-footer">
      <button type="button" class="link-btn" @click="$emit('switch', 'login')">返回登录</button>
    </div>
  </form>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useAuthStore } from '../../stores/auth.js'
import Input from '../common/Input.vue'
import Button from '../common/Button.vue'

const emit = defineEmits(['switch'])
const auth = useAuthStore()

const username = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const message = ref('')
const success = ref(false)
const errors = reactive({ username: '', newPassword: '', confirmPassword: '' })

function validate() {
  errors.username = ''
  errors.newPassword = ''
  errors.confirmPassword = ''
  message.value = ''
  let valid = true

  if (!username.value.trim()) { errors.username = '请输入用户名'; valid = false }
  if (!newPassword.value) { errors.newPassword = '请输入新密码'; valid = false }
  else if (newPassword.value.length < 6) { errors.newPassword = '密码至少6位'; valid = false }
  if (newPassword.value !== confirmPassword.value) { errors.confirmPassword = '两次密码不一致'; valid = false }

  return valid
}

async function handleReset() {
  if (!validate()) return
  try {
    await auth.forgotPassword(username.value.trim(), newPassword.value)
    success.value = true
    message.value = '密码重置成功，请登录'
  } catch (e) {
    success.value = false
    message.value = e.message || '重置失败'
  }
}
</script>

<style scoped>
.form-fields {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-message {
  margin-top: 12px;
  font-size: 13px;
  text-align: center;
}

.form-message.success { color: var(--success); }
.form-message.error { color: var(--danger); }

.submit-btn {
  margin-top: 24px;
}

.form-footer {
  margin-top: 16px;
  text-align: center;
}

.link-btn {
  font-size: 13px;
  color: var(--text-muted);
  transition: color var(--transition);
}

.link-btn:hover {
  color: var(--accent);
}
</style>
