import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { ApiError } from '../api/client'
import { applyTheme, Gender } from '../theme'

export function RegisterScreen() {
  const { register } = useAuth()
  const nav = useNavigate()
  const [nickname, setNickname] = useState('')
  const [password, setPassword] = useState('')
  const [gender, setGender] = useState<Gender | null>(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  // Recolor the whole app the instant they pick — before the account exists.
  const pick = (g: Gender) => {
    setGender(g)
    applyTheme(g)
  }

  const ready = nickname.trim() !== '' && password !== '' && gender !== null

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!gender) return
    setErr('')
    setBusy(true)
    try {
      await register(nickname, password, gender)
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
    <form onSubmit={submit} className="pad stack" style={{ gap: 16, marginTop: 'auto', marginBottom: 'auto' }}>
      <div className="center stack" style={{ gap: 8 }}>
        <div className="brand-mark">💞</div>
        <h2>捏一个属于你俩的分身</h2>
        <p className="muted tiny">先告诉我你是谁，界面会为你换上专属颜色</p>
      </div>

      <div className="stack" style={{ gap: 6 }}>
        <span className="tiny muted">我是</span>
        <div className="gender-row" role="radiogroup" aria-label="性别">
          <button
            type="button" role="radio" aria-checked={gender === 'male'}
            className="gender-card male" onClick={() => pick('male')}
          >
            <span className="g-emoji" aria-hidden="true">💙</span>
            <span>男生</span>
          </button>
          <button
            type="button" role="radio" aria-checked={gender === 'female'}
            className="gender-card female" onClick={() => pick('female')}
          >
            <span className="g-emoji" aria-hidden="true">💗</span>
            <span>女生</span>
          </button>
        </div>
      </div>

      <input aria-label="昵称" value={nickname} onChange={(e) => setNickname(e.target.value)} placeholder="起个昵称" />
      <input aria-label="密码" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="密码（≥6 位）" />

      {err && <div role="alert" style={{ color: 'var(--warn)' }}>{err}</div>}

      <button type="submit" className="btn-primary btn-lg btn-block" disabled={busy || !ready}>
        {busy ? '正在创建…' : '开始'}
      </button>
      <Link className="center" to="/login">已有账号？去登录</Link>
    </form>
  )
}
