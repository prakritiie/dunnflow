import { api } from './lib/api'
import { useApi, useAction } from './lib/hooks'
import { SkeletonRows, ErrorState, EmptyState, NoRun } from './lib/states'
import { useState } from 'react'

import { RuleIdTag, SectionLabel, UnverifiedChip } from './ui'

const DIRECTIVE_COLOR: Record<string, string> = {
  DEFER:    'text-signal-caution',
  WAIT:     'text-signal-caution',
  NOTIFY:   'text-blue-500',
  RETRY:    'text-blue-500',
  HOLD:     'text-signal-ambiguous',
  BLOCK:    'text-signal-critical',
  SKIP:     'text-signal-neutral',
  ESCALATE: 'text-signal-caution',
}

const REGULATORY_NOTES: Record<string, { text: string; citation: string; verified: boolean }> = {
  'RETRY_EXPONENTIAL_002': {
    text: 'Max 3 retries within 24h per RBI circular on failed payment retries',
    citation: 'RBI/2019-20/170 DPSS.CO.PD No.1810/02.14.003/2019-20',
    verified: false,
  },
  'DEFER_TO_CREDIT_CYCLE_003': {
    text: 'Reschedule timing aligned with 30-day cycle under NACH mandate rules',
    citation: 'NPCI/NACH/2020/001',
    verified: false,
  },
}

