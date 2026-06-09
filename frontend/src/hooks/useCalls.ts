import { useQuery } from '@tanstack/react-query'
import { fetchCalls } from '../lib/api'

export function useCalls(orgId = 'default') {
  return useQuery({
    queryKey: ['calls', orgId],
    queryFn: () => fetchCalls(orgId),
    refetchInterval: 15_000, // auto-refresh every 15s to catch new completions
  })
}
