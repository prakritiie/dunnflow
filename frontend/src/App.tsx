import React, { Component, ErrorInfo, ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import Landing from './Landing'
import Console from './Console'

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error: Error | null }> {
  state = { hasError: false, error: null }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }
  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Render error:', error, errorInfo)
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-ink-950 text-ink-100 p-6">
          <div className="bg-ink-900 border border-signal-critical/40 p-6 max-w-lg w-full" style={{ borderRadius: 6 }}>
            <h2 className="text-[16px] font-semibold text-signal-critical mb-2">Display Error</h2>
            <p className="text-[13px] text-ink-300 mb-4">
              {(this.state.error as any)?.message ?? 'An unexpected error occurred while rendering the page.'}
            </p>
            <button
              onClick={() => { this.setState({ hasError: false, error: null }); window.location.href = '/console/cases' }}
              className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white font-mono text-[12px]"
              style={{ borderRadius: 3 }}
            >
              Reload Console
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

// Real URL routes. Browser back works, refresh preserves position, and the
// Refusal Ledger can deep-link straight to a case.
function LandingRoute() {
  const nav = useNavigate()
  return <Landing onEnter={() => nav('/console/cases')} />
}

function ConsoleRoute() {
  const nav = useNavigate()
  const { route, caseRef } = useParams()
  const activeRoute = (caseRef ? 'cases' : (route ?? 'cases')) as any
  return (
    <Console
      route={activeRoute}
      caseRef={caseRef ?? null}
      onExit={() => nav('/')}
      onNavigate={(r, ref) => nav(ref ? `/console/cases/${ref}` : `/console/${r}`)}
    />
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingRoute />} />
          <Route path="/console" element={<Navigate to="/console/cases" replace />} />
          <Route path="/console/cases/:caseRef" element={<ConsoleRoute />} />
          <Route path="/console/:route" element={<ConsoleRoute />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
