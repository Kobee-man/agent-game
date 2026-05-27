const API_BASE = '/api'

class ApiError extends Error {
  constructor(status, detail) {
    super(detail)
    this.status = status
  }
}

async function request(path, options = {}) {
  const token = localStorage.getItem('token')
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  const data = await res.json().catch(() => ({}))

  if (!res.ok) {
    throw new ApiError(res.status, data.detail || '请求失败')
  }
  return data
}

export const api = {
  register: (username, password, nickname) =>
    request('/register', { method: 'POST', body: JSON.stringify({ username, password, nickname }) }),

  login: (username, password) =>
    request('/login', { method: 'POST', body: JSON.stringify({ username, password }) }),

  forgotPassword: (username, new_password) =>
    request('/forgot-password', { method: 'POST', body: JSON.stringify({ username, new_password }) }),

  getProfile: () => request('/profile'),

  getRooms: () => request('/room/list'),

  getMyRoom: () => request('/room/my-room'),

  getGames: () => request('/room/games'),

  createRoom: (opts = {}) =>
    request('/room/create', { method: 'POST', body: JSON.stringify(opts) }),

  joinRoom: (roomId) =>
    request('/room/join', { method: 'POST', body: JSON.stringify({ room_id: roomId }) }),

  leaveRoom: () =>
    request('/room/leave', { method: 'POST', body: JSON.stringify({}) }),

  destroyRoom: () =>
    request('/room/destroy', { method: 'POST', body: JSON.stringify({}) }),

  startRoom: (roomId) =>
    request('/room/start', { method: 'POST', body: JSON.stringify({ room_id: roomId }) }),

  getRoomStatus: (roomId) => request(`/room/status/${roomId}`),

  addAI: (roomId, count = 1) =>
    request('/undercover/add-ai', { method: 'POST', body: JSON.stringify({ room_id: roomId, count }) }),

  startUndercover: (roomId) =>
    request('/undercover/start', { method: 'POST', body: JSON.stringify({ room_id: roomId }) }),

  describeUndercover: (roomId, description) =>
    request('/undercover/describe', { method: 'POST', body: JSON.stringify({ room_id: roomId, description }) }),

  voteUndercover: (roomId, targetUid) =>
    request('/undercover/vote', { method: 'POST', body: JSON.stringify({ room_id: roomId, target_uid: targetUid }) }),

  getUndercoverStatus: (roomId) => request(`/undercover/status/${roomId}`),

  getUndercoverRules: () => request('/undercover/rules'),

  getSoupRules: () => request('/turtle-soup/rules'),
}

export function getWsUrl(path) {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}${path}`
}
