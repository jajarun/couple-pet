import { useEffect, useRef, useState } from 'react'
import { TabBar } from '../components/TabBar'
import { HomeScreen } from '../home/HomeScreen'
import { ChatScreen } from '../chat/ChatScreen'
import { StoryScreen } from '../story/StoryScreen'
import { MyAvatarScreen } from '../me/MyAvatarScreen'
import { useAuth } from '../auth/AuthContext'
import { useFeed } from '../hooks/useFeed'
import { useNudge } from '../hooks/useNudge'
import { usePresence } from '../hooks/usePresence'
import { useStory } from '../hooks/useStory'
import { ensurePushSubscribed } from '../hooks/usePush'
import { clearAppBadge } from '../push/appBadge'
import { hasUnseen } from './badge'
import { Gender } from '../theme'

export function MainShell({
  coupleId,
  myUserId,
  partnerId,
  partnerGender,
}: {
  coupleId: number
  myUserId: number
  partnerId: number
  partnerGender?: Gender | null
}) {
  const [tab, setTab] = useState('home')
  const { logout, user } = useAuth()
  useNudge(coupleId) // 页面开着时，分身每分钟可能主动撩你一下
  // 在线心跳。切后台时 TanStack 自动停掉 refetchInterval → 我对 TA 自动显示为离线。
  const presence = usePresence()
  const together = presence.data?.partner_online ?? false
  useEffect(() => {
    ensurePushSubscribed() // 已授权过就静默补订阅（不弹权限框）；不支持则无操作
  }, [])
  // 人一回到 App 就把主屏图标的未读角标清掉（进来看了就算看过）
  useEffect(() => {
    clearAppBadge()
    const onVisible = () => {
      if (document.visibilityState === 'visible') clearAppBadge()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [])
  const feed = useFeed(coupleId)
  const maxId = (feed.data?.events ?? []).reduce((m, e) => Math.max(m, e.id), 0)
  const seenRef = useRef(0)
  useEffect(() => {
    if (tab === 'chat') seenRef.current = maxId
  }, [tab, maxId])
  const unseen = hasUnseen(maxId, seenRef.current, tab)
  // 🎭 的红点不走 badge.ts 那套「未读事件游标」——服务端直接告诉你轮没轮到你
  const myTurn = useStory(coupleId).data?.my_turn ?? false

  const tabs = [
    { key: 'home', label: '🏠 TA' },
    { key: 'chat', label: unseen ? '💬 聊天 🔴' : '💬 聊天' },
    { key: 'story', label: myTurn ? '🎭 剧情 🔴' : '🎭 剧情' },
    { key: 'me', label: '⚙️ 我' },
  ]

  return (
    // Fixed to the viewport so the content scrolls INSIDE and the tab bar stays pinned.
    <div style={{ display: 'flex', flexDirection: 'column', height: '100dvh', minHeight: 0 }}>
      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', WebkitOverflowScrolling: 'touch', overscrollBehavior: 'contain' }}>
        {tab === 'home' && (
          <HomeScreen coupleId={coupleId} partnerId={partnerId} together={together} />
        )}
        {tab === 'chat' && (
          <ChatScreen
            coupleId={coupleId}
            myUserId={myUserId}
            partnerId={partnerId}
            myGender={user?.gender ?? null}
            partnerGender={partnerGender ?? null}
          />
        )}
        {tab === 'story' && <StoryScreen coupleId={coupleId} />}
        {tab === 'me' && <MyAvatarScreen onLogout={logout} />}
      </div>
      <TabBar tabs={tabs} active={tab} onChange={setTab} />
    </div>
  )
}
