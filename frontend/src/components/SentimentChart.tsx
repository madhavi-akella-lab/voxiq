import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import type { CallRecord } from '../lib/api'

const COLORS: Record<string, string> = {
  positive: '#16a34a',
  neutral:  '#6b7280',
  negative: '#dc2626',
}

export default function SentimentChart({ calls }: { calls: CallRecord[] }) {
  const complete = calls.filter(c => c.status === 'COMPLETE')
  const counts   = complete.reduce<Record<string, number>>((acc, c) => {
    const s = c.sentiment ?? 'neutral'
    acc[s]  = (acc[s] ?? 0) + 1
    return acc
  }, {})

  const data = Object.entries(counts).map(([name, value]) => ({ name, value }))
  if (data.length === 0) return null

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">Sentiment breakdown</h3>
      <ResponsiveContainer width="100%" height={160}>
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={3} dataKey="value">
            {data.map(entry => (
              <Cell key={entry.name} fill={COLORS[entry.name] ?? '#9ca3af'} />
            ))}
          </Pie>
          <Tooltip formatter={(v: number) => [`${v} calls`, '']} />
          <Legend iconType="circle" iconSize={8} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
