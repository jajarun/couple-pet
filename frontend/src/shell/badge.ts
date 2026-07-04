export function hasUnseen(maxEventId: number, seenEventId: number, activeTab: string): boolean {
  return maxEventId > seenEventId && activeTab !== 'chat'
}
