/**
 * Centralized API calls. Every function returns { data, error } — components
 * never touch fetch() directly.
 */

const BASE = '/api'

async function request(path, options = {}) {
  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      return { data: null, error: body.detail || `HTTP ${res.status}` }
    }
    if (res.status === 204) return { data: null, error: null }
    return { data: await res.json(), error: null }
  } catch {
    return { data: null, error: 'Network error — is the backend running?' }
  }
}

export const fetchUsers = () => request('/users')
export const createUser = (body) =>
  request('/users', { method: 'POST', body: JSON.stringify(body) })
export const updateUser = (username, body) =>
  request(`/users/${encodeURIComponent(username)}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
export const deleteUser = (username) =>
  request(`/users/${encodeURIComponent(username)}`, { method: 'DELETE' })
export const fetchStatus = () => request('/status')
export const fetchInbounds = () => request('/inbounds')
export const fetchOutbounds = () => request('/outbounds')
export const fetchConfig = () => request('/config')
export const fetchGeneratedConfig = () => request('/config/generated')
export const postConfig = (body) =>
  request('/config', { method: 'POST', body: JSON.stringify(body) })
