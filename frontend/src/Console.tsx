import { useEffect, useState, type ReactElement } from 'react'
import { api } from './lib/api'
import { useApi, useAction } from './lib/hooks'
import { ChainStatus, TestModeBadge } from './ui'
import Analyze from './Analyze'
import Cases from './Cases'
import Evidence from './Evidence'

export type Route = 'analyze' | 'cases' | 'evidence'

const NAV_ITEMS: { id: Route; label: string; icon: (p: { active: boolean }) => ReactElement }[] = [
  { id: 'analyze', label: 'Analyze', icon: AnalyzeIcon },
  { id: 'cases', label: 'Cases', icon: CasesIcon },
  { id: 'evidence', label: 'Evidence', icon: EvidenceIcon },
]

const ROUTE_TITLE: Record<Route, string> = {
  analyze: 'Analyze',
  cases: 'Cases',
  evidence: 'Evidence',
}

// ─── SVG Icons (14px, minimal) ────────────────────────────────────────────────

function AnalyzeIcon({ active }: { active: boolean }) {
  const c = active ? '#3395FF' : '#8695AB'
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M3 4.5H11M3 7H9M3 9.5H10" stroke={c} strokeWidth="1.2" strokeLinecap="round" />
      <rect x="2" y="2" width="10" height="10" rx="1.5" stroke={c} strokeWidth="1.2" />
    </svg>
  )
}

function CasesIcon({ active }: { active: boolean }) {
  const c = active ? '#3395FF' : '#8695AB'
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <rect x="1" y="2" width="12" height="10" rx="1" stroke={c} strokeWidth="1.2" />
      <line x1="1" y1="5" x2="13" y2="5" stroke={c} strokeWidth="1" />
      <line x1="4" y1="8" x2="10" y2="8" stroke={c} strokeWidth="1" />
    </svg>
  )
}

function EvidenceIcon({ active }: { active: boolean }) {
  const c = active ? '#3395FF' : '#8695AB'
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M7 1 L7 4 M7 10 L7 13" stroke={c} strokeWidth="1.2" />
      <path d="M1 7 L4 7 M10 7 L13 7" stroke={c} strokeWidth="1.2" />
      <circle cx="7" cy="7" r="2.5" stroke={c} strokeWidth="1.2" />
    </svg>
  )
}

// ─── Console shell ────────────────────────────────────────────────────────────

interface ConsoleProps {
  route: Route
  caseRef: string | null
  onExit: () => void
  onNavigate: (r: Route, caseRef?: string) => void
}

