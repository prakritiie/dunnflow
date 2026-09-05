import { api } from './lib/api'
import { useApi, useAction } from './lib/hooks'
import { SkeletonRows, ErrorState, EmptyState, NoRun } from './lib/states'
import { useState } from 'react'
import { fmtIST } from './data'
import { RuleIdTag, SectionLabel } from './ui'

// All 12 constraint IDs — show every one, grey out with zero refusals
const ALL_CONSTRAINTS = [
  'C_AMBIGUITY_CHECK',
  'C_ATTEMPT_CAP',
  'C_VELOCITY_LIMIT',
  'C_PROHIBITED_CLASS',
  'C_HARD_CLASS',
  'C_AMOUNT_CEILING',
  'C_INSTRUMENT_VALID',
  'C_ISSUER_SENTINEL',
  'C_CIRCUIT_BREAKER',
  'C_IDEMPOTENCY_LOCK',
  'C_COMPLIANCE_WINDOW',
  'C_KILL_SWITCH',
]


export default function RefusalLedger({ runId, onOpenCase, runLabel }: { runId: string | null; onOpenCase: (ref: string) => void; runLabel?: string }) {
  const { data, loading, error, reload } = useApi(
    () => (runId ? api.refusals(runId) : Promise.resolve([])), [runId])
  const { data: summaryData } = useApi(
    () => (runId ? api.refusalSummary(runId) : Promise.resolve([])), [runId])

  const [filterConstraint, setFilterConstraint] = useState('')
  const [filterRule, setFilterRule] = useState('')

  if (!runId) return <NoRun />
  if (error) return <ErrorState error={error} onRetry={reload} />
  if (loading) return <div className="p-6"><SkeletonRows rows={8} cols={5} /></div>

  const REFUSALS: any[] = (data ?? []).map((r: any) => ({ ...r, caseId: r.case_ref, ruleId: r.rule_id, constraintId: r.constraint_id, failureClass: r.failure_class, ts: r.evaluated_at }))
  // Server-computed summary — includes zero-count constraints so the filter
  // rail can show every constraint that exists, not just the ones with hits.
  const SUMMARY: any[] = summaryData ?? []
  const REFUSAL_COUNTS: Record<string, number> = {}
  SUMMARY.forEach((s: any) => { REFUSAL_COUNTS[s.constraint_id] = s.refusals ?? 0 })

  const ALL_RULES = [...new Set(REFUSALS.map((r: any) => r.ruleId))]

  const filtered = REFUSALS.filter((r: any) => {
    if (filterConstraint && r.constraintId !== filterConstraint) return false
    if (filterRule && r.ruleId !== filterRule) return false
    return true
  })

  const grouped: Record<string, typeof REFUSALS> = {}
  filtered.forEach((r) => {
    if (!grouped[r.constraintId]) grouped[r.constraintId] = []
    grouped[r.constraintId].push(r)
  })

  return (
    <div className="flex h-full">
      {/* Filter rail */}
      <div className="w-52 flex-none border-r border-ink-800 flex flex-col overflow-hidden">
        <div className="px-3 h-10 flex items-center border-b border-ink-800 flex-none">
          <SectionLabel>Filter</SectionLabel>
        </div>
        <div className="flex-1 overflow-auto p-2 space-y-4">
          {/* Constraint filter */}
          <div>
            <div className="text-[10px] font-medium text-ink-600 uppercase tracking-[0.08em] mb-1.5 px-1">Constraint</div>
            <button
              onClick={() => setFilterConstraint('')}
              className={`w-full text-left text-[12px] px-2 py-1.5 font-mono mb-1 ${!filterConstraint ? 'text-blue-500 bg-blue-tint' : 'text-ink-400 hover:text-ink-100'}`}
              style={{ borderRadius: 3 }}
            >
              All ({REFUSALS.length})
            </button>
            <div className="space-y-0.5">
              {ALL_CONSTRAINTS.map((c: any) => {
                const count = REFUSAL_COUNTS[c] ?? 0
                const hasRefusals = count > 0
                return (
                  <button
                    key={c}
                    onClick={() => hasRefusals && setFilterConstraint(filterConstraint === c ? '' : c)}
                    disabled={!hasRefusals}
                    className={`w-full flex items-center justify-between text-left text-[11px] px-2 py-1 font-mono ${
                      filterConstraint === c
                        ? 'text-blue-500 bg-blue-tint'
                        : hasRefusals
                        ? 'text-ink-400 hover:text-ink-100 hover:bg-ink-850'
                        : 'text-ink-700 cursor-default'
                    }`}
                    style={{ borderRadius: 3 }}
                    title={c}
                  >
                    <span className="truncate">{c.replace('C_', '')}</span>
                    {hasRefusals ? (
                      <span className="font-mono text-[10px] ml-1 flex-none">{count}</span>
                    ) : (
                      <span className="font-mono text-[10px] ml-1 flex-none text-ink-800">0</span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Rule filter */}
          <div>
            <div className="text-[10px] font-medium text-ink-600 uppercase tracking-[0.08em] mb-1.5 px-1">Rule</div>
            <div className="space-y-0.5">
              {ALL_RULES.map((r: any) => (
                <button
                  key={r}
                  onClick={() => setFilterRule(filterRule === r ? '' : r)}
                  className={`w-full text-left text-[11px] px-2 py-1 font-mono truncate ${filterRule === r ? 'text-blue-500 bg-blue-tint' : 'text-ink-400 hover:text-ink-100 hover:bg-ink-850'}`}
                  style={{ borderRadius: 3 }}
                  title={r}
                >
                  {r.replace(/_\d{3}$/, '')}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Table area */}
      <div className="flex-1 overflow-auto flex flex-col">
        <div className="sticky top-0 z-10 bg-ink-950 px-4 py-2.5 border-b border-ink-800 flex items-center justify-between flex-none">
          <div className="flex items-center gap-3">
            <SectionLabel>Refusal Ledger</SectionLabel>
            <span className="font-mono text-[11px] text-ink-500">{filtered.length} refusals</span>
          </div>
          <p className="text-[11px] text-ink-600 hidden md:block font-mono">
            EVERY evaluation is persisted — passes included. Partial logging cannot be suspected.
          </p>
        </div>

        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center flex-1 gap-2">
            <p className="text-[14px] text-ink-300">No refusals match the current filter.</p>
            <p className="text-[12px] text-ink-500">
              Clear filters to see all {REFUSALS.length} refusals.
            </p>
          </div>
        ) : (
          <div className="flex-1 overflow-auto">
            <div className="p-4 space-y-4">
              {Object.entries(grouped).map(([constraintId, entries]) => (
                <div key={constraintId} className="bg-ink-900 border border-ink-700" style={{ borderRadius: 4 }}>
                  <div className="flex items-center justify-between px-4 h-9 border-b border-ink-800 bg-ink-850">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-[12px] text-ink-300">{constraintId}</span>
                      <span className="text-[11px] text-ink-500">{entries.length} refusal{entries.length > 1 ? 's' : ''}</span>
                    </div>
                    <span
                      className="text-[10px] font-mono text-signal-critical border border-signal-critical chip-critical px-[6px] py-[1px] uppercase"
                      style={{ borderRadius: 3 }}
                    >
                      DENY
                    </span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[640px]">
                      <thead>
                        <tr className="border-b border-ink-800 bg-ink-850 sticky top-9">
                          <th className="px-4 py-2 text-left text-[11px] font-medium text-ink-500 uppercase tracking-[0.08em]">Case</th>
                          <th className="px-3 py-2 text-left text-[11px] font-medium text-ink-500 uppercase tracking-[0.08em]">Rule</th>
                          <th className="px-3 py-2 text-left text-[11px] font-medium text-ink-500 uppercase tracking-[0.08em]">Failure Class</th>
                          <th className="px-3 py-2 text-left text-[11px] font-medium text-ink-500 uppercase tracking-[0.08em]">Reason</th>
                          <th className="px-3 py-2 text-right text-[11px] font-medium text-ink-500 uppercase tracking-[0.08em]">Time</th>
                        </tr>
                      </thead>
                      <tbody>
                        {entries.map((r, i) => (
                          <tr
                            key={i}
                            className="row-refused border-b border-ink-800 last:border-b-0 hover:bg-ink-850 transition-colors"
                          >
                            <td className="px-4 py-2.5">
                              <span className="font-mono text-[12px] text-ink-200">{r.caseId}</span>
                            </td>
                            <td className="px-3 py-2.5">
                              <RuleIdTag ruleId={r.ruleId} />
                            </td>
                            <td className="px-3 py-2.5">
                              <span className="font-mono text-[11px] text-ink-400">{r.failureClass}</span>
                            </td>
                            <td className="px-3 py-2.5">
                              <span className="text-[12px] text-ink-300">{r.reason}</span>
                            </td>
                            <td className="px-3 py-2.5 text-right">
                              <span className="font-mono text-[11px] text-ink-500 tabular" style={{ fontVariantNumeric: 'tabular-nums' }}>
                                {fmtIST(r.ts).split(' ')[1]}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>

            <div className="px-4 py-4 border-t border-ink-800 bg-ink-950">
              <p className="text-[12px] text-ink-500">
                Showing all refusals from run {' '}
                <span className="font-mono text-ink-400">{runLabel ?? runId ?? '—'}</span>. Stored in{' '}
                <span className="font-mono text-ink-400">constraint_evaluations</span> — passes persisted alongside denials.
                {' '}Constraints with 0 refusals are greyed in the filter — they exist, they passed.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
