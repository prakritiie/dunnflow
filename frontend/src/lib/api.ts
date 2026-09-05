// Typed fetch client. No dependency added: native fetch + EventSource only.
const BASE = (import.meta as any).env?.VITE_API_URL ?? 'http://127.0.0.1:8000'

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number, public detail?: unknown) {
    super(message)
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })
  } catch {
    throw new ApiError('NETWORK_ERROR', 'Cannot reach the dunnflow API. Is the backend running?', 0)
  }
  if (!res.ok) {
    let code = 'HTTP_ERROR', message = res.statusText, detail: unknown
    try {
      const b = await res.json()
      if (b?.error) { code = b.error.code; message = b.error.message; detail = b.error.detail }
    } catch { /* non-JSON error body */ }
    throw new ApiError(code, message, res.status, detail)
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T)
}

const get = <T>(p: string) => req<T>(p)
const post = <T>(p: string, body?: unknown) =>
  req<T>(p, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  health: () => get<Health>('/api/v1/health'),
  systemStatus: () => get<SystemStatus>('/api/v1/system/status'),
  killSwitch: (armed: boolean) => post<{ kill_switch: boolean }>('/api/v1/system/killswitch', { armed }),

  latestRun: (arm = 'ARM_DUNNFLOW') => get<Run>(`/api/v1/runs/latest?arm=${arm}`),
  listRuns: () => get<{ items: Run[] }>('/api/v1/runs?limit=20'),
  getRun: (id: string) => get<Run>(`/api/v1/runs/${id}`),
  startRun: (arm: string, seed: number, n: number) =>
    post<{ run_id: string; status: string }>('/api/v1/runs', { arm, seed, n }),
  comparison: (id: string) => get<Comparison>(`/api/v1/runs/${id}/comparison`),
  distribution: (id: string) => get<ClassCount[]>(`/api/v1/runs/${id}/distribution`),
  series: (id: string) => get<Series>(`/api/v1/runs/${id}/series`),
  tiers: (id: string) => get<Tiers>(`/api/v1/runs/${id}/tiers`),

  cases: (id: string, q: { status?: string; failure_class?: string; limit?: number; offset?: number } = {}) => {
    const s = new URLSearchParams()
    Object.entries(q).forEach(([k, v]) => v !== undefined && s.set(k, String(v)))
    return get<Paged<Case>>(`/api/v1/runs/${id}/cases?${s}`)
  },
  // case_ref repeats across runs, so every case lookup is run-scoped
  case: (ref: string, runId?: string) => get<Case>(`/api/v1/cases/${ref}${runId ? `?run_id=${runId}` : ''}`),
  timeline: (ref: string, runId?: string) => get<TimelineEvent[]>(`/api/v1/cases/${ref}/timeline${runId ? `?run_id=${runId}` : ''}`),
  constraints: (ref: string, runId?: string) => get<ConstraintRow[]>(`/api/v1/cases/${ref}/constraints${runId ? `?run_id=${runId}` : ''}`),
  attempts: (ref: string, runId?: string) => get<AttemptRow[]>(`/api/v1/cases/${ref}/attempts${runId ? `?run_id=${runId}` : ''}`),

  refusals: (id: string, q: { constraint_id?: string; rule_id?: string } = {}) => {
    const s = new URLSearchParams()
    Object.entries(q).forEach(([k, v]) => v && s.set(k, String(v)))
    return get<Refusal[]>(`/api/v1/runs/${id}/refusals?${s}`)
  },
  refusalSummary: (id: string) => get<RefusalSummary[]>(`/api/v1/runs/${id}/refusals/summary`),

  exceptions: (id: string) => get<ExceptionCase[]>(`/api/v1/runs/${id}/exceptions`),
  approve: (ref: string, confirmed_case_ref: string, actor = 'operator') =>
    post<Decision>(`/api/v1/exceptions/${ref}/approve`, { confirmed_case_ref, actor }),
  reject: (ref: string, reason: string, actor = 'operator') =>
    post<Decision>(`/api/v1/exceptions/${ref}/reject`, { reason, actor }),

  audit: (id: string, limit = 50) => get<Paged<AuditEntry>>(`/api/v1/runs/${id}/audit?limit=${limit}`),
  auditStatus: () => get<AuditStatus>('/api/v1/audit/status'),
  verifyChain: () => post<VerifyResult>('/api/v1/audit/verify'),

  faults: () => get<Fault[]>('/api/v1/chaos/faults'),
  armFault: (id: string) => post<FaultState>(`/api/v1/chaos/${id}/arm`),
  fireFault: (id: string) => post<FaultState>(`/api/v1/chaos/${id}/fire`),
  disarmFault: (id: string) => post<FaultState>(`/api/v1/chaos/${id}/disarm`),

  taxonomy: () => get<Taxonomy>('/api/v1/policy/taxonomy'),
  policyConstraints: () => get<{ version: string; constraints: ConstraintSpec[] }>('/api/v1/policy/constraints'),
  classifyCase: (body: CaseIntakeInput) => post<CaseIntakeResult>('/api/v1/cases/intake', body),

  streamUrl: (id: string) => `${BASE}/api/v1/runs/${id}/stream`,
}

