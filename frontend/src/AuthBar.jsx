import { useState } from 'react'
import { api, setToken } from './api'

// 상단 인증 바: 로그인/회원가입 폼 토글, 로그인 상태 표시.
// 로그인 성공 시 onAuth({ nickname }) 호출.
export default function AuthBar({ user, onAuth, onLogout }) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState('login') // login | signup
  const [form, setForm] = useState({ email: '', password: '', nickname: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const path = mode === 'login' ? '/api/auth/login' : '/api/auth/signup'
      const body =
        mode === 'login'
          ? { email: form.email, password: form.password }
          : form
      const data = await api(path, { method: 'POST', body })
      setToken(data.token)
      onAuth({ nickname: data.nickname })
      setOpen(false)
      setForm({ email: '', password: '', nickname: '' })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (user) {
    return (
      <div className="authbar">
        <span className="who">👤 {user.nickname}</span>
        <button className="ghost small" onClick={onLogout}>
          로그아웃
        </button>
      </div>
    )
  }

  return (
    <div className="authbar">
      {!open ? (
        <button className="ghost small" onClick={() => setOpen(true)}>
          로그인 / 회원가입
        </button>
      ) : (
        <form className="auth-form" onSubmit={submit}>
          <div className="tabs">
            <button
              type="button"
              className={mode === 'login' ? 'on' : ''}
              onClick={() => setMode('login')}
            >
              로그인
            </button>
            <button
              type="button"
              className={mode === 'signup' ? 'on' : ''}
              onClick={() => setMode('signup')}
            >
              회원가입
            </button>
          </div>
          <input
            type="email"
            placeholder="이메일"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            required
          />
          <input
            type="password"
            placeholder="비밀번호 (6자 이상)"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            required
          />
          {mode === 'signup' && (
            <input
              placeholder="닉네임"
              value={form.nickname}
              onChange={(e) => setForm({ ...form, nickname: e.target.value })}
              required
            />
          )}
          {error && <div className="auth-error">{error}</div>}
          <div className="auth-actions">
            <button className="primary small" disabled={busy}>
              {busy ? '처리 중…' : mode === 'login' ? '로그인' : '가입하기'}
            </button>
            <button type="button" className="ghost small" onClick={() => setOpen(false)}>
              닫기
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
