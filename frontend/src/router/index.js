import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const routes = [
  {
    path: '/',
    name: 'login',
    component: () => import('../views/LoginView.vue')
  },
  {
    path: '/lobby',
    name: 'lobby',
    component: () => import('../views/LobbyView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/room/:id',
    name: 'room',
    component: () => import('../views/RoomView.vue'),
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.token) {
    return { name: 'login' }
  }
  if (to.name === 'login' && auth.token) {
    return { name: 'lobby' }
  }
})

export default router