// ── types (mirror the API contract) ──────────────────────────────────────────
export interface Health { status: string; postgres: boolean; redis: boolean }
export interface SystemStatus {
  kill_switch: boolean
  chain: { ok: boolean; seq_head: number; total_entries: number }
  env: string; test_mode: boolean
  policy_version: string; taxonomy_version: string; constraint_version: string
}
export interface Run {
  id: string; seed: number; arm: string; n: number; status: string
  policy_version: string; taxonomy_version: string; constraint_version: string
  metrics: RunMetrics | null; error: string | null
  started_at: string; completed_at: string | null; duration_seconds: number | null
}
export interface RunMetrics {
  cases: number; recovered: number; amount_recovered_minor: number
  network_attempts: number; duplicate_charges: number
  compliance_violations: number | null; escalated: number; refusals: number
  hard_class_retries: number; duplicate_charge_prevented: number
  deferred: number; deferred_amount_minor: number
  tiers: Record<string, number>; status_counts: Record<string, number>
}
export interface ArmMetrics {
  arm: string; run_id: string; cases: number; recovered: number; recovery_rate: number
  amount_recovered_minor: number; network_attempts: number; duplicate_charges: number
  compliance_violations: number | null; hard_class_retries: number; escalated: number
  duplicate_charge_prevented: number; attempt_efficiency_minor_per_call: number
  deferred: number; deferred_amount_minor: number
  tiers: Record<string, number>
}
export interface Comparison { seed: number; dunnflow: ArmMetrics | null; control: ArmMetrics | null }
export interface ClassCount { code: string; family: string; count: number; pct: number; recoverable: boolean }
export interface Series { labels: string[]; dunnflow: number[]; control: number[] }
export interface Tiers { tiers: Record<string, number>; total: number; no_model_pct: number; note: string }
export interface Paged<T> { items: T[]; total: number; limit?: number; offset?: number }
export interface Case {
  id: string; case_ref: string; merchant_id: string; obligation_ref: string
  failure_class: string; failure_family: string; amount_minor: number; status: string
  rule_id: string | null; classifier_tier: string | null; classifier_conf: number | null
  attempts: number; created_at: string; resolved_at: string | null
}
export interface TimelineEvent {
  seq: number; node: string; state_from: string | null; state_to: string | null
  rule_id: string | null; note: string | null; flags: Record<string, unknown>; occurred_at: string
}
export interface ConstraintRow { position: number; constraint_id: string; decision: string; reason: string | null; unverified: boolean }
export interface AttemptRow {
  attempt_index: number; action: string; outcome: string; idempotency_key: string
  gateway_ref: string | null; amount_minor: number; error_raw: unknown
  started_at: string; settled_at: string | null
}
export interface Refusal {
  case_ref: string; constraint_id: string; rule_id: string | null; failure_class: string | null
  reason: string | null; proposed_action: string; unverified: boolean; evaluated_at: string
}
export interface RefusalSummary { constraint_id: string; position: number; refusals: number; unverified: boolean; description: string }
export interface ExceptionCase extends Case { reason: string | null; decided: string | null }
export interface Decision { case_ref: string; status: string; decision: string }
export interface AuditEntry {
  seq: number; case_ref: string | null; entry_type: string; node: string | null
  rule_id: string | null; model_id: string | null; state_to: string | null
  prev_hash: string; hash: string; occurred_at: string
}
export interface AuditStatus { ok: boolean; seq_head: number; total_entries: number; decisions_with_model: number }
export interface VerifyResult { ok: boolean; first_divergent_seq: number | null; verified_through: number; entries_checked: number }
export interface Fault { id: string; label: string; family: string; severity: string; description: string; state: string }
export interface FaultState { fault_id: string; state: string }
export interface TaxonomyClass {
  code: string; terminality: string; retry_eligible: boolean; hard_class: boolean
  prohibited: boolean; max_attempts: number; backoff: string; rule_id: string | null; recoverable: boolean
}
export interface Taxonomy { version: string; families: { family: string; description: string; classes: TaxonomyClass[] }[] }
export interface ConstraintSpec { position: number; id: string; fail_mode: string; description: string; unverified?: boolean }
export interface CaseIntakeInput {
  merchant_id: string
  obligation_ref: string
  amount_minor: number
  failure_source: string
  failure_step: string
  failure_reason: string
  error_description: string
  customer_tokens: string[]
  retry_count?: number
}
export interface CaseIntakeResult {
  case_ref: string
  status: string
  dry_run?: boolean
  summary: string
  llm_mode: string
  classification: { code: string; confidence: number; tier: string; taxonomy_version: string; evidence_span?: string | null }
  decision: { action: string; rule_id: string; policy_version: string; rationale_code: string; requires_human_approval: boolean; scheduled_at?: string | null; attempts_remaining: number }
  sanitizer: { masked_text: string; sanitizer_summary: Record<string, unknown> }
  taxonomy: { terminality: string; recoverable: boolean }
}
