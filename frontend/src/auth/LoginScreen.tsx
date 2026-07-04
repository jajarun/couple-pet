import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { ApiError } from '../api/client'

export function LoginScreen() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [nickname, setNickname] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(true)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      await login(nickname, password, remember)
      nav('/')
    } catch (e2) {
      setErr(
        e2 instanceof ApiError && e2.status === 401
          ? '账号或密码不对哦~'
          : '登录出了点岔子，再试一次~',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="pad stack" style={{ gap: 16, marginTop: 'auto', marginBottom: 'auto' }}>
      <div className="center stack" style={{ gap: 8 }}>
        <div className="brand-mark">💕</div>
        <h2>欢迎回来</h2>
        <p className="muted tiny">TA 的分身正等着你</p>
      </div>
      <input aria-label="昵称" value={nickname} onChange={(e) => setNickname(e.target.value)} placeholder="昵称" />
      <input aria-label="密码" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="密码" />
      <label className="remember-row">
        <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
        记住我，下次自动登录
      </label>
      {err && <div role="alert" style={{ color: 'var(--warn)' }}>{err}</div>}
      <button type="submit" className="btn-primary btn-lg btn-block" disabled={busy}>进去</button>
      <Link className="center" to="/register">还没账号？去注册</Link>
    </form>
  )
}
