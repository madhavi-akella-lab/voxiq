import { X, Phone, Calendar, Tag, Mic } from 'lucide-react'
import type { CallRecord } from '../lib/api'
import SentimentBadge from './SentimentBadge'
import StatusBadge from './StatusBadge'

interface Props {
  call: CallRecord | null
  onClose: () => void
}

export default function CallDetail({ call, onClose }: Props) {
  if (!call) return null

  const date = new Date(call.created_at).toLocaleString()

  return (
    <div className="fixed inset-0 z-40 flex justify-end" onClick={onClose}>
      <div
        className="relative w-full max-w-lg bg-white shadow-xl h-full overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">Call Detail</h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-gray-100">
            <X size={18} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-6">

          {/* Meta */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="flex items-center gap-2 text-gray-500">
              <Calendar size={14} />
              <span>{date}</span>
            </div>
            <div className="flex items-center gap-2 text-gray-500">
              <Phone size={14} />
              <span>{call.caller_phone}</span>
            </div>
          </div>

          {/* Badges */}
          <div className="flex flex-wrap gap-2">
            <StatusBadge status={call.status} />
            <SentimentBadge sentiment={call.sentiment} />
            {call.routing_category && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-purple-100 text-purple-800">
                <Tag size={10} />
                {call.routing_category.replace(/_/g, ' ')}
              </span>
            )}
          </div>

          {/* Summary */}
          {call.summary && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">AI Summary</h3>
              <p className="text-sm text-gray-700 leading-relaxed bg-gray-50 rounded-lg p-3">{call.summary}</p>
            </div>
          )}

          {/* Caller intent */}
          {call.caller_intent && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Caller Intent</h3>
              <p className="text-sm text-gray-700">{call.caller_intent}</p>
            </div>
          )}

          {/* Topics */}
          {call.key_topics && call.key_topics.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Key Topics</h3>
              <div className="flex flex-wrap gap-2">
                {call.key_topics.map(t => (
                  <span key={t} className="px-2 py-0.5 text-xs rounded-full bg-blue-50 text-blue-700">{t}</span>
                ))}
              </div>
            </div>
          )}

          {/* Transcript */}
          {call.full_transcript && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2 flex items-center gap-1">
                <Mic size={12} /> Full Transcript
              </h3>
              <pre className="text-xs text-gray-600 whitespace-pre-wrap bg-gray-50 rounded-lg p-3 leading-relaxed font-mono">
                {call.full_transcript}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