export default function Console({ route, caseRef, onExit, onNavigate }: ConsoleProps) {
  const [collapsed, setCollapsed] = useState(false)
  const selectedCaseId = caseRef

  // live run context + chain status, server-computed
  const { data: sys } = useApi(() => api.systemStatus(), [])
  const { data: latest } = useApi(() => api.latestRun('ARM_DUNNFLOW').catch(() => null as any), [])
  // Overridable so a freshly launched run becomes "current" immediately,
  // instead of waiting for `latest` (which only reflects completed batch runs).
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  useEffect(() => {
    if (!activeRunId && latest?.id) setActiveRunId(latest.id)
  }, [latest, activeRunId])
  const { data: run } = useApi(
    () => (activeRunId ? api.getRun(activeRunId) : Promise.resolve(null as any)), [activeRunId])
  const killSwitchAction = useAction(api.killSwitch)
  const [killArmed, setKillArmed] = useState<boolean | null>(null)
  const killSwitchOn = killArmed ?? sys?.kill_switch ?? false

  const navigate = (r: Route, caseId?: string) => onNavigate(r, caseId)

  const toggleKillSwitch = async () => {
    const next = !killSwitchOn
    const res = await killSwitchAction.run(next)
    if (res) setKillArmed(res.kill_switch)
  }

  return (
    <div className="h-full flex bg-ink-950 overflow-hidden">
      {/* Sidebar */}
      <aside
        className="flex-none flex flex-col border-r border-ink-800 bg-ink-950 overflow-hidden"
        style={{ width: collapsed ? 56 : 220, transition: 'width 180ms cubic-bezier(0.2,0,0,1)' }}
      >
        {/* Wordmark */}
        <div className="h-12 flex items-center border-b border-ink-800 flex-none">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="w-14 h-full flex items-center justify-center text-ink-500 hover:text-ink-200 flex-none"
            style={{ transition: 'color 120ms' }}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <line x1="2" y1="4" x2="14" y2="4" stroke="currentColor" strokeWidth="1.2" />
              <line x1="2" y1="8" x2="14" y2="8" stroke="currentColor" strokeWidth="1.2" />
              <line x1="2" y1="12" x2="14" y2="12" stroke="currentColor" strokeWidth="1.2" />
            </svg>
          </button>
          {!collapsed && (
            <span className="font-mono text-[14px] font-medium text-ink-050 tracking-tight">dunnflow</span>
          )}
        </div>

        {/* Nav */}
        <div className="flex-1 overflow-y-auto py-2">
          {!collapsed && (
            <div className="px-4 py-2 text-[10px] font-medium text-ink-600 uppercase tracking-[0.1em]">
              Recovery Console
            </div>
          )}
          {NAV_ITEMS.map((item) => {
            const active = route === item.id
            const Icon = item.icon
            return (
              <button
                key={item.id}
                onClick={() => navigate(item.id)}
                className={`w-full flex items-center gap-2 px-3 h-8 text-left ${
                  active
                    ? 'bg-ink-850 text-ink-050 border-l-2 border-l-blue-500'
                    : 'text-ink-300 hover:bg-ink-850 hover:text-ink-100 border-l-2 border-l-transparent'
                }`}
                style={{ fontSize: 13 }}
                title={collapsed ? item.label : undefined}
              >
                <span className="flex-none w-4 flex items-center justify-center">
                  <Icon active={active} />
                </span>
                {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
              </button>
            )
          })}
        </div>

        {/* Nav footer */}
        <div className="flex-none border-t border-ink-800 px-3 py-3 space-y-2">
          <ChainStatus ok={sys?.chain.ok ?? true} seqHead={sys?.chain.seq_head ?? 0} />
          {!collapsed && (
            <button
              onClick={onExit}
              className="w-full text-left text-[11px] text-ink-500 hover:text-ink-300 font-mono"
            >
              ← Landing
            </button>
          )}
        </div>
      </aside>

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="h-12 flex-none flex items-center justify-between px-6 border-b border-ink-800 bg-ink-950">
          {/* Breadcrumb */}
          <div className="flex items-center gap-2 min-w-0">
            <span className="font-mono text-[12px] text-ink-500">dunnflow</span>
            <span className="text-ink-700">/</span>
            <span className="font-mono text-[12px] text-ink-200">
              {ROUTE_TITLE[route]}
            </span>
            {selectedCaseId && route === 'cases' && (
              <>
                <span className="text-ink-700">/</span>
                <span className="font-mono text-[12px] text-ink-200">{selectedCaseId}</span>
              </>
            )}
          </div>

          {/* Right: run context + TEST MODE + kill switch */}
          <div className="flex items-center gap-4">
            <span className="font-mono text-[11px] text-ink-500 hidden lg:block">
              {run ? `SEED ${run.seed} · N ${run.n} · ${run.arm}` : 'NO RUN'}
            </span>
            <TestModeBadge />
            <button
              onClick={toggleKillSwitch}
              disabled={killSwitchAction.pending}
              className={`font-mono text-[11px] border px-[8px] py-[3px] hidden md:inline-flex items-center gap-1.5 transition-colors disabled:opacity-60 ${
                killSwitchOn
                  ? 'text-signal-critical border-signal-critical bg-signal-critical/10'
                  : 'text-ink-500 border-ink-700 hover:text-signal-critical hover:border-signal-critical'
              }`}
              style={{ borderRadius: 3 }}
              title="Kill switch — halts all money movement, enforced server-side in the constraint kernel"
            >
              <span className={`w-1.5 h-1.5 rounded-full ${killSwitchOn ? 'bg-signal-critical' : 'bg-signal-positive'}`} />
              KILL SWITCH {killSwitchOn ? 'ARMED' : 'OFF'}
            </button>
          </div>
        </header>

        {/* View outlet */}
        <main className="flex-1 overflow-auto">
          {route === 'analyze' && <Analyze />}
          {route === 'cases' && <Cases runId={run?.id ?? null} selectedId={selectedCaseId}
                                       onSelect={(id) => navigate('cases', id ?? undefined)}
                                       onRunLaunched={setActiveRunId} />}
          {route === 'evidence' && <Evidence runId={run?.id ?? null} onOpenCase={(r) => navigate('cases', r)} />}
        </main>
      </div>
    </div>
  )
}
