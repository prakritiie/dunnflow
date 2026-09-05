import { api } from './lib/api'
import { useApi } from './lib/hooks'
import { SkeletonRows, ErrorState, NoRun } from './lib/states'
import { fmtCurrency, fmtDuration, fmtPct } from './data'
import {
  ClassifierTierBar, DualArmChart, Panel, SectionLabel,
} from './ui'

// ─── Arm column ───────────────────────────────────────────────────────────────

function ArmColumn({ arm, isMain, attemptRatio }: { arm: any; isMain: boolean; attemptRatio: number | null }) {
  const color = isMain ? '#3395FF' : '#5C6B82'
  const name = arm?.arm ?? arm?.name ?? (isMain ? 'ARM_DUNNFLOW' : 'ARM_CONTROL')
  const isControl = name === 'ARM_CONTROL'
  const recoveryRate = arm?.recovery_rate ?? arm?.recoveryRate ?? (arm?.cases ? arm.recovered / arm.cases : 0)
  const amountRecoveredMinor = arm?.amount_recovered_minor ?? arm?.amountRecoveredMinor ?? 0
  const networkAttempts = arm?.network_attempts ?? arm?.networkAttempts ?? 0
  const duplicateCharges = arm?.duplicate_charges ?? arm?.duplicateCharges ?? 0
  const duplicateChargePrevented = arm?.duplicate_charge_prevented ?? 0
  const recovered = arm?.recovered ?? 0
  const cases = arm?.cases ?? 0
  const complianceViolations = arm?.compliance_violations ?? arm?.complianceViolations

  return (
    <div className="flex flex-col" style={{ borderTop: `2px solid ${color}` }}>
      {/* Arm header */}
      <div className="bg-ink-900 border border-ink-700 border-t-0 px-4 py-3 flex items-center justify-between">
        <span className="font-mono text-[12px]" style={{ color }}>{name}</span>
        {isMain ? (
          <span
            className="text-[10px] font-mono text-blue-500 border border-blue-500 chip-blue px-[6px] py-[1px] uppercase tracking-[0.04em]"
            style={{ borderRadius: 3 }}
          >
            ACTIVE
          </span>
        ) : (
          <span
            className="text-[10px] font-mono text-ink-500 border border-ink-600 px-[6px] py-[1px] uppercase tracking-[0.04em]"
            style={{ borderRadius: 3 }}
          >
            BASELINE
          </span>
        )}
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2">
        {/* Recovery Rate */}
        <div className="bg-ink-900 border-b border-r border-ink-700 p-4">
          <div className="text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em] mb-2">Recovery Rate</div>
          <div
            className="text-[24px] font-semibold tabular"
            style={{ letterSpacing: '-0.02em', color: isMain ? '#3395FF' : '#8695AB', fontVariantNumeric: 'tabular-nums' }}
          >
            {fmtPct(recoveryRate)}
          </div>
          <div className="text-[12px] text-ink-500 mt-1 tabular">{recovered} / {cases} cases</div>
        </div>

        {/* Recovered amount — always in highest-contrast neutral */}
        <div className="bg-ink-900 border-b border-ink-700 p-4">
          <div className="text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em] mb-2">Recovered</div>
          <div
            className="text-[22px] font-semibold tabular"
            style={{ letterSpacing: '-0.02em', color: '#F2F5F9', fontVariantNumeric: 'tabular-nums' }}
          >
            {fmtCurrency(amountRecoveredMinor)}
          </div>
          <div className="text-[12px] text-ink-500 mt-1">{cases} cases processed</div>
        </div>

        {/* Network Attempts */}
        <div className="bg-ink-900 border-b border-r border-ink-700 p-4">
          <div className="text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em] mb-2">Network Attempts</div>
          <div
            className="text-[22px] font-semibold tabular"
            style={{ letterSpacing: '-0.02em', color: '#F2F5F9', fontVariantNumeric: 'tabular-nums' }}
          >
            {networkAttempts.toLocaleString('en-IN')}
          </div>
          {isMain && attemptRatio !== null ? (
            <div className="text-[12px] text-signal-positive mt-1">{attemptRatio.toFixed(1)}× fewer than baseline</div>
          ) : (
            <div className="text-[12px] text-ink-500 mt-1">{isControl ? 'fixed 3-attempt budget, all classes' : ''}</div>
          )}
        </div>

        {/* Duplicate charges */}
        <div className="bg-ink-900 border-b border-ink-700 p-4">
          <div className="text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em] mb-2">Duplicate Charges</div>
          <div
            className={`text-[22px] font-semibold tabular ${
              duplicateCharges > 0 ? 'text-signal-critical' : 'text-signal-positive'
            }`}
            style={{ letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums' }}
          >
            {duplicateCharges}
          </div>
          <div className="text-[12px] text-ink-500 mt-1">
            {isControl
              ? 'blind retry — no reconciliation'
              : duplicateChargePrevented > 0
              ? `${duplicateChargePrevented} suppressed by reconciler`
              : 'no ambiguous outcomes this run'}
          </div>
        </div>
      </div>

      {/* Compliance row */}
      <div className="bg-ink-900 border border-ink-700 border-t-0 px-4 py-3 flex items-center justify-between">
        <span className="text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em]">Compliance layer</span>
        {isControl ? (
          <span
            className="font-mono text-[11px] text-ink-500 border border-ink-700 px-[8px] py-[3px] uppercase tracking-[0.04em]"
            style={{ borderRadius: 3 }}
          >
            N/A — no constraint layer
          </span>
        ) : (
          <span
            className="font-mono text-[11px] text-signal-positive border border-signal-positive chip-positive px-[8px] py-[3px] uppercase tracking-[0.04em]"
            style={{ borderRadius: 3 }}
          >
            {complianceViolations ?? 0} VIOLATIONS
          </span>
        )}
      </div>
    </div>
  )
}

// ─── Failure class chart ──────────────────────────────────────────────────────

function FailureClassBar({ classes }: { classes: any[] }) {
  const FAILURE_CLASSES = classes
  const max = Math.max(...FAILURE_CLASSES.map((f: any) => f.count), 1)
  return (
    <div className="space-y-2">
      {FAILURE_CLASSES.map((fc: any) => (
        <div key={fc.code} className="flex items-center gap-3">
          <span className="font-mono text-[11px] text-ink-400 w-44 truncate flex-none">{fc.code}</span>
          <div className="flex-1 h-1.5 bg-ink-800" style={{ borderRadius: 1 }}>
            <div
              className="h-full"
              style={{
                width: `${(fc.count / max) * 100}%`,
                background: fc.recoverable ? '#3395FF' : '#3D4A5E',
                borderRadius: 1,
              }}
            />
          </div>
          <span className="font-mono text-[11px] text-ink-500 w-6 text-right tabular" style={{ fontVariantNumeric: 'tabular-nums' }}>
            {fc.count}
          </span>
        </div>
      ))}
      <div className="flex items-center gap-4 pt-1">
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-1.5 bg-blue-500" style={{ borderRadius: 1 }} />
          <span className="text-[11px] text-ink-500">recoverable</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-1.5 bg-ink-600" style={{ borderRadius: 1 }} />
          <span className="text-[11px] text-ink-500">non-recoverable / terminated</span>
        </div>
      </div>
    </div>
  )
}

// ─── Restraint panel ──────────────────────────────────────────────────────────

function RestraintPanel() {
  return (
    <div className="bg-ink-900 border border-ink-700" style={{ borderRadius: 4 }}>
      <div className="px-4 h-10 flex items-center border-b border-ink-800">
        <SectionLabel>Where we did not use an LLM</SectionLabel>
      </div>
      <div className="p-4 space-y-3">
        {[
          { label: 'Retry timing',      how: 'Policy matrix — deterministic by failure class and attempt index' },
          { label: 'Money movement',    how: 'Rule engine — every action carries a rule_id, never a model rationale' },
          { label: 'Compliance checks', how: 'Constraint kernel — 12 ordered veto gates, no model in the chain' },
        ].map((row) => (
          <div key={row.label} className="flex items-start gap-3">
            <span className="font-mono text-[11px] text-signal-neutral flex-none mt-0.5">✗ LLM</span>
            <div>
              <span className="text-[12px] font-medium text-ink-200">{row.label}</span>
              <p className="text-[12px] text-ink-500 mt-0.5">{row.how}</p>
            </div>
          </div>
        ))}
        <div className="pt-2 border-t border-ink-800">
          <p className="text-[11px] text-ink-600">
            Invariant query: <span className="font-mono text-ink-500">SELECT count(*) FROM audit_log WHERE entry_type=&apos;DECISION&apos; AND model_id IS NOT NULL</span> must return 0.
          </p>
        </div>
      </div>
    </div>
  )
}

// ─── Benchmark tab (dual-arm comparison) ──────────────────────────────────────

export default function CommandCenter({ runId }: { runId: string | null }) {
  const { data: cmp, loading: l1, error: e1, reload } = useApi(
    () => (runId ? api.comparison(runId) : Promise.resolve(null as any)), [runId])
  const { data: ser } = useApi(() => (runId ? api.series(runId) : Promise.resolve(null as any)), [runId])
  const { data: dist } = useApi(() => (runId ? api.distribution(runId) : Promise.resolve([])), [runId])
  const { data: runData } = useApi(() => (runId ? api.getRun(runId) : Promise.resolve(null as any)), [runId])

  if (!runId) return <NoRun />
  if (e1) return <ErrorState error={e1} onRetry={reload} />
  if (l1 || !cmp || !cmp.dunnflow) return <div className="p-6"><SkeletonRows rows={8} /></div>

  const ARM_DUNNFLOW: any = cmp.dunnflow
  const ARM_CONTROL: any = cmp.control ?? { arm: 'ARM_CONTROL', recovery_rate: 0, amount_recovered_minor: 0, network_attempts: 0, duplicate_charges: 0, compliance_violations: null, cases: 0, recovered: 0 }
  const RUN: any = runData ?? {}
  const RECOVERY_SERIES: any = ser ?? { labels: [], dunnflow: [], control: [] }
  const FAILURE_CLASSES: any[] = dist ?? []
  const tiers = ARM_DUNNFLOW.tiers ?? {}
  const tierTotal = Object.values(tiers).reduce((a: number, b: any) => a + Number(b || 0), 0) || 1
  const noModelPct = ((Number(tiers.T1 || 0) + Number(tiers.T2 || 0)) / tierTotal) * 100
  const attemptRatio = cmp.control && ARM_CONTROL.network_attempts > 0
    ? ARM_CONTROL.network_attempts / Math.max(ARM_DUNNFLOW.network_attempts, 1)
    : null

  return (
    <div className="space-y-6">
      {/* Run context strip — no fabricated fallbacks; shows what is actually known */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-4 flex-wrap">
          {[
            { label: 'Run', value: RUN.id ? String(RUN.id).slice(0, 8) + '...' : '—' },
            { label: 'Policy', value: RUN.policy_version ?? '—' },
            { label: 'Taxonomy', value: RUN.taxonomy_version ?? '—' },
            { label: 'Duration', value: RUN.duration_seconds ? fmtDuration(RUN.duration_seconds) : '—' },
          ].map((item, i) => (
            <div key={i} className="flex items-center gap-4">
              {i > 0 && <div className="w-px h-8 bg-ink-800" />}
              <div>
                <div className="text-[11px] font-medium text-ink-500 uppercase tracking-[0.08em] mb-0.5">{item.label}</div>
                <span className="font-mono text-[13px] text-ink-200">{item.value}</span>
              </div>
            </div>
          ))}
        </div>
        <div
          className="font-mono text-[11px] text-signal-positive border border-signal-positive chip-positive px-[8px] py-[3px] uppercase tracking-[0.04em]"
          style={{ borderRadius: 3 }}
        >
          {RUN.status ?? 'UNKNOWN'}
        </div>
      </div>

      {/* Dual arm columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ArmColumn arm={ARM_DUNNFLOW} isMain={true} attemptRatio={attemptRatio} />
        <ArmColumn arm={ARM_CONTROL} isMain={false} attemptRatio={null} />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2">
          <Panel title="Recoveries over batch" flush>
            <div className="p-4">
              <div className="mb-3 flex items-center gap-4">
                <div className="flex items-center gap-1.5">
                  <div className="w-4 h-px bg-blue-500" />
                  <span className="font-mono text-[11px] text-ink-400">ARM_DUNNFLOW</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-4 h-px bg-ink-500" />
                  <span className="font-mono text-[11px] text-ink-400">ARM_CONTROL</span>
                </div>
              </div>
              <DualArmChart
                labels={RECOVERY_SERIES.labels}
                dunnflow={RECOVERY_SERIES.dunnflow}
                control={RECOVERY_SERIES.control}
                height={180}
              />
              <p className="mt-2 text-[11px] text-ink-500 text-right">cases processed →</p>
            </div>
          </Panel>
        </div>
        <div className="space-y-4">
          <Panel title="Classifier Tier Distribution">
            <ClassifierTierBar tiers={tiers} />
            <div className="mt-4 pt-3 border-t border-ink-800">
              <p className="text-[12px] text-ink-400">
                T1 + T2: <span className="text-ink-200 font-mono">{noModelPct.toFixed(0)}%</span> of cases resolved without an LLM call.
              </p>
            </div>
          </Panel>
          <Panel title="Failure Class Distribution">
            <FailureClassBar classes={FAILURE_CLASSES} />
          </Panel>
        </div>
      </div>

      <RestraintPanel />
    </div>
  )
}
