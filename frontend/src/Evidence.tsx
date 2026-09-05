import { useState } from 'react'
import Audit from './Audit'
import CommandCenter from './CommandCenter'
import RefusalLedger from './RefusalLedger'
import Policy from './Policy'

type Tab = 'audit' | 'benchmark' | 'refusals' | 'policy'

const TABS: { id: Tab; label: string }[] = [
  { id: 'audit', label: 'Audit Chain' },
  { id: 'benchmark', label: 'Benchmark' },
  { id: 'refusals', label: 'Refusals' },
  { id: 'policy', label: 'Policy' },
]

export default function Evidence({ runId, onOpenCase }: { runId: string | null; onOpenCase: (ref: string) => void }) {
  const [tab, setTab] = useState<Tab>('audit')

  return (
    <div className="h-full flex flex-col">
      <div className="flex-none flex items-center gap-1 px-4 h-11 border-b border-ink-800 bg-ink-950">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-3 h-8 text-[12px] font-medium border-b-2 -mb-px transition-colors ${
              tab === t.id
                ? 'text-ink-050 border-b-blue-500'
                : 'text-ink-400 border-b-transparent hover:text-ink-100'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-auto">
        {tab === 'audit' && <Audit runId={runId} />}
        {tab === 'benchmark' && <div className="p-6 max-w-[1600px] mx-auto"><CommandCenter runId={runId} /></div>}
        {tab === 'refusals' && <RefusalLedger runId={runId} onOpenCase={onOpenCase} />}
        {tab === 'policy' && <Policy />}
      </div>
    </div>
  )
}
