import { motion } from 'framer-motion'
import { LoadingBanter } from '../components/LoadingBanter'
import { PressButton } from '../components/PressButton'
import { useStory } from '../hooks/useStory'
import { StoryRound } from '../api/types'

const LETTERS = ['A', 'B', 'C']

/** 已经翻篇的一幕：场景 + 两个人当时选了什么 */
function PastRound({ round, index }: { round: StoryRound; index: number }) {
  const mineText = round.my_choice !== null ? round.options[round.my_choice] : null
  const theirsText = round.partner_choice !== null ? round.options[round.partner_choice] : null
  const sameChoice = mineText !== null && mineText === theirsText
  return (
    <motion.section
      className="story-round"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index, 3) * 0.04 }}
    >
      <p className="story-scene">{round.scene}</p>
      {round.both_chose && (
        <div className="story-picks" data-testid={`picks-${round.round_no}`}>
          {sameChoice ? (
            <span className="story-pick same">💞 你们俩都选了「{mineText}」</span>
          ) : (
            <>
              <span className="story-pick">你选了「{mineText}」</span>
              <span className="story-pick partner">TA 选了「{theirsText}」</span>
            </>
          )}
        </div>
      )}
    </motion.section>
  )
}

export function StoryScreen({ coupleId }: { coupleId: number }) {
  const { data, isLoading, choose, isChoosing } = useStory(coupleId)

  if (isLoading || !data)
    return (
      <div className="pad">
        <LoadingBanter />
      </div>
    )

  const { story, rounds, my_turn } = data
  const last = rounds[rounds.length - 1]
  const isEnding = last && last.options.length === 0
  const chapter = Math.min(last?.round_no ?? 1, story.total_rounds)

  return (
    <div className="screenview">
      <div className="screenview-body pad stack" style={{ gap: 14 }}>
        <header className="story-head">
          <div className="story-title">🎭 {story.title}</div>
          <span className="story-progress">
            {story.status === 'ended' ? '已完结' : `第 ${chapter} 幕 / 共 ${story.total_rounds} 幕`}
          </span>
        </header>

        {rounds.map((r, i) =>
          // 最后那一幕如果还没选完，下面单独渲染成「可选区」，这里不重复画
          r === last && !r.both_chose && !isEnding ? null : (
            <PastRound key={r.round_no} round={r} index={i} />
          ),
        )}

        {isEnding && (
          <motion.div
            className="story-ending"
            data-testid="story-ending"
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <div className="story-ending-tag">— 完 —</div>
            <p className="muted tiny">明天还有新的一章 🌙</p>
          </motion.div>
        )}

        {last && !isEnding && !last.both_chose && (
          <section className="story-round" data-testid="story-current">
            <p className="story-scene">{last.scene}</p>
            {my_turn ? (
              <div className="story-options">
                {last.options.map((opt, i) => (
                  <PressButton
                    key={opt}
                    className="story-option"
                    onPress={() => choose(last.round_no, i).catch(() => {})}
                    disabled={isChoosing}
                  >
                    <span className="story-letter" aria-hidden="true">
                      {LETTERS[i] ?? '·'}
                    </span>
                    <span>{opt}</span>
                  </PressButton>
                ))}
              </div>
            ) : (
              <div className="story-waiting" data-testid="story-waiting" role="status">
                <div>✅ 你选好了「{last.options[last.my_choice ?? 0]}」</div>
                <div className="muted tiny">等 TA 也做出选择，故事才会继续…</div>
                <LoadingBanter />
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  )
}
