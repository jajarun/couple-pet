import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import { LoginScreen } from './auth/LoginScreen'
import { RegisterScreen } from './auth/RegisterScreen'
import { PixelPanel } from './components/PixelPanel'
import { LoadingBanter } from './components/LoadingBanter'
import { useCouple } from './hooks/useCouple'
import { useMyAvatar } from './hooks/useAvatar'
import { PairScreen } from './onboarding/PairScreen'
import { AvatarCreateScreen } from './onboarding/AvatarCreateScreen'
import { MainShell } from './shell/MainShell'

function RetryNotice({ onRetry }: { onRetry: () => void }) {
  return (
    <div style={{ padding: 16, textAlign: 'center' }}>
      <p>连不上服务器，稍等一下~</p>
      <button onClick={onRetry}>再试一次</button>
    </div>
  )
}

function Gate() {
  const { user } = useAuth()
  const couple = useCouple(!!user)
  const isActive = couple.data?.status === 'active'
  const myAvatar = useMyAvatar(isActive)

  if (couple.isLoading) return <LoadingBanter />
  if (couple.isError) return <RetryNotice onRetry={() => couple.refetch()} />
  if (!couple.data || couple.data.status === 'none')
    return <PairScreen couple={couple.data ?? { couple_id: null, status: 'none' }} />
  if (couple.data.status === 'pending') return <PairScreen couple={couple.data} />
  if (myAvatar.isLoading) return <LoadingBanter />
  if (myAvatar.isError) return <RetryNotice onRetry={() => myAvatar.refetch()} />
  if (!myAvatar.data || myAvatar.data.name === '') return <AvatarCreateScreen />
  return <MainShell coupleId={couple.data.couple_id} myUserId={user!.id} partnerId={couple.data.partner_id} />
}

export default function App() {
  const { user } = useAuth()
  return (
    <PixelPanel>
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/" /> : <LoginScreen />} />
        <Route path="/register" element={user ? <Navigate to="/" /> : <RegisterScreen />} />
        <Route path="/*" element={user ? <Gate /> : <Navigate to="/login" />} />
      </Routes>
    </PixelPanel>
  )
}
