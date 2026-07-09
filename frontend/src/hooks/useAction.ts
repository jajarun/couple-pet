import { useMutation, useQueryClient } from '@tanstack/react-query'
import { postAction } from '../api/actions'
import { ApiError } from '../api/client'
import { ActionBundle, Avatar, PresenceView, Stats } from '../api/types'
import { petAvatarKey } from './useAvatar'
import { dailyKey } from './useDaily'
import { FeedData, appendToFeed, feedKey, statsKey } from './useFeed'
import { presenceKey } from './usePresence'

export function useAction(coupleId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { action_type: string; content: string; client_key: string }) =>
      postAction(v.action_type, v.content, v.client_key),
    retry: (failureCount, error) => failureCount < 2 && !(error instanceof ApiError),
    retryDelay: 200,
    onError: (error) => {
      if (!(error instanceof ApiError) || error.status !== 409) return
      // 另一端刚把分身气跑了 / 刚哄完在等对方点头，而我们这边还不知道 → 重取，切到 RunawayScreen
      if (error.detail === 'pet_away' || error.detail === 'awaiting_forgiveness') {
        qc.invalidateQueries({ queryKey: petAvatarKey })
      }
      // TA 在我按下「摸摸头」的那一刻下线了 → 立刻把同框态改掉，按钮自己消失
      if (error.detail === 'not_together') {
        qc.setQueryData<PresenceView>(presenceKey, { partner_online: false })
      }
    },
    onSuccess: (bundle: ActionBundle) => {
      qc.setQueryData<FeedData>(feedKey(coupleId), (old) => appendToFeed(old, bundle.events))
      qc.setQueryData<Stats>(statsKey(coupleId), bundle.stats)
      // 服务端刚按同框与否结算过数值，顺手把同框态对齐（比等下一次心跳快 10 秒）
      if (bundle.together !== undefined) {
        qc.setQueryData<PresenceView>(presenceKey, { partner_online: bundle.together })
      }
      // 服务端刚算好的进化态直接回写，进度条当场就动——别再多发一次 GET /avatars/pet
      const evo = bundle.evolution
      if (evo) {
        qc.setQueryData<Avatar>(petAvatarKey, (old) => (old ? { ...old, evolution: evo } : old))
      }
      // 出走态变了（这一下把它逼走了 / 刚哄完转 pending）→ is_away / runaway_note 得重新取
      if (bundle.ran_away || bundle.events.some((e) => e.action_type === 'coax')) {
        qc.invalidateQueries({ queryKey: petAvatarKey })
      }
      // 动作也算今日露面：立刻刷一把火苗/今日一问，别等轮询 20s
      qc.invalidateQueries({ queryKey: dailyKey(coupleId) })
    },
  })
}
