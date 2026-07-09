import { motion } from 'framer-motion'

/** 两人同时开着页面时亮起。这个信号本身就是留在页面上的理由。 */
export function TogetherBanner() {
  return (
    <motion.div
      className="together-banner"
      data-testid="together-banner"
      role="status"
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
    >
      <span className="together-dot" aria-hidden="true" />
      <span>✨ TA 正在看这只分身</span>
      <span className="together-x2">互动 ×2</span>
    </motion.div>
  )
}
