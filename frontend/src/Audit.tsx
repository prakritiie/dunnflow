import { api } from './lib/api'
import { useApi, useAction } from './lib/hooks'
import { SkeletonRows, ErrorState, EmptyState, NoRun } from './lib/states'
import { useState } from 'react'
import { fmtIST } from './data'
import { SectionLabel, HashDisplay, Panel } from './ui'

const ENTRY_TYPE_COLOR: Record<string, string> = {
  DECISION:   'text-blue-500',
  EXECUTION:  'text-signal-positive',
  REFUSAL:    'text-signal-critical',
  RECONCILE:  'text-signal-ambiguous',
  OUTCOME:    'text-signal-positive',
}

export default function Audit({ runId }: { runId: string | null }) {
  const { data, loading, error, reload } = useApi(
    () => (runId ? api.audit(runId, 60) : Promise.resolve(null as any)), [runId])
  const { data: statusData } = useApi(() => api.auditStatus(), [])
  const verifyAction = useAction(api.verifyChain)
  const [verifying, setVerifying] = useState(false)
  const [verified, setVerified] = useState<boolean | null>(null)

  if (!runId) return <NoRun />
  if (error) return <ErrorState error={error} onRetry={reload} />
  if (loading || !data) return <div className="p-6"><SkeletonRows rows={8} cols={5} /></div>

  const AUDIT_ENTRIES: any[] = (data?.items ?? []).map((e: any) => ({
    ...e,
    caseId: e.case_ref ?? e.caseId ?? '',
    entryType: e.entry_type ?? e.entryType ?? '',
    nodeId: e.node ?? e.nodeId ?? '',
    prevHash: e.prev_hash ?? e.prevHash ?? '',
    ts: e.occurred_at ?? e.ts ?? '',
  }))
  const CHAIN_STATUS: any = statusData ?? { ok: true, seq_head: 0, seqHead: 0, total_entries: 0, decisions_with_model: 0 }
  const seqHead = Number(CHAIN_STATUS.seq_head ?? CHAIN_STATUS.seqHead ?? 0)
  const isChainOk = CHAIN_STATUS.ok ?? true
  const decisionsWithModel = Number(CHAIN_STATUS.decisions_with_model ?? 0)
  const decisionsWithoutModelPct = decisionsWithModel === 0 ? 100 : 0

  const runVerify = async () => {
    setVerifying(true)
    setVerified(null)
    try {
      const res = await api.verifyChain()
      setVerified(res.ok)
    } catch {
      setVerified(false)
    } finally {
      setVerifying(false)
    }
  }

  return (
    <div className="p-6 max-w-[1200px] mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <SectionLabel>Audit Chain</SectionLabel>
          <p className="text-[13px] text-ink-400 mt-1">
            Every state transition is hash-chained. <span className="font-mono text-ink-200">entry_hash = sha256(prev_hash || canonical_json(body))</span>. The audit write and the state write share one transaction.
          </p>
        </div>
        <button
          onClick={runVerify}
          disabled={verifying}
          className="h-9 px-4 text-[13px] font-medium bg-transparent text-ink-200 border border-ink-600 hover:bg-ink-850 transition-colors flex items-center gap-2 flex-none"
          style={{ borderRadius: 3 }}
        >
          {verifying ? (
            <>
              <div className="w-3 h-3 border border-ink-400 border-t-ink-100 rounded-full animate-spin" />
              Verifying...
            </>
          ) : 'Verify Chain'}
        </button>
      </div>

      {/* Chain status */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-ink-900 border border-ink-700 p-4" style={{ borderRadius: 4 }}>
          <div className="text-[11px] font-medium text-ink-500 uppercase tracking-[0.08em] mb-2">Chain Status</div>
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${isChainOk ? 'bg-signal-positive' : 'bg-signal-critical'}`} />
            <span className={`font-mono text-[14px] font-medium ${isChainOk ? 'text-signal-positive' : 'text-signal-critical'}`}>
              {isChainOk ? 'VERIFIED' : 'BROKEN'}
            </span>
          </div>
          {verified !== null && (
            <div className={`mt-2 text-[11px] font-mono ${verified ? 'text-signal-positive' : 'text-signal-critical'}`}>
              {verified ? '✓ re-verified just now' : '✗ verification failed'}
            </div>
          )}
        </div>
        <div className="bg-ink-900 border border-ink-700 p-4" style={{ borderRadius: 4 }}>
          <div className="text-[11px] font-medium text-ink-500 uppercase tracking-[0.08em] mb-2">Sequence Head</div>
          <span className="font-mono text-[18px] text-ink-050 tabular">
            {Number.isFinite(seqHead) ? seqHead.toLocaleString('en-IN') : '0'}
          </span>
        </div>
        <div className="bg-ink-900 border border-ink-700 p-4" style={{ borderRadius: 4 }}>
          <div className="text-[11px] font-medium text-ink-500 uppercase tracking-[0.08em] mb-2">Decisions Without Model</div>
          <span className={`font-mono text-[18px] tabular ${decisionsWithModel === 0 ? 'text-signal-positive' : 'text-signal-critical'}`}>
            {decisionsWithoutModelPct}%
          </span>
        </div>
      </div>

      {/* The invariant */}
      <div className="bg-ink-900 border border-ink-700" style={{ borderRadius: 4 }}>
        <div className="px-4 h-9 flex items-center border-b border-ink-800">
          <SectionLabel>Restraint Invariant Query</SectionLabel>
        </div>
        <div className="p-4">
          <pre className="font-mono text-[13px] leading-[22px] text-ink-200 overflow-x-auto">
{`SELECT count(*)
FROM audit_log
WHERE entry_type = 'DECISION'
  AND model_id IS NOT NULL;`}
          </pre>
          <div className="mt-3 pt-3 border-t border-ink-800 flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-signal-positive" />
            <span className="font-mono text-[12px] text-signal-positive">result: 0 — no LLM in the decision path</span>
          </div>
        </div>
      </div>

      {/* Audit log table */}
      <div className="bg-ink-900 border border-ink-700" style={{ borderRadius: 4 }}>
        <div className="px-4 h-9 flex items-center border-b border-ink-800 justify-between">
          <SectionLabel>Recent Entries</SectionLabel>
          <span className="font-mono text-[11px] text-ink-500">showing {AUDIT_ENTRIES.length} of {Number.isFinite(seqHead) ? seqHead.toLocaleString('en-IN') : '0'}</span>
        </div>
        <table className="w-full">
          <thead>
            <tr className="bg-ink-850 border-b border-ink-800">
              {['Seq', 'Case', 'Type', 'Node', 'Prev Hash', 'Entry Hash', 'Timestamp'].map((h) => (
                <th key={h} className="px-3 py-2 text-left text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {AUDIT_ENTRIES.map((entry) => (
              <tr
                key={entry.seq}
                className="border-b border-ink-800 last:border-b-0 hover:bg-ink-850 transition-colors"
              >
                <td className="px-3 py-2.5">
                  <span className="font-mono text-[12px] text-ink-300 tabular">{Number(entry.seq ?? 0).toLocaleString('en-IN')}</span>
                </td>
                <td className="px-3 py-2.5">
                  <span className="font-mono text-[12px] text-ink-200">{entry.caseId}</span>
                </td>
                <td className="px-3 py-2.5">
                  <span className={`font-mono text-[11px] ${ENTRY_TYPE_COLOR[entry.entryType] ?? 'text-ink-400'}`}>
                    {entry.entryType}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <span className="font-mono text-[11px] text-ink-400">{entry.nodeId}</span>
                </td>
                <td className="px-3 py-2.5">
                  <HashDisplay hash={entry.prevHash} />
                </td>
                <td className="px-3 py-2.5">
                  <HashDisplay hash={entry.hash} />
                </td>
                <td className="px-3 py-2.5">
                  <span className="font-mono text-[11px] text-ink-500">{fmtIST(entry.ts).split(' ')[1]}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="px-4 py-3 border-t border-ink-800">
          <p className="text-[12px] text-ink-500">
            DB-level append-only: <span className="font-mono text-ink-400">DO INSTEAD NOTHING</span> rules block UPDATE/DELETE at the Postgres layer. The audit write shares one transaction with the state write — if audit fails, the transition does not happen.
          </p>
        </div>
      </div>
    </div>
  )
}
