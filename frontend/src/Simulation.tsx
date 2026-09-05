import { api } from './lib/api'
import type { RunMetrics } from './lib/api'
import { useState, useEffect, useRef } from 'react'
import {fmtCurrency} from './data'
import { SectionLabel, ComplianceBadge, StateChip } from './ui'

type SimState = 'idle' | 'running' | 'complete'

export default function Simulation({ onRunReady }: { onRunReady?: (runId: string) => void }) {
  const [arm, setArm] = useState<'ARM_DUNNFLOW' | 'ARM_CONTROL'>('ARM_DUNNFLOW')
  const [seed, setSeed] = useState('42')
  const [n, setN] = useState('400')
  const [simState, setSimState] = useState<SimState>('idle')
  const [progress, setProgress] = useState(0)
  const [streamLines, setStreamLines] = useState<string[]>([])
  const [runId, setRunId] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [finalMetrics, setFinalMetrics] = useState<RunMetrics | null>(null)
  const streamRef = useRef<HTMLDivElement>(null)

  const total = parseInt(n, 10) || 400

  useEffect(() => {
    if (simState !== 'running' || !runId) return
    let stop = false
    const poll = async () => {
      while (!stop) {
        try {
          const r = await api.getRun(runId)
          if (r.status === 'COMPLETE' && r.metrics) {
            setProgress(total)
            setFinalMetrics(r.metrics)
            setStreamLines((p) => [...p,
              `[done] recovered ${r.metrics!.recovered}/${r.metrics!.cases}`,
              `[done] attempts=${r.metrics!.network_attempts} duplicates=${r.metrics!.duplicate_charges} violations=${r.metrics!.compliance_violations} deferred=${r.metrics!.deferred ?? 0}`,
            ])
            setSimState('complete')
            onRunReady?.(runId)
            return
          }
          if (r.status === 'FAILED') {
            setErr(r.error ?? 'Run failed'); setSimState('idle'); return
          }
          setProgress((p) => Math.min(p + Math.ceil(total / 20), total - 1))
        } catch { /* transient - keep polling */ }
        await new Promise((res) => setTimeout(res, 500))
      }
    }
    poll()
    return () => { stop = true }
  }, [simState, total, runId])

  

  const startSim = async () => {
    setErr(null); setProgress(0); setStreamLines([]); setFinalMetrics(null); setSimState('running')
    try {
      const r = await api.startRun(arm, parseInt(seed, 10) || 42, total)
      setRunId(r.run_id)
      setStreamLines((p) => [...p, `[run] queued ${r.run_id}`,
        `[run] seed=${seed} n=${total} arm=${arm}`])
    } catch (e: any) {
      setErr(e?.message ?? 'Could not start run')
      setSimState('idle')
    }
  }

  const reset = () => {
    setRunId(null); setErr(null)
    setSimState('idle')
    setProgress(0)
    setStreamLines([])
    setFinalMetrics(null)
  }

  const pct = total > 0 ? (progress / total) * 100 : 0

  return (
    <div className="p-6 max-w-[1000px] mx-auto space-y-6">
      <div>
        <SectionLabel>Simulation</SectionLabel>
        <p className="text-[13px] text-ink-400 mt-1">
          Launch a synthetic run. Both arms process the same seeded failure set for a fair comparison.
        </p>
      </div>

      {/* Config */}
      <div className="bg-ink-900 border border-ink-700" style={{ borderRadius: 4 }}>
        <div className="px-4 h-10 flex items-center border-b border-ink-800">
          <SectionLabel>Run Configuration</SectionLabel>
        </div>
        <div className="p-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em] mb-1.5">
                Arm
              </label>
              <select
                value={arm}
                onChange={(e) => setArm(e.target.value as typeof arm)}
                disabled={simState === 'running'}
                className="w-full h-8 px-3 bg-ink-950 border border-ink-600 text-[13px] text-ink-100 font-mono focus:border-blue-500 focus:outline-none disabled:opacity-60"
                style={{ borderRadius: 3 }}
              >
                <option value="ARM_DUNNFLOW">ARM_DUNNFLOW</option>
                <option value="ARM_CONTROL">ARM_CONTROL</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em] mb-1.5">
                Seed <span className="text-[10px] text-ink-600 normal-case tracking-normal">required</span>
              </label>
              <input
                type="text"
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
                disabled={simState === 'running'}
                className="w-full h-8 px-3 bg-ink-950 border border-ink-600 text-[13px] text-ink-100 font-mono focus:border-blue-500 focus:outline-none disabled:opacity-60"
                style={{ borderRadius: 3 }}
                placeholder="42"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-ink-400 uppercase tracking-[0.08em] mb-1.5">
                N (cases)
              </label>
              <input
                type="text"
                value={n}
                onChange={(e) => setN(e.target.value)}
                disabled={simState === 'running'}
                className="w-full h-8 px-3 bg-ink-950 border border-ink-600 text-[13px] text-ink-100 font-mono focus:border-blue-500 focus:outline-none disabled:opacity-60"
                style={{ borderRadius: 3 }}
                placeholder="400"
              />
            </div>
          </div>

          <div className="mt-4 flex items-center gap-3">
            {simState === 'idle' && (
              <button
                onClick={startSim}
                className="h-9 px-5 text-[13px] font-medium bg-blue-500 text-white border border-blue-500 hover:bg-blue-600 transition-colors flex items-center gap-2"
                style={{ borderRadius: 3 }}
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M3 2L10 6L3 10V2Z" fill="currentColor" />
                </svg>
                Launch Run
              </button>
            )}
            {simState === 'running' && (
              <button
                className="h-9 px-5 text-[13px] font-medium bg-transparent text-signal-critical border border-signal-critical hover:bg-signal-critical/10 transition-colors"
                style={{ borderRadius: 3 }}
                onClick={reset}
              >
                Abort
              </button>
            )}
            {simState === 'complete' && (
              <button
                onClick={reset}
                className="h-9 px-5 text-[13px] font-medium bg-transparent text-ink-200 border border-ink-600 hover:bg-ink-850 transition-colors"
                style={{ borderRadius: 3 }}
              >
                New Run
              </button>
            )}
            {simState !== 'idle' && (
              <div className="flex items-center gap-3 font-mono text-[12px] text-ink-400">
                <span>{progress} / {total}</span>
                <span>·</span>
                <span style={{ color: arm === 'ARM_DUNNFLOW' ? '#3395FF' : '#5C6B82' }}>{arm}</span>
                {simState === 'complete' && <StateChip status="RECOVERED" small />}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Progress */}
      {simState !== 'idle' && (
        <div className="bg-ink-900 border border-ink-700" style={{ borderRadius: 4 }}>
          <div className="px-4 h-10 flex items-center border-b border-ink-800 justify-between">
            <SectionLabel>Progress</SectionLabel>
            <span className="font-mono text-[12px] text-ink-400">{pct.toFixed(1)}%</span>
          </div>
          <div className="p-4 space-y-3">
            <div className="h-1 bg-ink-800 w-full" style={{ borderRadius: 1 }}>
              <div
                className="h-full transition-all"
                style={{
                  width: `${pct}%`,
                  background: arm === 'ARM_DUNNFLOW' ? '#3395FF' : '#5C6B82',
                  borderRadius: 1,
                  transition: 'width 180ms cubic-bezier(0.2,0,0,1)',
                }}
              />
            </div>
            {simState === 'complete' && finalMetrics && (
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                <div>
                  <div className="text-[11px] text-ink-500 uppercase tracking-[0.06em] mb-1">Recovered</div>
                  <div className="font-mono text-[18px] text-blue-500">{finalMetrics.recovered} / {finalMetrics.cases}</div>
                </div>
                <div>
                  <div className="text-[11px] text-ink-500 uppercase tracking-[0.06em] mb-1">Amount</div>
                  <div className="font-mono text-[18px] text-ink-050">{fmtCurrency(finalMetrics.amount_recovered_minor)}</div>
                </div>
                <div>
                  <div className="text-[11px] text-ink-500 uppercase tracking-[0.06em] mb-1">Violations</div>
                  <ComplianceBadge violations={finalMetrics.compliance_violations ?? 0} />
                </div>
                <div>
                  <div className="text-[11px] text-ink-500 uppercase tracking-[0.06em] mb-1">Duplicates</div>
                  <div className="font-mono text-[18px] text-signal-positive">{finalMetrics.duplicate_charges}</div>
                </div>
                <div>
                  <div className="text-[11px] text-ink-500 uppercase tracking-[0.06em] mb-1">Deferred</div>
                  <div className="font-mono text-[18px] text-signal-caution">{finalMetrics.deferred ?? 0}</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Stream */}
      {streamLines.length > 0 && (
        <div className="bg-ink-900 border border-ink-700" style={{ borderRadius: 4 }}>
          <div className="px-4 h-9 flex items-center border-b border-ink-800">
            <SectionLabel>Live Stream</SectionLabel>
          </div>
          <div
            ref={streamRef}
            className="p-4 overflow-y-auto space-y-0.5"
            style={{ maxHeight: 300, fontFamily: "'JetBrains Mono', monospace" }}
          >
            {streamLines.map((line, i) => {
              const isDcp = line.includes('DUPLICATE_CHARGE_PREVENTED')
              const isComplete = line.includes('run complete')
              const isError = line.includes('AMBIGUOUS') || line.includes('NEEDS_HUMAN')
              return (
                <div
                  key={i}
                  className={`text-[12px] leading-[20px] ${
                    isDcp || isComplete ? 'text-signal-positive' :
                    isError ? 'text-signal-caution' :
                    'text-ink-400'
                  }`}
                  style={{ animation: `fadeIn 120ms ease-out` }}
                >
                  {line}
                </div>
              )
            })}
            {simState === 'running' && (
              <div className="font-mono text-[12px] text-ink-300">
                <span className="cursor">█</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
