import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from './api'

export interface AsyncState<T> { data: T | null; loading: boolean; error: ApiError | null; reload: () => void }

/** Fetch-on-mount with loading + error state. No dependency added. */
export function useApi<T>(fn: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)
  const [tick, setTick] = useState(0)
  const alive = useRef(true)

  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])

  useEffect(() => {
    setLoading(true); setError(null)
    fn()
      .then((d) => { if (alive.current) { setData(d); setLoading(false) } })
      .catch((e) => {
        if (!alive.current) return
        setError(e instanceof ApiError ? e : new ApiError('UNKNOWN', String(e), 0))
        setLoading(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  return { data, loading, error, reload: useCallback(() => setTick((t) => t + 1), []) }
}

/** Imperative action with pending/error state, for buttons. */
export function useAction<A extends unknown[], R>(fn: (...a: A) => Promise<R>) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const run = useCallback(async (...a: A): Promise<R | null> => {
    setPending(true); setError(null)
    try { return await fn(...a) }
    catch (e) { setError(e instanceof ApiError ? e : new ApiError('UNKNOWN', String(e), 0)); return null }
    finally { setPending(false) }
  }, [fn])
  return { run, pending, error }
}

/** SSE run progress. Falls back to polling if the stream drops. */
export function useRunStream(runId: string | null, onEvent: (e: any) => void) {
  useEffect(() => {
    if (!runId) return
    const base = (import.meta as any).env?.VITE_API_URL ?? 'http://127.0.0.1:8000'
    const es = new EventSource(`${base}/api/v1/runs/${runId}/stream`)
    const handler = (ev: MessageEvent) => { try { onEvent(JSON.parse(ev.data)) } catch { /* ignore */ } }
    es.addEventListener('progress', handler as EventListener)
    es.addEventListener('complete', handler as EventListener)
    es.onerror = () => es.close()
    return () => es.close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId])
}
