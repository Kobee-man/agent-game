<template>
  <form @submit.prevent="handleRegister">
    <div class="form-fields">
      <Input
        v-model="username"
        label="用户名"
        placeholder="3-20位字母或数字"
        :error="errors.username"
      />
      <Input
        v-model="nickname"
        label="昵称（可选）"
        placeholder="你希望别人怎么称呼你"
      />
      <Input
        v-model="password"
        label="密码"
        type="password"
        placeholder="至少6位"
        :error="errors.password"
      />
      <Input
        v-model="confirmPassword"
        label="确认密码"
        type="password"
        placeholder="再次输入密码"
        :error="errors.confirmPassword"
        @enter="handleRegister"
      />
    </div>
    <p v-if="errors.general" class="form-error">{{ errors.general }}</p>
    <Button type="submit" block :loading="auth.loading" class="submit-btn">
      注册
    </Button>
    <div class="form-footer">
      <button type="button" class="link-btn" @click="$emit('switch', 'login')">已有账号？登录</button>
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
const nickname = ref('')
const password = ref('')
const confirmPassword = ref('')
const errors = reactive({ username: '', password: '', confirmPassword: '', general: '' })

function validate() {
  errors.username = ''
  errors.password = ''
  errors.confirmPassword = ''
  errors.general = ''
  let valid = true

  const u = username.value.trim()
  if (!u) { errors.username = '请输入用户名'; valid = false }
  else if (u.length < 3 || u.length > 20) { errors.username = '用户名长度3-20位'; valid = false }
  else if (!/^[a-zA-Z0-9]+$/.test(u)) { errors.username = '用户名只能包含字母和数字'; valid = false }

  if (!password.value) { errors.password = '请输入密码'; valid = false }
  else if (password.value.length < 6) { errors.password = '密码至少6位'; valid = false }

  if (password.value !== confirmPassword.value) { errors.confirmPassword = '两次密码不一致'; valid = false }

  return valid
}

async function handleRegister() {
  if (!validate()) return
  try {
    await auth.register(username.value.trim(), password.value, nickname.value.trim() || undefined)
  } catch (e) {
    errors.general = e.message || '注册失败'
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
