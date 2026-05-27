<template>
  <div class="login-page">
    <div class="login-container">
      <div class="brand">
        <div class="brand-icon">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
            <circle cx="16" cy="16" r="14" stroke="var(--accent)" stroke-width="2.5" />
            <path d="M12 13c0-2.2 1.8-4 4-4s4 1.8 4 4c0 1.5-.8 2.8-2 3.5V19" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" />
            <circle cx="16" cy="23" r="1.5" fill="var(--accent)" />
          </svg>
        </div>
        <h1 class="brand-title">海龟汤</h1>
        <p class="brand-subtitle">推理 · 解谜 · 智斗</p>
      </div>

      <div class="auth-card">
        <div class="tab-bar">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            :class="['tab', { active: activeTab === tab.key }]"
            @click="activeTab = tab.key"
          >
            {{ tab.label }}
          </button>
          <div class="tab-indicator" :style="indicatorStyle" />
        </div>

        <div class="tab-content">
          <Transition name="slide-up" mode="out-in">
            <LoginForm v-if="activeTab === 'login'" key="login" @switch="activeTab = $event" />
            <RegisterForm v-else-if="activeTab === 'register'" key="register" @switch="activeTab = $event" />
            <ForgotPasswordForm v-else key="forgot" @switch="activeTab = $event" />
          </Transition>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import LoginForm from '../components/auth/LoginForm.vue'
import RegisterForm from '../components/auth/RegisterForm.vue'
import ForgotPasswordForm from '../components/auth/ForgotPasswordForm.vue'

const tabs = [
  { key: 'login', label: '登录' },
  { key: 'register', label: '注册' },
  { key: 'forgot', label: '重置' },
]

const activeTab = ref('login')

const indicatorStyle = computed(() => {
  const idx = tabs.findIndex(t => t.key === activeTab.value)
  return { left: `${idx * 33.333}%` }
})
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(ellipse 600px 400px at 50% 0%, rgba(99, 102, 241, 0.08), transparent),
    var(--bg-primary);
}

.login-container {
  width: 100%;
  max-width: 400px;
}

.brand {
  text-align: center;
  margin-bottom: 40px;
}

.brand-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  background: var(--accent-subtle);
  border-radius: 16px;
  margin-bottom: 16px;
}

.brand-title {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.5px;
}

.brand-subtitle {
  margin-top: 4px;
  font-size: 14px;
  color: var(--text-muted);
  letter-spacing: 2px;
}

.auth-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.tab-bar {
  display: flex;
  position: relative;
  border-bottom: 1px solid var(--border);
}

.tab {
  flex: 1;
  padding: 14px 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-muted);
  transition: color var(--transition);
  text-align: center;
}

.tab.active {
  color: var(--text-primary);
}

.tab-indicator {
  position: absolute;
  bottom: 0;
  width: 33.333%;
  height: 2px;
  background: var(--accent);
  transition: left 0.25s ease;
  border-radius: 1px;
}

.tab-content {
  padding: 24px;
}
</style>
