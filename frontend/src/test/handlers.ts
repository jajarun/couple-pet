import { http, HttpResponse } from 'msw'

// Default handlers; per-test handlers via server.use(...) take precedence.
// An empty feed by default keeps components that poll useFeed (Home, MainShell)
// happy without every test having to mock /events.
export const handlers = [
  // 分身回复默认关闭；要测「已开启」的用例用 server.use 覆盖
  http.get('/api/auth/me', () =>
    HttpResponse.json({ id: 1, nickname: 'alice', gender: 'female', ai_reply_enabled: false }),
  ),
  http.get('/api/events', () =>
    HttpResponse.json({ events: [], stats: { grievance: 0, dogfood: 0, miss: 0, intimacy: 0 } }),
  ),
  http.get('/api/daily', () =>
    HttpResponse.json({
      question: { text: '今天过得咋样?', flavor: 'deep' },
      my_answer: null,
      partner_answer: null,
      both_answered: false,
      streak: {
        count: 0,
        i_did_today: false,
        partner_did_today: false,
        at_risk: false,
        rescuable: false,
        lagging_user_id: null,
      },
    }),
  ),
  http.post('/api/streak/rescue', () =>
    HttpResponse.json({
      count: 3,
      i_did_today: false,
      partner_did_today: false,
      at_risk: true,
      rescuable: false,
      lagging_user_id: null,
    }),
  ),
  // 默认推送未启用（空公钥），订阅/退订成功；单测按需用 server.use 覆盖
  http.get('/api/push/public-key', () => HttpResponse.json({ key: '' })),
  http.post('/api/push/subscribe', () => new HttpResponse(null, { status: 204 })),
  http.delete('/api/push/subscribe', () => new HttpResponse(null, { status: 204 })),
]
