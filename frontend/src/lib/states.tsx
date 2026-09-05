import type { ApiError } from './api'

/** Skeleton rows matching real row height so content does not jump on load. */
export function SkeletonRows({ rows = 6, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div aria-busy="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 border-b border-ink-800" style={{ height: 40 }}>
          {Array.from({ length: cols }).map((_, j) => (
            <div key={j} className="h-3 bg-ink-850 animate-pulse"
                 style={{ width: `${[40, 70, 55, 30][j % 4]}%`, borderRadius: 3 }} />
          ))}
        </div>
      ))}
    </div>
  )
}

/** Panel-level error. States the fix, never leaks internals. */
export function ErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  const offline = error.code === 'NETWORK_ERROR'
  return (
    <div className="p-6 text-center" style={{ minHeight: 120 }}>
      <div className="text-[14px] font-medium text-signal-critical mb-1">
        {offline ? 'Backend unreachable' : 'Could not load this view'}
      </div>
      <div className="text-[13px] text-ink-400 mb-3">{error.message}</div>
      <div className="font-mono text-[11px] text-ink-600 mb-3">{error.code}</div>
      {onRetry && (
        <button onClick={onRetry}
                className="h-8 px-3 text-[13px] text-ink-200 border border-ink-600 hover:bg-ink-850"
                style={{ borderRadius: 3 }}>Retry</button>
      )}
    </div>
  )
}

/** Empty states state the condition - they are often meaningful information. */
export function EmptyState({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className="p-6 text-center" style={{ minHeight: 120 }}>
      <div className="text-[13px] text-ink-300">{message}</div>
      {hint && <div className="text-[12px] text-ink-500 mt-1">{hint}</div>}
    </div>
  )
}

export function NoRun() {
  return (
    <EmptyState
      message="No completed run yet."
      hint="Start one from Simulation to populate this view."
    />
  )
}
