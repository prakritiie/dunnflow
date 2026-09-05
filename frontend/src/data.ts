// ─── Formatters ───────────────────────────────────────────────────────────────

export function fmtCurrency(minor?: number | null): string {
  if (minor === undefined || minor === null || isNaN(minor)) return '₹0'
  const rupees = Math.floor(minor / 100)
  const str = Math.abs(rupees).toString()
  const sign = rupees < 0 ? '-' : ''
  if (str.length <= 3) return `${sign}₹${str}`
  const last3 = str.slice(-3)
  const rest = str.slice(0, -3)
  const formatted = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',')
  return `${sign}₹${formatted},${last3}`
}

export function fmtCurrencyAbbr(minor?: number | null): string {
  if (minor === undefined || minor === null || isNaN(minor)) return '₹0'
  const rupees = minor / 100
  if (rupees >= 10000000) return `₹${(rupees / 10000000).toFixed(1)}Cr`
  if (rupees >= 100000) return `₹${(rupees / 100000).toFixed(1)}L`
  if (rupees >= 1000) return `₹${(rupees / 1000).toFixed(1)}K`
  return `₹${rupees}`
}

export function fmtPct(n?: number | null): string {
  if (n === undefined || n === null || isNaN(n)) return '0.0%'
  return `${(n * 100).toFixed(1)}%`
}

export function fmtIST(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  return d
    .toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false })
    .replace(',', '')
}

export function fmtDuration(seconds?: number | null): string {
  if (!seconds || isNaN(seconds)) return '0s'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

// ─── Shared UI constants (not data) ──────────────────────────────────────────

export const STATUS_COLORS: Record<string, string> = {
  RECOVERED: 'signal-positive',
  DUPLICATE_CHARGE_PREVENTED: 'signal-positive',
  SCHEDULED: 'signal-caution',
  NEEDS_HUMAN: 'signal-neutral',
  IN_FLIGHT: 'signal-ambiguous',
  RECON_PENDING: 'signal-ambiguous',
  EXHAUSTED: 'signal-neutral',
  TERMINATED: 'signal-neutral',
}

export type CaseStatus = keyof typeof STATUS_COLORS

// All runtime data now comes from the API - see src/lib/api.ts
