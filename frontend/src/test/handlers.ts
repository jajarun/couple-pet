import { http, HttpResponse } from 'msw'

// Default handlers; per-test handlers via server.use(...) take precedence.
// An empty feed by default keeps components that poll useFeed (Home, MainShell)
// happy without every test having to mock /events.
export const handlers = [
  http.get('/api/events', () =>
    HttpResponse.json({ events: [], stats: { grievance: 0, dogfood: 0, miss: 0, intimacy: 0 } }),
  ),
]
