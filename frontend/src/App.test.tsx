import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { test, expect, beforeEach } from 'vitest'
import { server } from './test/server'
import { renderWithProviders } from './test/utils'
import { AuthProvider } from './auth/AuthContext'
import App from './App'

beforeEach(() => localStorage.clear())

test('unauthenticated users land on login', async () => {
  renderWithProviders(
    <AuthProvider>
      <App />
    </AuthProvider>,
  )
  expect(await screen.findByRole('button', { name: '进去' })).toBeInTheDocument()
})

test('authenticated active couple with a captured avatar lands on home', async () => {
  localStorage.setItem('couple.token', 'tok')
  localStorage.setItem('couple.user', JSON.stringify({ id: 1, nickname: 'mimi' }))
  server.use(
    http.get('/api/couples/me', () => HttpResponse.json({ couple_id: 1, status: 'active', partner_id: 2 })),
    http.get('/api/avatars/mine', () => HttpResponse.json({ id: 1, couple_id: 1, subject_user_id: 1, keeper_user_id: 2, name: '本尊', appearance: {}, persona: {} })),
    http.get('/api/avatars/pet', () => HttpResponse.json({ id: 2, couple_id: 1, subject_user_id: 2, keeper_user_id: 1, name: '臭宝', appearance: { emoji: '🐷' }, persona: {} })),
    http.get('/api/events', () => HttpResponse.json({ events: [], stats: { grievance: 0, dogfood: 0, miss: 0, intimacy: 0 } })),
  )
  renderWithProviders(
    <AuthProvider>
      <App />
    </AuthProvider>,
  )
  expect(await screen.findByRole('button', { name: '骂一顿' })).toBeInTheDocument()
})
