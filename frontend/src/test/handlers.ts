import { http, HttpResponse } from 'msw'

// Default handlers; per-test handlers via server.use(...) take precedence.
// An empty feed by default keeps components that poll useFeed (Home, MainShell)
// happy without every test having to mock /events.
export const handlers = [
  http.get('/api/events', () =>
    HttpResponse.json({ events: [], stats: { grievance: 0, dogfood: 0, miss: 0, intimacy: 0 } }),
  ),
  http.get('/api/daily', () =>
    HttpResponse.json({
      question: { text: '今天过得咋样?', flavor: 'deep' },
      my_answer: null,
      partner_answer: null,
      both_answered: false,
      streak: { count: 0, i_did_today: false, partner_did_today: false, at_risk: false, lagging_user_id: null },
    }),
  ),
]
