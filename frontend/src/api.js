// 인증 토큰을 붙여 백엔드 API를 호출하는 헬퍼.
// 토큰은 localStorage에 보관한다.

const TOKEN_KEY = 'fridge_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}
export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export async function api(path, { method = 'GET', body, auth = false } = {}) {
  const headers = {}
  if (body) headers['Content-Type'] = 'application/json'
  if (auth) {
    const t = getToken()
    if (t) headers['Authorization'] = `Bearer ${t}`
  }
  const res = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const err = new Error(data.detail || `요청 실패 (HTTP ${res.status})`)
    err.status = res.status
    throw err
  }
  // 204/빈 응답 방어
  const text = await res.text()
  return text ? JSON.parse(text) : {}
}
