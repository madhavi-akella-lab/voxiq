interface Props { status: string }

const styles: Record<string, string> = {
  TRANSCRIBING: 'bg-blue-100 text-blue-800',
  ANALYZING:    'bg-yellow-100 text-yellow-800',
  COMPLETE:     'bg-green-100 text-green-800',
  FAILED:       'bg-red-100 text-red-800',
}

const labels: Record<string, string> = {
  TRANSCRIBING: '⏳ Transcribing',
  ANALYZING:    '🤖 Analysing',
  COMPLETE:     '✅ Complete',
  FAILED:       '❌ Failed',
}

export default function StatusBadge({ status }: Props) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${styles[status] ?? 'bg-gray-100 text-gray-700'}`}>
      {labels[status] ?? status}
    </span>
  )
}
