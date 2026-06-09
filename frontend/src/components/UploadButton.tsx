import { useRef, useState } from 'react'
import { Upload, Loader2 } from 'lucide-react'
import { uploadAudio } from '../lib/api'
import { useQueryClient } from '@tanstack/react-query'

export default function UploadButton() {
  const inputRef   = useRef<HTMLInputElement>(null)
  const [state, setState] = useState<'idle' | 'uploading' | 'done' | 'error'>('idle')
  const [msg, setMsg]     = useState('')
  const qc = useQueryClient()

  async function handleFile(file: File) {
    setState('uploading')
    setMsg('')
    try {
      const key = await uploadAudio(file)
      setState('done')
      setMsg(`Uploaded! Processing will take ~1 minute.`)
      // Refetch calls after a short delay so the new TRANSCRIBING record appears
      setTimeout(() => qc.invalidateQueries({ queryKey: ['calls'] }), 3000)
      setTimeout(() => setState('idle'), 6000)
    } catch (e) {
      setState('error')
      setMsg('Upload failed — check your API URL in .env')
    }
  }

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept="audio/*,.mp3,.wav,.m4a,.flac,.ogg"
        className="hidden"
        onChange={e => { if (e.target.files?.[0]) handleFile(e.target.files[0]) }}
      />
      <button
        onClick={() => inputRef.current?.click()}
        disabled={state === 'uploading'}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        {state === 'uploading'
          ? <><Loader2 size={16} className="animate-spin" /> Uploading…</>
          : <><Upload size={16} /> Upload Audio</>}
      </button>
      {msg && (
        <p className={`mt-2 text-sm ${state === 'error' ? 'text-red-600' : 'text-green-600'}`}>
          {msg}
        </p>
      )}
    </div>
  )
}
