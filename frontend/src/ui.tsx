import { useState } from 'react'

// ─── StateChip ────────────────────────────────────────────────────────────────

type ChipVariant = 'positive' | 'caution' | 'critical' | 'ambiguous' | 'neutral' | 'blue'

const STATUS_VARIANT: Record<string, ChipVariant> = {
  RECOVERED: 'positive',
  DUPLICATE_CHARGE_PREVENTED: 'positive',
  ALLOW: 'positive',
  CHAIN_OK: 'positive',
  DENY: 'critical',
  TERMINATED: 'critical',
  COMPLIANCE_VIOLATION: 'critical',
  UNVERIFIED: 'caution',
  HOLD: 'caution',
  SCHEDULED: 'caution',
  NEEDS_HUMAN: 'caution',
  AMBIGUOUS: 'ambiguous',
  RECON_PENDING: 'ambiguous',
  IN_FLIGHT: 'ambiguous',
  EXHAUSTED: 'neutral',
  SKIPPED: 'neutral',
  NEEDS_HUMAN_QUEUE: 'caution',
  ARM_DUNNFLOW: 'blue',
  ARM_CONTROL: 'neutral',
}

const CHIP_COLORS: Record<ChipVariant, { text: string; border: string; bg: string }> = {
  positive:  { text: 'text-signal-positive', border: 'border-signal-positive', bg: 'chip-positive' },
  caution:   { text: 'text-signal-caution',  border: 'border-signal-caution',  bg: 'chip-caution'  },
  critical:  { text: 'text-signal-critical', border: 'border-signal-critical', bg: 'chip-critical' },
  ambiguous: { text: 'text-signal-ambiguous',border: 'border-signal-ambiguous',bg: 'chip-ambiguous'},
  neutral:   { text: 'text-signal-neutral',  border: 'border-signal-neutral',  bg: 'chip-neutral'  },
  blue:      { text: 'text-blue-500',        border: 'border-blue-500',        bg: 'chip-blue'     },
}

export function StateChip({ status, small }: { status: string; small?: boolean }) {
  const variant = STATUS_VARIANT[status] ?? 'neutral'
  const { text, border, bg } = CHIP_COLORS[variant]
  return (
    <span
      className={`inline-flex items-center border ${border} ${text} ${bg} font-mono ${small ? 'text-[10px] px-[6px] py-[2px]' : 'text-[11px] px-[8px] py-[3px]'}`}
      style={{ borderRadius: 3, letterSpacing: '0.04em' }}
    >
      {status}
    </span>
  )
}

// ─── RuleIdTag ────────────────────────────────────────────────────────────────

export function RuleIdTag({ ruleId }: { ruleId: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = () => {
    navigator.clipboard.writeText(ruleId).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 900)
  }
  return (
    <button
      onClick={handleCopy}
      className="font-mono text-[12px] text-ink-200 bg-ink-850 px-[8px] py-[3px] cursor-copy hover:text-ink-050 hover:bg-ink-800 transition-colors"
      style={{ borderRadius: 3 }}
      title="Click to copy"
    >
      {copied ? 'Copied' : ruleId}
    </button>
  )
}

// ─── ClassifierTierChip ───────────────────────────────────────────────────────

const TIER_COLORS: Record<string, { text: string; bar: string }> = {
  T1: { text: 'text-signal-positive', bar: '#2FA97C' },
  T2: { text: 'text-blue-500',        bar: '#3395FF' },
  T3: { text: 'text-signal-caution',  bar: '#D89B2C' },
  T4: { text: 'text-signal-neutral',  bar: '#5C6B82' },
}

export function ClassifierTierChip({ tier, conf }: { tier: string; conf: number }) {
  const { text, bar } = TIER_COLORS[tier] ?? TIER_COLORS.T4
  return (
    <div className="flex flex-col gap-[3px]">
      <span className={`font-mono text-[11px] ${text}`}>{tier}</span>
      <div className="w-8 h-[2px] bg-ink-700" style={{ borderRadius: 1 }}>
        <div className="h-full" style={{ width: `${conf * 100}%`, background: bar, borderRadius: 1 }} />
      </div>
    </div>
  )
}

