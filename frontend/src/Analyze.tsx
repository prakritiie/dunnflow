import { useMemo, useState } from 'react'
import { api, type CaseIntakeInput, type CaseIntakeResult } from './lib/api'
import { useAction } from './lib/hooks'
import { MetricTile, Panel, SectionLabel, StateChip } from './ui'

const defaultForm: CaseIntakeInput = {
  merchant_id: 'M-20481',
  obligation_ref: 'OBL-88142',
  amount_minor: 214000,
  failure_source: 'gateway',
  failure_step: 'payment_authorization',
  failure_reason: 'gateway_timeout',
  error_description: 'The payment gateway timed out while authorising the card and the customer was not charged, but the flow was left in a stale state for retry.',
  customer_tokens: ['alice@example.com', '4111 1111 1111 1111'],
  retry_count: 2,
}

export default function Analyze() {
  const [form, setForm] = useState<CaseIntakeInput>(defaultForm)
  const [result, setResult] = useState<CaseIntakeResult | null>(null)
  const { run, pending, error } = useAction(api.classifyCase)

  const summary = useMemo(() => {
    if (!result) return 'No case submitted yet.'
    return `${result.classification.code} · ${result.decision.action} · ${result.summary}`
  }, [result])

  const update = <K extends keyof CaseIntakeInput>(key: K, value: CaseIntakeInput[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const next = await run(form)
    if (next) setResult(next)
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-7xl mx-auto flex flex-col gap-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-[0.12em] text-ink-500">Analyze</div>
            <h1 className="mt-1 text-3xl font-semibold text-ink-050">Diagnostics &amp; policy dry-run</h1>
            <p className="mt-1 text-[13px] text-ink-400 max-w-2xl">
              Classify a hand-entered case and preview what the policy engine would do. This is a
              dry run only — nothing is attempted, nothing is charged, and no case enters a live
              batch. Use it to inspect the classifier and rule matrix before trusting them with a run.
            </p>
          </div>
          <StateChip status={result ? result.status : 'READY'} small />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-[1.15fr_0.85fr] gap-6">
          <Panel title="Create case">
            <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="flex flex-col gap-2 text-[12px] text-ink-300">
                Merchant ID
                <input
                  value={form.merchant_id}
                  onChange={(e) => update('merchant_id', e.target.value)}
                  className="bg-ink-950 border border-ink-700 px-3 py-2 text-ink-050 focus:border-blue-500 outline-none"
                />
              </label>

              <label className="flex flex-col gap-2 text-[12px] text-ink-300">
                Obligation ref
                <input
                  value={form.obligation_ref}
                  onChange={(e) => update('obligation_ref', e.target.value)}
                  className="bg-ink-950 border border-ink-700 px-3 py-2 text-ink-050 focus:border-blue-500 outline-none"
                />
              </label>

              <label className="flex flex-col gap-2 text-[12px] text-ink-300">
                Amount (minor)
                <input
                  type="number"
                  value={form.amount_minor}
                  onChange={(e) => update('amount_minor', Number(e.target.value || 0))}
                  className="bg-ink-950 border border-ink-700 px-3 py-2 text-ink-050 focus:border-blue-500 outline-none"
                />
              </label>

              <label className="flex flex-col gap-2 text-[12px] text-ink-300">
                Retry count
                <input
                  type="number"
                  value={form.retry_count ?? 0}
                  onChange={(e) => update('retry_count', Number(e.target.value || 0))}
                  className="bg-ink-950 border border-ink-700 px-3 py-2 text-ink-050 focus:border-blue-500 outline-none"
                />
              </label>

              <label className="flex flex-col gap-2 text-[12px] text-ink-300">
                Failure source
                <input
                  value={form.failure_source}
                  onChange={(e) => update('failure_source', e.target.value)}
                  className="bg-ink-950 border border-ink-700 px-3 py-2 text-ink-050 focus:border-blue-500 outline-none"
                />
              </label>

              <label className="flex flex-col gap-2 text-[12px] text-ink-300">
                Failure step
                <input
                  value={form.failure_step}
                  onChange={(e) => update('failure_step', e.target.value)}
                  className="bg-ink-950 border border-ink-700 px-3 py-2 text-ink-050 focus:border-blue-500 outline-none"
                />
              </label>

              <label className="flex flex-col gap-2 text-[12px] text-ink-300 md:col-span-2">
                Failure reason
                <input
                  value={form.failure_reason}
                  onChange={(e) => update('failure_reason', e.target.value)}
                  className="bg-ink-950 border border-ink-700 px-3 py-2 text-ink-050 focus:border-blue-500 outline-none"
                />
              </label>

              <label className="flex flex-col gap-2 text-[12px] text-ink-300 md:col-span-2">
                Error description (free text)
                <textarea
                  value={form.error_description}
                  onChange={(e) => update('error_description', e.target.value)}
                  rows={5}
                  className="bg-ink-950 border border-ink-700 px-3 py-2 text-ink-050 focus:border-blue-500 outline-none"
                />
              </label>

              <label className="flex flex-col gap-2 text-[12px] text-ink-300 md:col-span-2">
                Customer tokens for masking
                <input
                  value={form.customer_tokens.join(', ')}
                  onChange={(e) => update('customer_tokens', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
                  className="bg-ink-950 border border-ink-700 px-3 py-2 text-ink-050 focus:border-blue-500 outline-none"
                />
              </label>

              <div className="md:col-span-2 flex items-center justify-between gap-3 pt-2 border-t border-ink-800">
                <div className="text-[12px] text-ink-400">Input is sanitized and PII-masked before the model sees it.</div>
                <button
                  type="submit"
                  disabled={pending}
                  className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-4 py-2 text-[12px] font-medium text-white"
                  style={{ borderRadius: 4 }}
                >
                  {pending ? 'Classifying…' : 'Run diagnostics'}
                </button>
              </div>

              {error && (
                <div className="md:col-span-2 text-[12px] text-signal-critical border border-signal-critical bg-signal-critical/10 px-3 py-2">
                  {error.message}
                </div>
              )}
            </form>
          </Panel>

          <div className="flex flex-col gap-4">
            <Panel title="Classifier diagnostics">
              <div className="flex flex-col gap-4">
                <MetricTile label="Case ref" value={result?.case_ref ?? '—'} large accent />
                <div className="text-[12px] text-ink-300 bg-ink-950 border border-ink-800 p-3" style={{ borderRadius: 4 }}>
                  {summary}
                </div>

                {result ? (
                  <>
                    <div className="grid grid-cols-2 gap-3">
                      <MetricTile label="Classification" value={result.classification.code} sub={result.classification.tier} accent />
                      <MetricTile label="Confidence" value={`${(result.classification.confidence * 100).toFixed(0)}%`} sub={result.classification.tier === 'T3' ? 'model confidence' : 'deterministic — no model call'} />
                    </div>
                    <div className="text-[12px] text-ink-300 border border-ink-800 bg-ink-950 p-3" style={{ borderRadius: 4 }}>
                      <div className="font-medium text-ink-200 mb-2">Sanitized evidence</div>
                      <div className="text-ink-400 whitespace-pre-wrap">{result.sanitizer.masked_text || 'No PII-bearing evidence was retained.'}</div>
                    </div>
                  </>
                ) : (
                  <div className="text-[12px] text-ink-400 border border-dashed border-ink-700 p-3 text-center">
                    Submit a case to see the classifier's tier, confidence, and sanitized evidence.
                  </div>
                )}
              </div>
            </Panel>

            <Panel title="Policy rule dry-run" count={result ? undefined : 'no case yet'}>
              {result ? (
                <div className="flex flex-col gap-3">
                  <div className="grid grid-cols-2 gap-3">
                    <MetricTile label="Directive" value={result.decision.action} sub={result.decision.rule_id} />
                    <MetricTile label="Attempts remaining" value={String(result.decision.attempts_remaining)} />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <MetricTile
                      label="Money movement"
                      value={result.taxonomy.recoverable ? 'ALLOWED' : 'BLOCKED'}
                      highlight={result.taxonomy.recoverable ? 'positive' : 'critical'}
                      sub={`terminality: ${result.taxonomy.terminality}`}
                    />
                    <MetricTile
                      label="Human approval"
                      value={result.decision.requires_human_approval ? 'REQUIRED' : 'not required'}
                      highlight={result.decision.requires_human_approval ? 'caution' : 'default'}
                    />
                  </div>
                  <div className="text-[11px] text-ink-500 border-t border-ink-800 pt-3">
                    This is a preview only — no attempt was executed, no constraint kernel evaluation ran, and no
                    money moved. To act on a case, ingest it into a run from the Cases screen.
                  </div>
                </div>
              ) : (
                <div className="text-[12px] text-ink-400 text-center py-4">
                  The rule the policy engine would select appears here once a case is submitted.
                </div>
              )}
            </Panel>
          </div>
        </div>
      </div>
    </div>
  )
}
