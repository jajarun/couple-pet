import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { setAuthToken } from '../api/client'
import { registerUser, loginUser } from '../api/auth'
import { AuthUser } from '../api/types'

const TOKEN_KEY = 'couple.token'
const USER_KEY = 'couple.user'

interface AuthValue {
  user: AuthUser | null
  token: string | null
  login: (nickname: string, password: string) => Promise<void>
  register: (nickname: string, password: string) => Promise<void>
  logout: () => void
}
const AuthCtx = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState<AuthUser | null>(() => {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as AuthUser) : null
  })

  useEffect(() => {
    setAuthToken(token)
  }, [token])

  const apply = (t: string, u: AuthUser) => {
    localStorage.setItem(TOKEN_KEY, t)
    localStorage.setItem(USER_KEY, JSON.stringify(u))
    setAuthToken(t)
    setToken(t)
    setUser(u)
  }

  const login = async (nickname: string, password: string) => {
    const res = await loginUser(nickname, password)
    apply(res.access_token, res.user)
  }
  const register = async (nickname: string, password: string) => {
    const res = await registerUser(nickname, password)
    apply(res.access_token, res.user)
  }
  const logout = () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setAuthToken(null)
    setToken(null)
    setUser(null)
  }

  return (
    <AuthCtx.Provider value={{ user, token, login, register, logout }}>{children}</AuthCtx.Provider>
  )
}

export function useAuth() {
  const v = useContext(AuthCtx)
  if (!v) throw new Error('useAuth must be used within AuthProvider')
  return v
}
