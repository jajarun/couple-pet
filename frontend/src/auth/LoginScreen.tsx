import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { ApiError } from '../api/client'

export function LoginScreen() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [nickname, setNickname] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      await login(nickname, password)
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
    <form onSubmit={submit} style={{ display: 'grid', gap: 10, padding: 16 }}>
      <h2>登录</h2>
      <input aria-label="昵称" value={nickname} onChange={(e) => setNickname(e.target.value)} placeholder="昵称" />
      <input aria-label="密码" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="密码" />
      {err && (
        <div role="alert" style={{ color: 'var(--warn)' }}>
          {err}
        </div>
      )}
      <button type="submit" disabled={busy}>进去</button>
      <Link to="/register">还没账号？去注册</Link>
    </form>
  )
}
