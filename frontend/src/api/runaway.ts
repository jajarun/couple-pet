import { apiRequest } from './client'
import { RunawayState } from './types'

/** 点头：让「代表我、被 TA 气跑了」的那只分身回家。哄是 TA 的事，回不回去是我的事。 */
export function postForgive() {
  return apiRequest<{ state: RunawayState }>('POST', '/runaway/forgive')
}
