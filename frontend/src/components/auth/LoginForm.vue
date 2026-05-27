<template>
  <form @submit.prevent="handleLogin">
    <div class="form-fields">
      <Input
        v-model="username"
        label="用户名"
        placeholder="请输入用户名"
        :error="errors.username"
        @enter="handleLogin"
      />
      <Input
        v-model="password"
        label="密码"
        type="password"
        placeholder="请输入密码"
        :error="errors.password"
        @enter="handleLogin"
      />
    </div>
    <p v-if="errors.general" class="form-error">{{ errors.general }}</p>
    <Button type="submit" block :loading="auth.loading" class="submit-btn">
      登录
    </Button>
    <div class="form-footer">
      <button type="button" class="link-btn" @click="$emit('switch', 'forgot')">忘记密码？</button>
      <button type="button" class="link-btn" @click="$emit('switch', 'register')">创建账号</button>
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
const password = ref('')
const errors = reactive({ username: '', password: '', general: '' })

function validate() {
  errors.username = ''
  errors.password = ''
  errors.general = ''
  let valid = true
  if (!username.value.trim()) { errors.username = '请输入用户名'; valid = false }
  if (!password.value) { errors.password = '请输入密码'; valid = false }
  return valid
}

async function handleLogin() {
  if (!validate()) return
  try {
    await auth.login(username.value.trim(), password.value)
  } catch (e) {
    errors.general = e.message || '登录失败'
  }
}
</script>

<style scoped>
.form-fields {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-error {
  margin-top: 12px;
  font-size: 13px;
  color: var(--danger);
  text-align: center;
}

.submit-btn {
  margin-top: 24px;
}

.form-footer {
  display: flex;
  justify-content: space-between;
  margin-top: 16px;
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
