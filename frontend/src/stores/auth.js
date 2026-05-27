import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../utils/api.js'
import router from '../router/index.js'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(null)
  const loading = ref(false)

  const isLoggedIn = computed(() => !!token.value)

  function setToken(t) {
    token.value = t
    localStorage.setItem('token', t)
  }

  async function login(username, password) {
    loading.value = true
    try {
      const data = await api.login(username, password)
      setToken(data.access_token)
      await fetchProfile()
      router.push('/lobby')
    } finally {
      loading.value = false
    }
  }

  async function register(username, password, nickname) {
    loading.value = true
    try {
      await api.register(username, password, nickname)
      const data = await api.login(username, password)
      setToken(data.access_token)
      await fetchProfile()
      router.push('/lobby')
    } finally {
      loading.value = false
    }
  }

  async function forgotPassword(username, newPassword) {
    loading.value = true
    try {
      await api.forgotPassword(username, newPassword)
    } finally {
      loading.value = false
    }
  }

  async function fetchProfile() {
    if (!token.value) return
    try {
      user.value = await api.getProfile()
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    router.push('/')
  }

  return { token, user, loading, isLoggedIn, login, register, forgotPassword, fetchProfile, logout }
})