// ─── MetricTile ───────────────────────────────────────────────────────────────

export function MetricTile({
  label, value, sub, highlight, large, accent,
}: {
  label: string
  value: string | number
  sub?: string
  highlight?: 'positive' | 'critical' | 'caution' | 'ambiguous' | 'default'
  large?: boolean
  accent?: boolean
}) {
  const valueColor = {
    positive:  'text-signal-positive',
    critical:  'text-signal-critical',
    caution:   'text-signal-caution',
    ambiguous: 'text-signal-ambiguous',
    default:   'text-ink-050',
  }[highlight ?? 'default']

  return (
    <div
      className={`bg-ink-900 border border-ink-700 p-4 flex flex-col gap-2 ${accent ? 'border-l-2 border-l-blue-500' : ''}`}
      style={{ borderRadius: 4 }}
    >
      <span className="text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em]">{label}</span>
      <span
        className={`font-sans font-semibold tabular ${valueColor} ${large ? 'text-[28px] leading-[32px]' : 'text-[22px] leading-[28px]'}`}
        style={{ letterSpacing: '-0.02em' }}
      >
        {value}
      </span>
      {sub && <span className="text-[12px] text-ink-400">{sub}</span>}
    </div>
  )
}

// ─── ComplianceBadge ──────────────────────────────────────────────────────────

