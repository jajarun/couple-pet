export interface AuthUser {
  id: number
  nickname: string
  gender?: 'male' | 'female' | null
}
/** GET/PATCH /auth/me 的返回。开关状态以服务端为准，别从 AuthContext 缓存的 user 上读。 */
export interface Me extends AuthUser {
  ai_reply_enabled: boolean
}
export interface AuthResponse {
  access_token: string
  token_type: string
  user: AuthUser
}
export interface Stats {
  grievance: number
  dogfood: number
  miss: number
  intimacy: number
}
export type EventKind = 'action' | 'ai_reaction' | 'real_response' | 'system' | 'daily_qa'
export interface GameEvent {
  id: number
  couple_id: number
  actor_user_id: number | null
  kind: EventKind
  action_type: string | null
  content: string
  parent_event_id: number | null
  created_at: string
}
export interface Avatar {
  id: number
  couple_id: number
  subject_user_id: number
  keeper_user_id: number
  name: string
  appearance: Record<string, unknown>
  persona: Record<string, unknown>
}
export type CoupleState =
  | { couple_id: number; status: 'active'; partner_id: number; partner_gender?: 'male' | 'female' | null }
  | { couple_id: number; status: 'pending'; pair_code: string }
  | { couple_id: null; status: 'none' }
export interface ActionBundle {
  events: GameEvent[]
  stats: Stats
}
export interface FeedResponse {
  events: GameEvent[]
  stats: Stats
  has_more?: boolean
}
export interface StreakView {
  count: number
  i_did_today: boolean
  partner_did_today: boolean
  at_risk: boolean
  rescuable: boolean
  lagging_user_id: number | null
}
export interface DailyResponse {
  question: { text: string; flavor: string }
  my_answer: string | null
  partner_answer: string | null
  both_answered: boolean
  streak: StreakView
}
export interface PushSubscribePayload {
  endpoint: string
  keys: { p256dh: string; auth: string }
}
