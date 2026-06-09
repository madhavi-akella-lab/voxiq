import type { CallRecord } from '../lib/api'

export default function StatsCards({ calls }: { calls: CallRecord[] }) {
  const total     = calls.length
  const complete  = calls.filter(c => c.status === 'COMPLETE').length
  const pending   = calls.filter(c => c.status === 'TRANSCRIBING' || c.status === 'ANALYZING').length
  const positive  = calls.filter(c => c.sentiment === 'positive').length
  const pctPos    = complete ? Math.round((positive / complete) * 100) : 0

  const cards = [
    { label: 'Total calls',       value: total,       color: 'text-blue-600' },
    { label: 'Analysed',          value: complete,    color: 'text-green-600' },
    { label: 'In progress',       value: pending,     color: 'text-yellow-600' },
    { label: 'Positive sentiment',value: `${pctPos}%`,color: 'text-emerald-600' },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      {cards.map(c => (
        <div key={c.label} className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-500 mb-1">{c.label}</p>
          <p className={`text-2xl font-semibold ${c.color}`}>{c.value}</p>
        </div>
      ))}
    </div>
  )
}
