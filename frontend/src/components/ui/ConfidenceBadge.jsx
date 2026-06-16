import { CheckCircle2, TrendingUp, AlertTriangle } from 'lucide-react'

const CONFIG = {
  verified: {
    label: 'Verified',
    className: 'badge-verified',
    Icon: CheckCircle2,
  },
  high_confidence: {
    label: 'High confidence',
    className: 'badge-high-confidence',
    Icon: TrendingUp,
  },
  validation_required: {
    label: 'Validation required',
    className: 'badge-validation-required',
    Icon: AlertTriangle,
  },
}

export default function ConfidenceBadge({ level }) {
  const config = CONFIG[level] ?? CONFIG.validation_required
  const { label, className, Icon } = config

  return (
    <span className={className}>
      <Icon size={11} />
      {label}
    </span>
  )
}
