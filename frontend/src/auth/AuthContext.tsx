import { createContext, useContext, useEffect, useRef, useState, ReactNode } from 'react'
import { setAuthToken, setOnUnauthorized } from '../api/client'
import { registerUser, loginUser } from '../api/auth'
import { AuthUser, AuthResponse } from '../api/types'
import { applyTheme, Gender } from '../theme'

const TOKEN_KEY = 'couple.token'
const USER_KEY = 'couple.user'
const CRED_KEY = 'couple.cred'      // saved credentials for auto-login (remember me)
const REMEMBER_KEY = 'couple.remember'

type Creds = { nickname: string; password: string }
type Phase = 'restoring' | 'ready'

interface AuthValue {
  user: AuthUser | null
  token: string | null
  phase: Phase
  login: (nickname: string, password: string, remember?: boolean) => Promise<void>
  register: (nickname: string, password: string, gender: Gender, remember?: boolean) => Promise<void>
  logout: () => void
}
const AuthCtx = createContext<AuthValue | null>(null)

// Remembered sessions live in localStorage; "just this time" ones in sessionStorage.
function readSession(): { token: string | null; user: AuthUser | null } {
  for (const s of [localStorage, sessionStorage]) {
    const t = s.getItem(TOKEN_KEY)
    const u = s.getItem(USER_KEY)
    if (t && u) {
      try {
        return { token: t, user: JSON.parse(u) as AuthUser }
      } catch {
        /* corrupt entry → ignore, fall through */
      }
    }
  }
  return { token: null, user: null }
}
function readCreds(): Creds | null {
  const raw = localStorage.getItem(CRED_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as Creds
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [initial] = useState(readSession)
  const [token, setToken] = useState<string | null>(initial.token)
  const [user, setUser] = useState<AuthUser | null>(initial.user)
  // No live session but creds on file → try a silent login before showing anything.
  const [phase, setPhase] = useState<Phase>(
    initial.token ? 'ready' : readCreds() ? 'restoring' : 'ready',
  )
  const autoTried = useRef(false)

  // Install the restored token into the API client SYNCHRONOUSLY on first render.
  // If we deferred this to an effect, child effects (which fire first on mount)
  // would send the initial /couples/me request tokenless → 401 → onUnauthorized
  // → false logout on every refresh.
  const primed = useRef(false)
  if (!primed.current) {
    primed.current = true
    setAuthToken(initial.token)
  }

  useEffect(() => {
    setAuthToken(token)
  }, [token])

  // Keep the app's color following whoever is signed in.
  useEffect(() => {
    applyTheme(user?.gender)
  }, [user])

  const applySession = (res: AuthResponse, remember: boolean) => {
    const primary = remember ? localStorage : sessionStorage
    const other = remember ? sessionStorage : localStorage
    primary.setItem(TOKEN_KEY, res.access_token)
    primary.setItem(USER_KEY, JSON.stringify(res.user))
    other.removeItem(TOKEN_KEY)
    other.removeItem(USER_KEY)
    localStorage.setItem(REMEMBER_KEY, remember ? '1' : '0')
    setAuthToken(res.access_token)
    setToken(res.access_token)
    setUser(res.user)
  }

  const rememberCreds = (remember: boolean, creds: Creds) => {
    if (remember) localStorage.setItem(CRED_KEY, JSON.stringify(creds))
    else localStorage.removeItem(CRED_KEY)
  }

  const login = async (nickname: string, password: string, remember = true) => {
    const res = await loginUser(nickname, password)
    applySession(res, remember)
    rememberCreds(remember, { nickname, password })
  }
  const register = async (nickname: string, password: string, gender: Gender, remember = true) => {
    const res = await registerUser(nickname, password, gender)
    applySession(res, remember)
    rememberCreds(remember, { nickname, password })
  }

  // Drop the session (both stores) but leave saved creds untouched.
  const clearSession = () => {
    for (const s of [localStorage, sessionStorage]) {
      s.removeItem(TOKEN_KEY)
      s.removeItem(USER_KEY)
    }
    setAuthToken(null)
    setToken(null)
    setUser(null)
  }
  const logout = () => {
    clearSession()
    localStorage.removeItem(CRED_KEY)
    localStorage.removeItem(REMEMBER_KEY)
  }

  // A 401 means the token is stale — drop it, but keep creds so the next launch
  // can silently sign back in. Genuinely bad creds get pruned by the auto-login below.
  useEffect(() => {
    setOnUnauthorized(clearSession)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Launch auto-login: remembered creds, no live session.
  useEffect(() => {
    if (phase !== 'restoring' || autoTried.current) return
    autoTried.current = true
    const cred = readCreds()
    if (!cred) {
      setPhase('ready')
      return
    }
    loginUser(cred.nickname, cred.password)
      .then((res) => applySession(res, true))
      .catch((err: unknown) => {
        // Only forget creds when the server actually rejects them.
        if (err && typeof err === 'object' && (err as { status?: number }).status === 401) {
          localStorage.removeItem(CRED_KEY)
        }
      })
      .finally(() => setPhase('ready'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <AuthCtx.Provider value={{ user, token, phase, login, register, logout }}>{children}</AuthCtx.Provider>
  )
}

export function useAuth() {
  const v = useContext(AuthCtx)
  if (!v) throw new Error('useAuth must be used within AuthProvider')
  return v
}
