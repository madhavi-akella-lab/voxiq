import { useState } from 'react'
import { RefreshCw, Phone } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useCalls } from './hooks/useCalls'
import type { CallRecord } from './lib/api'
import SentimentBadge from './components/SentimentBadge'
import StatusBadge from './components/StatusBadge'
import UploadButton from './components/UploadButton'
import CallDetail from './components/CallDetail'
import StatsCards from './components/StatsCards'
import SentimentChart from './components/SentimentChart'

export default function App() {
  const { data: calls = [], isLoading, isError } = useCalls()
  const [selected, setSelected] = useState<CallRecord | null>(null)
  const [search, setSearch] = useState('')
  const qc = useQueryClient()

  const filtered = calls.filter(c =>
    !search ||
    c.call_id.includes(search) ||
    (c.summary ?? '').toLowerCase().includes(search.toLowerCase()) ||
    (c.caller_phone ?? '').includes(search)
  )

  return (
    <div className="min-h-screen bg-gray-50">

      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Phone size={22} className="text-blue-600" />
            <span className="text-lg font-semibold text-gray-900">VoxIQ</span>
            <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-100">Voice Intelligence</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => qc.invalidateQueries({ queryKey: ['calls'] })}
              className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors"
              title="Refresh"
            >
              <RefreshCw size={16} />
            </button>
            <UploadButton />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">

        {/* Stats + Chart */}
        {calls.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2">
              <StatsCards calls={calls} />
            </div>
            <SentimentChart calls={calls} />
          </div>
        )}

        {/* Calls table */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between gap-4">
            <h2 className="text-sm font-semibold text-gray-800">Call records</h2>
            <input
              type="text"
              placeholder="Search calls…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 w-56 focus:outline-none focus:ring-2 focus:ring-blue-200"
            />
          </div>

          {isLoading && (
            <div className="py-16 text-center text-sm text-gray-400">Loading calls…</div>
          )}

          {isError && (
            <div className="py-16 text-center text-sm text-red-500">
              Could not load calls — check your VITE_API_URL in .env
            </div>
          )}

          {!isLoading && !isError && filtered.length === 0 && (
            <div className="py-16 text-center text-sm text-gray-400">
              {calls.length === 0
                ? 'No calls yet — upload an audio file to get started'
                : 'No calls match your search'}
            </div>
          )}

          {filtered.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-gray-500 border-b border-gray-100">
                    <th className="text-left px-5 py-3 font-medium">Date</th>
                    <th className="text-left px-5 py-3 font-medium">Phone</th>
                    <th className="text-left px-5 py-3 font-medium">Summary</th>
                    <th className="text-left px-5 py-3 font-medium">Category</th>
                    <th className="text-left px-5 py-3 font-medium">Sentiment</th>
                    <th className="text-left px-5 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(call => (
                    <tr
                      key={call.call_id}
                      onClick={() => setSelected(call)}
                      className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors"
                    >
                      <td className="px-5 py-3 text-gray-500 whitespace-nowrap">
                        {new Date(call.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-5 py-3 text-gray-700 font-mono text-xs">
                        {call.caller_phone}
                      </td>
                      <td className="px-5 py-3 text-gray-700 max-w-xs truncate">
                        {call.summary ?? <span className="text-gray-400 italic">Processing…</span>}
                      </td>
                      <td className="px-5 py-3">
                        {call.routing_category
                          ? <span className="text-xs text-purple-700 bg-purple-50 px-2 py-0.5 rounded-full">
                              {call.routing_category.replace(/_/g, ' ')}
                            </span>
                          : <span className="text-gray-300">—</span>
                        }
                      </td>
                      <td className="px-5 py-3">
                        <SentimentBadge sentiment={call.sentiment} />
                      </td>
                      <td className="px-5 py-3">
                        <StatusBadge status={call.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {/* Slide-over detail panel */}
      {selected && <CallDetail call={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
