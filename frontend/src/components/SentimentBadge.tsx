interface Props {
  sentiment?: string
}

const styles: Record<string, string> = {
  positive: 'bg-green-100 text-green-800',
  neutral:  'bg-gray-100 text-gray-700',
  negative: 'bg-red-100 text-red-800',
}

const labels: Record<string, string> = {
  positive: '😊 Positive',
  neutral:  '😐 Neutral',
  negative: '😟 Negative',
}

export default function SentimentBadge({ sentiment }: Props) {
  const s = sentiment ?? 'neutral'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${styles[s] ?? styles.neutral}`}>
      {labels[s] ?? s}
    </span>
  )
}