export function ComplianceBadge({ violations }: { violations: number }) {
  const ok = violations === 0
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-[11px] font-mono px-[10px] py-[5px] border uppercase tracking-[0.04em] ${
        ok
          ? 'text-signal-positive border-signal-positive chip-positive'
          : 'text-signal-critical border-signal-critical chip-critical'
      }`}
      style={{ borderRadius: 3 }}
    >
      {ok ? `0 VIOLATIONS` : `${violations} VIOLATION${violations > 1 ? 'S' : ''}`}
    </span>
  )
}

// ─── Panel ────────────────────────────────────────────────────────────────────

export function Panel({
  title, children, action, flush, accent, critical, count,
}: {
  title?: string
  children: React.ReactNode
  action?: React.ReactNode
  flush?: boolean
  accent?: boolean
  critical?: boolean
  count?: number | string
}) {
  return (
    <div
      className={`bg-ink-900 border border-ink-700 flex flex-col ${
        accent ? 'border-l-2 border-l-blue-500' : ''
      } ${critical ? 'border-l-2 border-l-signal-critical' : ''}`}
      style={{ borderRadius: 4 }}
    >
      {title && (
        <div className="flex items-center justify-between px-4 h-10 border-b border-ink-800">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em]">{title}</span>
            {count !== undefined && (
              <span className="text-[11px] text-ink-500 font-mono">{count}</span>
            )}
          </div>
          {action && <div>{action}</div>}
        </div>
      )}
      <div className={flush ? '' : 'p-4'}>{children}</div>
    </div>
  )
}

// ─── MiniSparkline ────────────────────────────────────────────────────────────

export function MiniSparkline({ data, color = '#3395FF', width = 80, height = 28 }: {
  data: number[]
  color?: string
  width?: number
  height?: number
}) {
  if (data.length < 2) return null
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width
    const y = height - 2 - ((v - min) / range) * (height - 4)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  return (
    <svg width={width} height={height}>
      <polyline points={pts.join(' ')} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// ─── DualArmChart (line chart) ────────────────────────────────────────────────

export function DualArmChart({ labels, dunnflow, control, height = 160 }: {
  labels?: string[]
  dunnflow?: number[]
  control?: number[]
  height?: number
}) {
  const lbls = labels && labels.length > 0 ? labels : ['0', '100', '200', '300', '400']
  const dVals = dunnflow && dunnflow.length > 0 ? dunnflow : [0]
  const cVals = control && control.length > 0 ? control : [0]

  const W = 600
  const H = height
  const PADL = 48
  const PADB = 28
  const PADT = 12
  const PADR = 16
  const chartW = W - PADL - PADR
  const chartH = H - PADB - PADT

  const allVals = [...dVals, ...cVals]
  const minV = 0
  const maxV = Math.max(...allVals, 1)

  const toX = (i: number) => PADL + (lbls.length > 1 ? (i / (lbls.length - 1)) * chartW : 0)
  const toY = (v: number) => PADT + chartH - ((v - minV) / (maxV - minV)) * chartH

  const dPts = dVals.map((v, i) => `${toX(i).toFixed(1)},${toY(v).toFixed(1)}`).join(' ')
  const cPts = cVals.map((v, i) => `${toX(i).toFixed(1)},${toY(v).toFixed(1)}`).join(' ')

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(f * maxV))

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} className="overflow-visible">
      {/* Grid lines */}
      {gridLines.map((v) => (
        <g key={v}>
          <line
            x1={PADL} x2={W - PADR}
            y1={toY(v)} y2={toY(v)}
            stroke="#151A24" strokeWidth="1"
          />
          <text x={PADL - 6} y={toY(v) + 4} textAnchor="end" fill="#5C6B82" fontSize="10" fontFamily="'JetBrains Mono', monospace">
            {v}
          </text>
        </g>
      ))}

      {/* X axis labels */}
      {lbls.map((l, i) => (
        <text key={i} x={toX(i)} y={H - 4} textAnchor="middle" fill="#5C6B82" fontSize="10" fontFamily="'JetBrains Mono', monospace">
          {l}
        </text>
      ))}

      {/* Control arm line */}
      <polyline points={cPts} fill="none" stroke="#5C6B82" strokeWidth="1.5" strokeLinejoin="round" />

      {/* Dunnflow arm line */}
      <polyline points={dPts} fill="none" stroke="#3395FF" strokeWidth="1.5" strokeLinejoin="round" />

      {/* End labels */}
      <text x={toX(dVals.length - 1) + 6} y={toY(dVals[dVals.length - 1]) + 4} fill="#3395FF" fontSize="10" fontFamily="'JetBrains Mono', monospace">
        DUNNFLOW
      </text>
      <text x={toX(cVals.length - 1) + 6} y={toY(cVals[cVals.length - 1]) + 4} fill="#5C6B82" fontSize="10" fontFamily="'JetBrains Mono', monospace">
        CONTROL
      </text>
    </svg>
  )
}

// ─── ClassifierTierBar ────────────────────────────────────────────────────────

export function ClassifierTierBar({ tiers }: { tiers?: Record<string, number> | null }) {
  const t = tiers ?? {}
  const t1 = t.T1 ?? 0
  const t2 = t.T2 ?? 0
  const t3 = t.T3 ?? 0
  const t4 = t.T4 ?? 0
  const total = t1 + t2 + t3 + t4 || 1
  const pcts = {
    T1: (t1 / total) * 100,
    T2: (t2 / total) * 100,
    T3: (t3 / total) * 100,
    T4: (t4 / total) * 100,
  }
  const colors = { T1: '#2FA97C', T2: '#3395FF', T3: '#D89B2C', T4: '#5C6B82' }
  return (
    <div className="flex flex-col gap-2">
      <div className="flex h-2 w-full overflow-hidden" style={{ borderRadius: 1 }}>
        {(['T1', 'T2', 'T3', 'T4'] as const).map((tk) => (
          <div key={tk} style={{ width: `${pcts[tk]}%`, background: colors[tk] }} />
        ))}
      </div>
      <div className="flex gap-4">
        {(['T1', 'T2', 'T3', 'T4'] as const).map((tk) => (
          <div key={tk} className="flex items-center gap-1.5">
            <div className="w-2 h-2" style={{ background: colors[tk], borderRadius: 1 }} />
            <span className="font-mono text-[11px] text-ink-300">{tk} {pcts[tk].toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── SkeletonRow ──────────────────────────────────────────────────────────────

export function SkeletonRows({ count = 5, cols = 6 }: { count?: number; cols?: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <tr key={i} className="border-b border-ink-800">
          {Array.from({ length: cols }).map((_, j) => (
            <td key={j} className="px-3 py-2.5">
              <div
                className="skeleton bg-ink-850 rounded"
                style={{ height: 12, width: `${[40, 60, 80, 55, 45, 70][j % 6]}%` }}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}

// ─── SectionLabel ─────────────────────────────────────────────────────────────

export function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em]">
      {children}
    </span>
  )
}

// ─── UnverifiedChip ───────────────────────────────────────────────────────────

export function UnverifiedChip() {
  return (
    <span
      className="inline-flex items-center text-[10px] font-mono text-signal-caution border border-signal-caution chip-caution px-[6px] py-[2px] uppercase tracking-[0.04em]"
      style={{ borderRadius: 3 }}
      title="Regulatory constant not independently verified — source citation required"
    >
      UNVERIFIED
    </span>
  )
}

// ─── ChainStatus ──────────────────────────────────────────────────────────────

export function ChainStatus({ ok, seqHead = 0 }: { ok: boolean; seqHead?: number | null }) {
  const head = Number(seqHead ?? 0)
  return (
    <div className={`flex items-center gap-1.5 font-mono text-[11px] ${ok ? 'text-signal-positive' : 'text-signal-critical'}`}>
      <div className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-signal-positive' : 'bg-signal-critical'}`} />
      {ok ? `CHAIN OK · seq ${Number.isFinite(head) ? head.toLocaleString('en-IN') : '0'}` : `CHAIN BROKEN · seq ${Number.isFinite(head) ? head.toLocaleString('en-IN') : '0'}`}
    </div>
  )
}

