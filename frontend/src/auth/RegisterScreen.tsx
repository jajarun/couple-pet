import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { ApiError } from '../api/client'

export function RegisterScreen() {
  const { register } = useAuth()
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
      await register(nickname, password)
      nav('/')
    } catch (e2) {
      if (e2 instanceof ApiError && e2.status === 409) setErr('这名字被抢啦，换一个')
      else if (e2 instanceof ApiError && e2.status === 422) setErr('密码至少 6 位哦')
      else setErr('注册出了点岔子，再试一次~')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} style={{ display: 'grid', gap: 10, padding: 16 }}>
      <h2>注册</h2>
      <input aria-label="昵称" value={nickname} onChange={(e) => setNickname(e.target.value)} placeholder="起个昵称" />
      <input aria-label="密码" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="密码（≥6 位）" />
      {err && (
        <div role="alert" style={{ color: 'var(--warn)' }}>
          {err}
        </div>
      )}
      <button type="submit" disabled={busy}>注册</button>
      <Link to="/login">已有账号？去登录</Link>
    </form>
  )
}
