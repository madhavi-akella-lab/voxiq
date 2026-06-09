const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:3000'

export interface CallRecord {
  call_id: string
  created_at: string
  updated_at: string
  org_id: string
  status: 'TRANSCRIBING' | 'ANALYZING' | 'COMPLETE' | 'FAILED'
  caller_phone: string
  audio_key: string
  summary?: string
  sentiment?: 'positive' | 'neutral' | 'negative'
  routing_category?: string
  caller_intent?: string
  key_topics?: string[]
  resolution?: string
  full_transcript?: string
  duration_seconds?: number
  confidence_score?: number
}

export async function fetchCalls(orgId = 'default', limit = 50): Promise<CallRecord[]> {
  const res = await fetch(`${API_URL}/calls?org_id=${orgId}&limit=${limit}`)
  if (!res.ok) throw new Error('Failed to fetch calls')
  const data = await res.json()
  return data.calls
}

export async function getUploadUrl(ext: string, orgId = 'default'): Promise<{ upload_url: string; key: string }> {
  const res = await fetch(`${API_URL}/upload-url?ext=${ext}&org_id=${orgId}`)
  if (!res.ok) throw new Error('Failed to get upload URL')
  return res.json()
}

export async function uploadAudio(file: File, orgId = 'default'): Promise<string> {
  const ext = file.name.split('.').pop() ?? 'mp3'
  const { upload_url, key } = await getUploadUrl(ext, orgId)
  const putRes = await fetch(upload_url, {
    method: 'PUT',
    body: file,
    headers: { 'Content-Type': `audio/${ext}` },
  })
  if (!putRes.ok) throw new Error('Upload to S3 failed')
  return key
}
