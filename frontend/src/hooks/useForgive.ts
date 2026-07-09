import { useMutation, useQueryClient } from '@tanstack/react-query'
import { postForgive } from '../api/runaway'
import { ApiError } from '../api/client'
import { myAvatarKey } from './useAvatar'

/** 点头让分身回家。成功/失败都重取 /avatars/mine——失败多半是状态过期（TA 还没来哄）。 */
export function useForgive() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: postForgive,
    retry: (failureCount, error) => failureCount < 2 && !(error instanceof ApiError),
    retryDelay: 200,
    onSettled: () => qc.invalidateQueries({ queryKey: myAvatarKey }),
  })
}