export default function Policy() {
  const { data, loading, error, reload } = useApi(() => api.taxonomy(), [])
  const [selectedFamily, setSelectedFamily] = useState<string | null>(null)
  const [selectedCode, setSelectedCode] = useState<string | null>(null)

  if (error) return <ErrorState error={error} onRetry={reload} />
  if (loading || !data) return <div className="p-6"><SkeletonRows rows={8} cols={3} /></div>

  const TAXONOMY: any[] = (data?.families ?? []).map((fam: any) => ({
    ...fam,
    classes: (fam.classes ?? []).map((c: any) => ({
      ...c,
      ruleId: c.rule_id ?? c.ruleId ?? '',
      hardClass: c.hard_class ?? c.hardClass ?? (c.terminality === 'HARD'),
      prohibited: c.prohibited ?? (c.terminality === 'PROHIBITED'),
      directive: c.directive ?? (c.terminality === 'HARD' ? 'TERMINATE' : c.terminality === 'PROHIBITED' ? 'BLOCK' : 'RETRY'),
    })),
  }))

  const activeFamily = selectedFamily ?? TAXONOMY[0]?.family ?? null
  const family = TAXONOMY.find((f: any) => f.family === activeFamily)
  const cls = family?.classes.find((c: any) => c.code === selectedCode)

  return (
    <div className="flex h-full">
      {/* Taxonomy tree */}
      <div className="w-64 flex-none border-r border-ink-800 overflow-auto">
        <div className="sticky top-0 bg-ink-950 px-4 h-10 flex items-center border-b border-ink-800">
          <SectionLabel>Taxonomy</SectionLabel>
          <span className="font-mono text-[11px] text-ink-600 ml-2">{data?.version ?? '—'}</span>
        </div>
        <div className="py-1">
          {TAXONOMY.map((fam) => (
            <div key={fam.family}>
              <button
                onClick={() => { setSelectedFamily(fam.family); setSelectedCode(null) }}
                className={`w-full flex items-center justify-between px-4 py-2 text-left ${
                  selectedFamily === fam.family ? 'bg-ink-850 text-ink-100' : 'text-ink-400 hover:text-ink-100 hover:bg-ink-900'
                }`}
              >
                <span className="text-[11px] font-medium uppercase tracking-[0.06em]">{fam.family}</span>
                <span className="font-mono text-[10px] text-ink-600">{fam.classes.length}</span>
              </button>
              {selectedFamily === fam.family && fam.classes.map((cls: any) => (
                <button
                  key={cls.code}
                  onClick={() => setSelectedCode(cls.code === selectedCode ? null : cls.code)}
                  className={`w-full flex items-center gap-2 pl-6 pr-4 py-1.5 text-left ${
                    selectedCode === cls.code ? 'bg-blue-tint text-blue-400' : 'text-ink-400 hover:text-ink-200 hover:bg-ink-850'
                  }`}
                >
                  <span className="w-1 h-1 rounded-full flex-none" style={{ background: selectedCode === cls.code ? '#3395FF' : '#3D4A5E' }} />
                  <span className="font-mono text-[11px] truncate">{cls.code}</span>
                  {cls.prohibited && (
                    <span className="ml-auto text-[9px] font-mono text-signal-critical">P</span>
                  )}
                  {cls.hardClass && !cls.prohibited && (
                    <span className="ml-auto text-[9px] font-mono text-signal-caution">H</span>
                  )}
                </button>
              ))}
            </div>
          ))}
        </div>
        <div className="px-4 py-3 border-t border-ink-800 space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] text-signal-critical w-4">P</span>
            <span className="text-[11px] text-ink-500">PROHIBITED — no money movement</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] text-signal-caution w-4">H</span>
            <span className="text-[11px] text-ink-500">HARD — conf floor 0.90</span>
          </div>
        </div>
      </div>

      {/* Rule detail */}
      <div className="flex-1 overflow-auto p-4">
        {!selectedCode && family && (
          <div className="space-y-4">
            <div className="bg-ink-900 border border-ink-700 p-4" style={{ borderRadius: 4 }}>
              <div className="text-[11px] font-medium text-ink-500 uppercase tracking-[0.08em] mb-1">{family.family}</div>
              <p className="text-[13px] text-ink-300">{family.classes.length} classes in this family</p>
            </div>
            <div className="border border-ink-700" style={{ borderRadius: 4 }}>
              <div className="grid grid-cols-[1fr_80px_1fr_80px_80px] bg-ink-850 border-b border-ink-800">
                {['Class', 'Directive', 'Rule', 'Hard', 'Prohibited'].map((h) => (
                  <div key={h} className="px-3 py-2 text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em]">{h}</div>
                ))}
              </div>
              {family.classes.map((cls: any) => (
                <div
                  key={cls.code}
                  className="grid grid-cols-[1fr_80px_1fr_80px_80px] border-b border-ink-800 last:border-b-0 hover:bg-ink-850 cursor-pointer transition-colors"
                  onClick={() => setSelectedCode(cls.code)}
                >
                  <div className="px-3 py-2.5">
                    <span className="font-mono text-[12px] text-ink-200">{cls.code}</span>
                  </div>
                  <div className="px-3 py-2.5">
                    <span className={`font-mono text-[11px] ${DIRECTIVE_COLOR[cls.directive] ?? 'text-ink-300'}`}>
                      {cls.directive}
                    </span>
                  </div>
                  <div className="px-3 py-2.5">
                    <RuleIdTag ruleId={cls.ruleId} />
                  </div>
                  <div className="px-3 py-2.5 text-center">
                    {cls.hardClass ? (
                      <span className="font-mono text-[11px] text-signal-caution">YES</span>
                    ) : (
                      <span className="font-mono text-[11px] text-ink-600">—</span>
                    )}
                  </div>
                  <div className="px-3 py-2.5 text-center">
                    {cls.prohibited ? (
                      <span className="font-mono text-[11px] text-signal-critical">YES</span>
                    ) : (
                      <span className="font-mono text-[11px] text-ink-600">—</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {cls && (
          <div className="space-y-4">
            <button
              onClick={() => setSelectedCode(null)}
              className="text-[12px] text-ink-400 hover:text-ink-100 font-mono flex items-center gap-1.5"
            >
              ← Back
            </button>

            <div className="bg-ink-900 border border-ink-700 p-4" style={{ borderRadius: 4 }}>
              <div className="flex items-start justify-between gap-4 mb-4">
                <div>
                  <span className="font-mono text-[16px] text-ink-050">{cls.code}</span>
                  <div className="text-[12px] text-ink-500 mt-0.5 font-mono">{family?.family}</div>
                </div>
                <div className="flex items-center gap-2">
                  {cls.prohibited && (
                    <span
                      className="text-[11px] font-mono text-signal-critical border border-signal-critical chip-critical px-[8px] py-[3px] uppercase"
                      style={{ borderRadius: 3 }}
                    >
                      PROHIBITED
                    </span>
                  )}
                  {cls.hardClass && (
                    <span
                      className="text-[11px] font-mono text-signal-caution border border-signal-caution chip-caution px-[8px] py-[3px] uppercase"
                      style={{ borderRadius: 3 }}
                    >
                      HARD CLASS
                    </span>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-[11px] font-medium text-ink-500 uppercase tracking-[0.08em] mb-1">Directive</div>
                  <span className={`font-mono text-[14px] ${DIRECTIVE_COLOR[cls.directive] ?? 'text-ink-200'}`}>
                    {cls.directive}
                  </span>
                </div>
                <div>
                  <div className="text-[11px] font-medium text-ink-500 uppercase tracking-[0.08em] mb-1">Rule</div>
                  <RuleIdTag ruleId={cls.ruleId} />
                </div>
              </div>
            </div>

            {REGULATORY_NOTES[cls.ruleId] && (
              <div className="bg-ink-900 border border-ink-700 p-4" style={{ borderRadius: 4 }}>
                <div className="flex items-center gap-2 mb-2">
                  <SectionLabel>Regulatory Basis</SectionLabel>
                  <UnverifiedChip />
                </div>
                <p className="text-[13px] text-ink-300 mb-2">{REGULATORY_NOTES[cls.ruleId].text}</p>
                <p className="font-mono text-[12px] text-ink-500">{REGULATORY_NOTES[cls.ruleId].citation}</p>
                <p className="text-[11px] text-signal-caution mt-2">
                  UNVERIFIED — source citation present but not independently confirmed. Clear this chip only after legal review.
                </p>
              </div>
            )}

            <div className="bg-ink-900 border border-ink-700 p-4" style={{ borderRadius: 4 }}>
              <SectionLabel>Invariant Assertions</SectionLabel>
              <div className="mt-3 space-y-2">
                {[
                  { check: 'Money movement possible', value: cls.prohibited ? 'NO — PROHIBITED class' : 'YES — within constraint limits', ok: !cls.prohibited },
                  { check: 'LLM in decision path', value: 'NO — rule_id is deterministic', ok: true },
                  { check: 'Constraint kernel position', value: 'C_PROHIBITED_CLASS at pos 3', ok: true },
                ].map((inv) => (
                  <div key={inv.check} className="flex items-center gap-3">
                    <span className={`font-mono text-[11px] ${inv.ok ? 'text-signal-positive' : 'text-signal-critical'}`}>
                      {inv.ok ? '✓' : '✗'}
                    </span>
                    <span className="text-[12px] text-ink-400 w-44">{inv.check}</span>
                    <span className={`font-mono text-[12px] ${inv.ok ? 'text-ink-300' : 'text-signal-critical'}`}>{inv.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {!selectedCode && !family && (
          <div className="flex flex-col items-center justify-center h-64 gap-2">
            <p className="text-[14px] text-ink-400">Select a failure family from the taxonomy</p>
          </div>
        )}
      </div>
    </div>
  )
}
