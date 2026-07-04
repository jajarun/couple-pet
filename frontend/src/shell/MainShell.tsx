import { useEffect, useRef, useState } from 'react'
import { TabBar } from '../components/TabBar'
import { HomeScreen } from '../home/HomeScreen'
import { FeedScreen } from '../feed/FeedScreen'
import { ChatScreen } from '../chat/ChatScreen'
import { MyAvatarScreen } from '../me/MyAvatarScreen'
import { useAuth } from '../auth/AuthContext'
import { useFeed } from '../hooks/useFeed'
import { hasUnseen } from './badge'

export function MainShell({ coupleId, myUserId, partnerId }: { coupleId: number; myUserId: number; partnerId: number }) {
  const [tab, setTab] = useState('home')
  const { logout } = useAuth()
  const feed = useFeed(coupleId)
  const maxId = (feed.data?.events ?? []).reduce((m, e) => Math.max(m, e.id), 0)
  const seenRef = useRef(0)
  useEffect(() => {
    if (tab === 'feed') seenRef.current = maxId
  }, [tab, maxId])
  const unseen = hasUnseen(maxId, seenRef.current, tab)

  const tabs = [
    { key: 'home', label: '🏠 TA' },
    { key: 'feed', label: unseen ? '🔔 事件流 🔴' : '🔔 事件流' },
    { key: 'chat', label: '💬 唠' },
    { key: 'me', label: '⚙️ 我' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <div style={{ flex: 1 }}>
        {tab === 'home' && <HomeScreen coupleId={coupleId} />}
        {tab === 'feed' && <FeedScreen coupleId={coupleId} myUserId={myUserId} partnerId={partnerId} />}
        {tab === 'chat' && <ChatScreen coupleId={coupleId} />}
        {tab === 'me' && <MyAvatarScreen onLogout={logout} />}
      </div>
      <TabBar tabs={tabs} active={tab} onChange={setTab} />
    </div>
  )
}
