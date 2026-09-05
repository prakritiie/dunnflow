import { useEffect, useState } from 'react'

function useScrolled(threshold = 40) {
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > threshold)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [threshold])
  return scrolled
}

const GOALS = [
  {
    title: 'Detect revenue at risk',
    desc: 'Classifies why a payment failed — liquidity, instrument, behavioral, risk, transient, or ambiguous — instead of treating every failure the same.',
  },
  {
    title: 'Choose the right intervention',
    desc: 'A deterministic policy matrix picks one bounded action per failure class: retry, reconcile, request a new instrument, or stop permanently.',
  },
  {
    title: 'Execute within compliance limits',
    desc: '12 ordered constraints (attempt caps, velocity limits, amount ceilings, kill switch) can deny or delay an action — never create or upgrade one.',
  },
  {
    title: 'Measure recovery, not assumptions',
    desc: 'Every batch runs against a blind-retry baseline on the same seeded data, so recovered amount is a comparison, not a claim.',
  },
  {
    title: 'Guarantee against double charges',
    desc: 'A gateway timeout is never treated as a failure. Ambiguous outcomes are reconciled before anything retries.',
  },
  {
    title: 'Full audit trail',
    desc: 'Every state transition writes a hash-chained entry in the same transaction as the state change — verifiable on demand.',
  },
]

const CONSOLE_LINKS = [
  { title: 'Analyze', desc: 'Diagnose a case and preview the policy dry-run.' },
  { title: 'Cases', desc: 'The live batch, with inline approve/reject for escalations.' },
  { title: 'Evidence', desc: 'Audit chain, benchmark, refusals, and policy — one panel.' },
]

export default function Landing({ onEnter }: { onEnter: () => void }) {
  const scrolled = useScrolled()

  return (
    <div className="min-h-full bg-ink-950 text-ink-100 font-sans flex flex-col">
      {/* Navbar */}
      <nav
        className="sticky top-0 z-50"
        style={{
          background: scrolled ? 'rgba(5,7,13,0.97)' : 'transparent',
          borderBottom: scrolled ? '1px solid #151A24' : '1px solid transparent',
          transition: 'background 200ms, border-color 200ms',
        }}
      >
        <div className="max-w-[900px] mx-auto px-6 h-14 flex items-center justify-between">
          <span className="font-mono text-[15px] font-medium text-ink-050 tracking-tight">dunnflow</span>
          <button
            onClick={onEnter}
            className="h-8 px-4 text-[13px] font-medium bg-blue-500 text-white border border-blue-500 hover:bg-blue-600 transition-colors"
            style={{ borderRadius: 3 }}
          >
            Enter Console →
          </button>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-[900px] mx-auto px-6 pt-16 pb-14 w-full">
        <span
          className="text-[11px] font-mono text-ink-500 border border-ink-700 bg-ink-900 px-[8px] py-[4px] uppercase tracking-[0.08em] inline-block mb-5"
          style={{ borderRadius: 3 }}
        >
          dunnflow · AI Revenue Recovery
        </span>
        <h1
          className="text-[36px] leading-[44px] lg:text-[42px] lg:leading-[50px] font-semibold text-ink-050 mb-5"
          style={{ letterSpacing: '-0.03em' }}
        >
          Revenue slips away one failure at a time.{' '}
          <span className="text-ink-400">dunnflow wins it back — and proves it.</span>
        </h1>
        <p className="text-[15px] leading-[24px] text-ink-300 mb-8 max-w-[640px]">
          An agent that detects revenue at risk from failed payments, diagnoses why it failed,
          picks one bounded recovery action, checks it against compliance constraints, executes
          idempotently, and writes an audit entry for every step — then measures money recovered
          against a blind-retry baseline.
        </p>
        <button
          onClick={onEnter}
          className="h-10 px-6 text-[14px] font-medium bg-blue-500 text-white border border-blue-500 hover:bg-blue-600 transition-colors"
          style={{ borderRadius: 3 }}
        >
          Enter Console →
        </button>
        <p className="mt-4 font-mono text-[11px] text-ink-600 uppercase tracking-[0.08em]">
          Test Mode Only — no real money movement
        </p>
      </section>

      <div className="border-t border-ink-800" />

      {/* Key goals */}
      <section className="max-w-[900px] mx-auto px-6 py-14 w-full">
        <div className="font-mono text-[11px] text-ink-600 uppercase tracking-[0.1em] mb-6">What this builds toward</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {GOALS.map((g) => (
            <div key={g.title} className="bg-ink-900 border border-ink-700 p-4" style={{ borderRadius: 4 }}>
              <div className="text-[13px] font-medium text-ink-100 mb-1.5">{g.title}</div>
              <p className="text-[12px] text-ink-400 leading-[19px]">{g.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <div className="border-t border-ink-800" />

      {/* Console links */}
      <section className="max-w-[900px] mx-auto px-6 py-14 w-full">
        <div className="font-mono text-[11px] text-ink-600 uppercase tracking-[0.1em] mb-6">The console</div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {CONSOLE_LINKS.map((link) => (
            <button
              key={link.title}
              onClick={onEnter}
              className="text-left bg-ink-900 border border-ink-700 p-4 hover:bg-ink-850 hover:border-ink-600 transition-colors"
              style={{ borderRadius: 4 }}
            >
              <div className="text-[14px] font-medium text-ink-100 mb-1">{link.title}</div>
              <p className="text-[12px] text-ink-400 leading-[18px]">{link.desc}</p>
            </button>
          ))}
        </div>
      </section>

      <footer className="border-t border-ink-800 mt-auto">
        <div className="max-w-[900px] mx-auto px-6 py-6 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span className="font-mono text-[12px] text-ink-700">Test mode only — no real money movement.</span>
          <span className="font-mono text-[12px] text-ink-700">Built for the Razorpay AI Buildathon · Track 03</span>
        </div>
      </footer>
    </div>
  )
}
