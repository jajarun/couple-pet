/** 动作 → 时间线上的一句话。聊天页和首页（同框时的实时反应）共用。 */
export const ACTION_VERB: Record<string, (other: string) => string> = {
  scold: (o) => `骂了${o}`,
  poke: (o) => `戳了${o}`,
  feed_dogfood: () => '喂了狗粮',
  hug: (o) => `抱了${o}`,
  miss_you: (o) => `说想${o}`,
  apologize: () => '道了歉',
  chat: (o) => `找${o}唠`,
  coax: (o) => `在哄${o}回家`,
  headpat: (o) => `摸了摸${o}的头`,
}

export function verbOf(actionType: string | null, other: string): string {
  const make = actionType ? ACTION_VERB[actionType] : undefined
  return make ? make(other) : '做了个动作'
}