// ─── TestModeBadge ────────────────────────────────────────────────────────────

export function TestModeBadge() {
  return (
    <span
      className="inline-flex items-center text-[11px] font-mono text-signal-caution border border-signal-caution chip-caution px-[8px] py-[3px] uppercase tracking-[0.04em]"
      style={{ borderRadius: 3 }}
    >
      TEST MODE
    </span>
  )
}

// ─── Button ───────────────────────────────────────────────────────────────────

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type ButtonSize = 'sm' | 'md' | 'lg'

const BTN_BASE = 'inline-flex items-center justify-center gap-2 font-sans font-medium cursor-pointer border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-ink-950 disabled:cursor-not-allowed disabled:opacity-60'

const BTN_VARIANT: Record<ButtonVariant, string> = {
  primary:   'bg-blue-500 text-white border-blue-500 hover:bg-blue-600 hover:border-blue-600',
  secondary: 'bg-transparent text-ink-100 border-ink-600 hover:bg-ink-850',
  ghost:     'bg-transparent text-ink-300 border-transparent hover:bg-ink-850 hover:text-ink-100',
  danger:    'bg-transparent text-signal-critical border-signal-critical hover:bg-[rgba(229,72,77,0.12)]',
}

const BTN_SIZE: Record<ButtonSize, string> = {
  sm: 'h-7 px-[10px] text-[11px]',
  md: 'h-8 px-3 text-[13px]',
  lg: 'h-10 px-4 text-[14px]',
}

export function Button({
  children, variant = 'secondary', size = 'md', onClick, disabled, loading, type = 'button',
}: {
  children: React.ReactNode
  variant?: ButtonVariant
  size?: ButtonSize
  onClick?: () => void
  disabled?: boolean
  loading?: boolean
  type?: 'button' | 'submit'
}) {
  return (
    <button
      type={type}
      className={`${BTN_BASE} ${BTN_VARIANT[variant]} ${BTN_SIZE[size]}`}
      style={{ borderRadius: 3 }}
      onClick={onClick}
      disabled={disabled || loading}
    >
      {loading ? (
        <span className="flex items-center gap-2">
          <span className="w-16 h-0.5 bg-white/30 rounded-full overflow-hidden">
            <span className="block h-full bg-white animate-pulse" style={{ width: '60%' }} />
          </span>
        </span>
      ) : children}
    </button>
  )
}

// ─── HashDisplay ──────────────────────────────────────────────────────────────

export function HashDisplay({ hash }: { hash: string }) {
  return (
    <span className="font-mono text-[11px] text-ink-400">{hash}</span>
  )
}
