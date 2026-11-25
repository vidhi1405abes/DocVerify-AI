import { VERDICT_LABELS, VERDICT_STYLES } from './verdict'

const VerdictBadge = ({ verdict }) => (
  <span
    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${
      VERDICT_STYLES[verdict]?.badge ?? 'bg-gray-100 text-gray-700 ring-gray-500/20'
    }`}
  >
    {VERDICT_LABELS[verdict] ?? verdict}
  </span>
)

export default VerdictBadge
