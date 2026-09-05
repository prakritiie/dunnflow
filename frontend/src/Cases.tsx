import { api } from './lib/api'
import { useApi, useAction } from './lib/hooks'
import { SkeletonRows, ErrorState, NoRun } from './lib/states'
import { useState } from 'react'
import { fmtCurrency, fmtIST } from './data'
import { StateChip, RuleIdTag, ClassifierTierChip, Panel, SectionLabel, UnverifiedChip, MetricTile, Button } from './ui'
import Simulation from './Simulation'

const PAGE_SIZE = 50

// ─── Constraint trace component ───────────────────────────────────────────────

function ConstraintTracePanel({ expanded: initExpanded, trace }: { expanded?: boolean; trace: any[] }) {
  const CONSTRAINT_TRACE = trace
  const [expanded, setExpanded] = useState(initExpanded ?? false)
  const denies = CONSTRAINT_TRACE.filter((c: any) => c.decision === 'DENY')
  const allows = CONSTRAINT_TRACE.filter((c: any) => c.decision === 'ALLOW')

  return (
    <div className="bg-ink-900 border border-ink-700" style={{ borderRadius: 4 }}>
      <button
        className="w-full flex items-center justify-between px-4 h-10 border-b border-ink-800 hover:bg-ink-850 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <SectionLabel>Constraint Trace</SectionLabel>
          <span className="font-mono text-[11px] text-ink-500">
            {CONSTRAINT_TRACE.length} EVALUATED · {allows.length} ALLOW · {denies.length} DENY
          </span>
        </div>
        <svg
          width="12" height="12" viewBox="0 0 12 12" fill="none"
          className={`text-ink-500 transition-transform ${expanded ? 'rotate-180' : ''}`}
          style={{ transition: 'transform 180ms' }}
        >
          <path d="M2 4L6 8L10 4" stroke="currentColor" strokeWidth="1.2" />
        </svg>
      </button>

      {!expanded && (
        <div className="px-4 py-3 flex items-center gap-2">
          <span className="text-[13px] text-ink-300">{CONSTRAINT_TRACE.length} constraints evaluated</span>
          <span className="text-[11px] font-mono text-signal-positive">· {allows.length} ALLOW</span>
          {denies.length > 0 && <span className="text-[11px] font-mono text-signal-critical">· {denies.length} DENY</span>}
        </div>
      )}

      {expanded && (
        <div className="divide-y divide-ink-800">
          {CONSTRAINT_TRACE.map((c: any) => (
            <div key={c.id} className="flex items-start gap-4 px-4 py-3">
              <span className="font-mono text-[11px] text-ink-600 w-4 flex-none mt-0.5">{c.pos}</span>
              <span className="font-mono text-[12px] text-ink-300 w-44 flex-none truncate">{c.id}</span>
              <div className="flex items-center gap-2 flex-none">
                <span
                  className={`font-mono text-[11px] ${c.decision === 'ALLOW' ? 'text-signal-positive' : 'text-signal-critical'}`}
                >
                  {c.result}
                </span>
                {c.unverified && <UnverifiedChip />}
              </div>
              <span className="text-[12px] text-ink-400 flex-1 truncate">{c.note}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Case timeline ────────────────────────────────────────────────────────────

function CaseTimelinePanel({ timeline }: { timeline: any[] }) {
  const CASE_TIMELINE = timeline
  return (
    <div className="bg-ink-900 border border-ink-700" style={{ borderRadius: 4 }}>
      <div className="px-4 h-10 flex items-center border-b border-ink-800">
        <SectionLabel>Case Timeline</SectionLabel>
      </div>
      <div className="relative p-4 pl-8">
        <div className="absolute left-[28px] top-4 bottom-4 w-px bg-ink-700" />
        <div className="space-y-0">
          {CASE_TIMELINE.map((entry: any, i: number) => {
            const isLast = i === CASE_TIMELINE.length - 1
            const isDcp = entry.dcp
            const isAmbiguous = entry.ambiguous
            const nodeColor = isDcp
              ? '#2FA97C'
              : isAmbiguous
              ? '#22B8CF'
              : entry.ruleId
              ? '#3395FF'
              : '#3D4A5E'
            return (
              <div
                key={entry.seq}
                className={`relative flex gap-4 pb-5 ${isLast ? 'pb-0' : ''} ${isDcp ? 'dcp-reveal' : ''}`}
              >
                <div
                  className="absolute left-[-16px] w-2 h-2 rounded-full flex-none mt-1.5 z-10"
                  style={{ background: nodeColor, top: 4 }}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-3 flex-wrap mb-1">
                    <span className="font-mono text-[11px] text-ink-500">{fmtIST(entry.ts)}</span>
                    <span className="font-mono text-[12px] text-ink-200">{entry.node}</span>
                    <span className="font-mono text-[11px] text-ink-400">
                      {entry.from} → {entry.to}
                    </span>
                  </div>
                  {entry.ruleId && (
                    <div className="flex items-center gap-2 mb-1">
                      <RuleIdTag ruleId={entry.ruleId} />
                    </div>
                  )}
                  <p className={`text-[12px] ${isDcp ? 'text-signal-positive font-medium' : 'text-ink-400'}`}>
                    {entry.note}
                  </p>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ─── Case detail ──────────────────────────────────────────────────────────────

function CaseDetail({ caseData, timeline, trace }: { caseData: any; timeline: any[]; trace: any[] }) {
  return (
    <div className="space-y-4">
      <div className="bg-ink-900 border border-ink-700 p-4" style={{ borderRadius: 4 }}>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono text-[14px] text-ink-050">{caseData.obligationRef}</span>
              <StateChip status={caseData.status} />
            </div>
            <div className="flex items-center gap-4 text-[12px] text-ink-400">
              <span className="font-mono">{caseData.id}</span>
              <span>{caseData.merchantId}</span>
              <span className="font-mono">{fmtIST(caseData.createdAt)}</span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-[22px] font-semibold text-ink-050 tabular" style={{ letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums' }}>
              {fmtCurrency(caseData.amountMinor)}
            </div>
            <div className="text-[12px] text-ink-500">
              {caseData.failureClass} · {caseData.failureFamily}
            </div>
          </div>
        </div>
        <div className="mt-3 pt-3 border-t border-ink-800 flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <SectionLabel>Rule</SectionLabel>
            <RuleIdTag ruleId={caseData.ruleId} />
          </div>
          <div className="flex items-center gap-2">
            <SectionLabel>Classifier</SectionLabel>
            <ClassifierTierChip tier={caseData.classifierTier} conf={caseData.classifierConf} />
          </div>
          <div className="flex items-center gap-2">
            <SectionLabel>Attempts</SectionLabel>
            <span className="font-mono text-[13px] text-ink-200">{caseData.attempts}</span>
          </div>
        </div>
      </div>

      {timeline.length > 0 && <CaseTimelinePanel timeline={timeline} />}
      {trace.length > 0 && <ConstraintTracePanel expanded={false} trace={trace} />}
    </div>
  )
}

// ─── Inline HITL actions ──────────────────────────────────────────────────────

function InlineHitlActions({ caseRow, onDone }: { caseRow: any; onDone: () => void }) {
  const approveAction = useAction(api.approve)
  const rejectAction = useAction(api.reject)
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')

  const handleApprove = async (e: React.MouseEvent) => {
    e.stopPropagation()
    const r = await approveAction.run(caseRow.id, caseRow.id, 'operator')
    if (r) onDone()
  }

  const handleRejectSubmit = async (e: React.MouseEvent | React.FormEvent) => {
    e.stopPropagation()
    e.preventDefault()
    if (!reason.trim()) return
    const r = await rejectAction.run(caseRow.id, reason.trim(), 'operator')
    if (r) { setRejecting(false); setReason(''); onDone() }
  }

  if (rejecting) {
    return (
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={handleRejectSubmit}
        className="flex items-center gap-1.5"
      >
        <input
          autoFocus
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="reason (required)"
          className="h-6 px-2 w-32 bg-ink-950 border border-ink-600 text-[11px] text-ink-100 focus:border-blue-500 outline-none"
          style={{ borderRadius: 3 }}
        />
        <Button variant="danger" size="sm" onClick={handleRejectSubmit as any} disabled={!reason.trim() || rejectAction.pending}>
          {rejectAction.pending ? '…' : 'Confirm'}
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setRejecting(false)}>
          ✗
        </Button>
      </form>
    )
  }

  return (
    <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
      <Button variant="danger" size="sm" onClick={() => setRejecting(true)} disabled={approveAction.pending}>
        Reject
      </Button>
      <Button variant="primary" size="sm" onClick={handleApprove as any} loading={approveAction.pending}>
        Approve
      </Button>
      {(approveAction.error || rejectAction.error) && (
        <span className="text-[10px] text-signal-critical">{(approveAction.error ?? rejectAction.error)?.message}</span>
      )}
    </div>
  )
}

// ─── Metric banner ────────────────────────────────────────────────────────────

function MetricBanner({ runId }: { runId: string }) {
  const { data: run } = useApi(() => api.getRun(runId), [runId])
  const m = run?.metrics
  if (!m) return null
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      <MetricTile label="Recovered" value={`${m.recovered} / ${m.cases}`} accent />
      <MetricTile label="Amount recovered" value={fmtCurrency(m.amount_recovered_minor)} />
      <MetricTile
        label="Deferred"
        value={m.deferred ?? 0}
        sub={m.deferred_amount_minor ? fmtCurrency(m.deferred_amount_minor) : 'to next credit cycle'}
        highlight={m.deferred ? 'caution' : 'default'}
      />
      <MetricTile label="Escalated" value={m.escalated ?? 0} sub="awaiting human review" highlight={m.escalated ? 'caution' : 'default'} />
      <MetricTile
        label="Violations"
        value={m.compliance_violations ?? 0}
        highlight={m.compliance_violations ? 'critical' : 'positive'}
      />
      <MetricTile label="Duplicates prevented" value={m.duplicate_charge_prevented ?? 0} highlight="positive" />
    </div>
  )
}

// ─── Cases list (+ merged exceptions) ─────────────────────────────────────────

export default function Cases({ runId, selectedId, onSelect, onRunLaunched }: {
  runId: string | null; selectedId: string | null; onSelect: (id: string | null) => void
  onRunLaunched?: (runId: string) => void
}) {
  const [page, setPage] = useState(0)
  const [showLauncher, setShowLauncher] = useState(!runId)
  const { data, loading, error, reload } = useApi(
    () => (runId ? api.cases(runId, { limit: PAGE_SIZE, offset: page * PAGE_SIZE }) : Promise.resolve(null as any)), [runId, page])
  const { data: timeline } = useApi(
    () => (selectedId && runId ? api.timeline(selectedId, runId) : Promise.resolve([])), [selectedId, runId])
  const { data: trace } = useApi(
    () => (selectedId && runId ? api.constraints(selectedId, runId) : Promise.resolve([])), [selectedId, runId])

  const launcher = (
    <Panel
      title="Run launcher"
      action={runId && (
        <button onClick={() => setShowLauncher((v) => !v)} className="text-[11px] font-mono text-ink-400 hover:text-ink-100">
          {showLauncher ? 'Hide' : 'New run'}
        </button>
      )}
    >
      {showLauncher ? (
        <Simulation onRunReady={(id) => { setShowLauncher(false); onRunLaunched?.(id); reload() }} />
      ) : (
        <span className="text-[12px] text-ink-500">A run is active. Open this panel to launch another.</span>
      )}
    </Panel>
  )

  if (!runId) {
    return (
      <div className="p-6 max-w-[900px] mx-auto space-y-6">
        <NoRun />
        <Simulation onRunReady={(id) => { onRunLaunched?.(id); reload() }} />
      </div>
    )
  }
  if (error) return <ErrorState error={error} onRetry={reload} />
  if (loading || !data) return <div className="p-6"><SkeletonRows rows={10} cols={5} /></div>

  const CASES: any[] = (data?.items ?? []).map((c: any) => ({
    ...c,
    id: c.case_ref ?? c.id,
    caseId: c.case_ref ?? c.id,
    obligationRef: c.obligation_ref ?? c.obligationRef ?? '',
    merchantId: c.merchant_id ?? c.merchantId ?? '',
    failureClass: c.failure_class ?? c.failureClass ?? '',
    failureFamily: c.failure_family ?? c.failureFamily ?? '',
    amountMinor: c.amount_minor ?? c.amountMinor ?? 0,
    ruleId: c.rule_id ?? c.ruleId ?? '',
    classifierTier: c.classifier_tier ?? c.classifierTier ?? 'T1',
    classifierConf: c.classifier_conf ?? c.classifierConf ?? 1.0,
    createdAt: c.created_at ?? c.createdAt ?? '',
    attempts: c.attempts ?? c.attempt_count ?? 0,
  }))
  const CASE_TIMELINE: any[] = (timeline ?? []).map((t: any) => ({
    ...t,
    ts: t.occurred_at ?? t.ts ?? '',
    ruleId: t.rule_id ?? t.ruleId,
    from: t.state_from ?? t.from ?? '',
    to: t.state_to ?? t.to ?? '',
    node: t.node ?? '',
    note: t.note ?? '',
  }))
  const CONSTRAINT_TRACE: any[] = (trace ?? []).map((c: any) => ({
    ...c,
    pos: c.position ?? c.pos ?? 0,
    id: c.constraint_id ?? c.id ?? '',
    decision: c.decision ?? 'ALLOW',
    result: c.decision ?? 'ALLOW',
    note: c.reason ?? c.note ?? '',
    unverified: c.unverified ?? false,
  }))

  const selectedCase = selectedId ? CASES.find((c: any) => c.id === selectedId || c.caseId === selectedId) : null
  const total: number = data.total ?? CASES.length
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <MetricBanner runId={runId} />
      {launcher}

      <div className="flex h-[560px] border border-ink-800" style={{ borderRadius: 4 }}>
        {/* Case list */}
        <div className={`flex flex-col border-r border-ink-800 ${selectedCase ? 'w-80 flex-none' : 'flex-1'}`}>
          <div className="flex items-center justify-between px-4 h-10 border-b border-ink-800 flex-none">
            <SectionLabel>Cases</SectionLabel>
            <span className="font-mono text-[11px] text-ink-500">{total} total</span>
          </div>

          <div className="flex-1 overflow-auto">
            <table className="w-full">
              <thead>
                <tr className="sticky top-0 bg-ink-850 hairline-b">
                  <th className="px-4 py-2.5 text-left text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em]">Case / Ref</th>
                  {!selectedCase && (
                    <>
                      <th className="px-3 py-2.5 text-left text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em]">Failure</th>
                      <th className="px-3 py-2.5 text-left text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em]">Rule</th>
                      <th className="px-3 py-2.5 text-right text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em]">Amount</th>
                    </>
                  )}
                  <th className="px-3 py-2.5 text-left text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em]">Status</th>
                  <th className="px-3 py-2.5 text-left text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em]">Action</th>
                </tr>
              </thead>
              <tbody>
                {CASES.map((c: any) => {
                  const isSelected = c.id === selectedId
                  const needsHuman = c.status === 'NEEDS_HUMAN'
                  return (
                    <tr
                      key={c.id}
                      onClick={() => onSelect(isSelected ? null : c.id)}
                      className={`border-b border-ink-800 cursor-pointer hover:bg-ink-850 ${isSelected ? 'row-selected' : needsHuman ? 'row-escalated' : ''}`}
                    >
                      <td className="px-4 py-2.5">
                        <div className="font-mono text-[12px] text-ink-200">{c.id}</div>
                        <div className="font-mono text-[11px] text-ink-500">{c.obligationRef}</div>
                      </td>
                      {!selectedCase && (
                        <>
                          <td className="px-3 py-2.5">
                            <div className="font-mono text-[11px] text-ink-300 truncate max-w-[140px]">{c.failureClass}</div>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className="font-mono text-[11px] text-ink-500 truncate max-w-[160px] block">{c.ruleId}</span>
                          </td>
                          <td className="px-3 py-2.5 text-right">
                            <span className="font-mono text-[13px] text-ink-050 tabular">{fmtCurrency(c.amountMinor)}</span>
                          </td>
                        </>
                      )}
                      <td className="px-3 py-2.5">
                        <StateChip status={c.status} small />
                      </td>
                      <td className="px-3 py-2.5">
                        {needsHuman ? (
                          <InlineHitlActions caseRow={c} onDone={reload} />
                        ) : (
                          <span className="text-[11px] text-ink-700">—</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="px-4 py-3 border-t border-ink-800 flex items-center justify-between flex-none">
            <span className="text-[12px] text-ink-500">
              Showing {CASES.length ? page * PAGE_SIZE + 1 : 0}–{page * PAGE_SIZE + CASES.length} of {total}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="text-[12px] text-ink-400 hover:text-ink-100 disabled:opacity-40 disabled:cursor-not-allowed font-mono px-2 py-1 border border-ink-700 hover:border-ink-600"
                style={{ borderRadius: 3 }}
              >
                ← Prev
              </button>
              <span className="font-mono text-[12px] text-ink-300 px-2">{page + 1} / {totalPages}</span>
              <button
                onClick={() => setPage((p) => (p + 1 < totalPages ? p + 1 : p))}
                disabled={page + 1 >= totalPages}
                className="text-[12px] text-ink-400 hover:text-ink-100 disabled:opacity-40 disabled:cursor-not-allowed font-mono px-2 py-1 border border-ink-700 hover:border-ink-600"
                style={{ borderRadius: 3 }}
              >
                Next →
              </button>
            </div>
          </div>
        </div>

        {/* Detail pane */}
        {selectedCase && (
          <div className="flex-1 overflow-auto p-4">
            <button
              onClick={() => onSelect(null)}
              className="text-[12px] text-ink-400 hover:text-ink-100 font-mono mb-4 flex items-center gap-1.5"
            >
              ← Back to list
            </button>
            <CaseDetail caseData={selectedCase} timeline={CASE_TIMELINE} trace={CONSTRAINT_TRACE} />
          </div>
        )}
      </div>
    </div>
  )
}
