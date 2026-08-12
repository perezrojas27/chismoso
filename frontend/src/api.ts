import { authHeaders } from './portalAuth'

const API = '/api/biometrico'

export type AttendanceRow = {
  date: string
  employee_id: string
  employee_name: string
  department: string
  first_seen_at: string
  last_seen_at: string | null
}

export type AttendanceReport = {
  from_date: string
  to_date: string
  rows: AttendanceRow[]
}

export type CafeteriaEmployee = {
  employee_id: string
  employee_name: string
  department: string
  marked_time: string
  observation?: string
  has_exception?: boolean
}

export type CafeteriaReport = {
  date: string
  cutoff: string
  headcount: number
  employees: CafeteriaEmployee[]
  exceptions_count?: number
}

export type DeviceSearchSample = {
  employee_id: string
  employee_name: string
  timestamp: string
}

export type DeviceSearchResult = {
  date: string
  total_matches: number
  sample_count: number
  samples: DeviceSearchSample[]
  message: string
}

export type DeviceHealth = {
  device_id: string
  host: string
  port?: number
  location?: string
  /** Código de sede del agente edge (cloud inventory). */
  site_code?: string | null
  site_id?: string | null
  agent_hostname?: string | null
  reachable: boolean | null
  auth_ok?: boolean | null
  error: string | null
  online?: boolean | null
  connection_established?: boolean
  configured?: boolean
  status_message?: string
  suggested_id?: string
  device_label?: string | null
  search?: DeviceSearchResult | null
  origin?: 'env' | 'managed' | 'discovered' | 'agent'
  removable?: boolean
}

export type DevicesResponse = {
  status: string
  source: string
  user: string
  use_https: boolean
  cafeteria_cutoff: string
  cafeteria_late_end: string
  devices: DeviceHealth[]
  devices_ok: number
  devices_total: number
  message?: string
  read_only?: boolean
}

export type HealthResponse = {
  status: string
  source: string
  device_id: string
  cafeteria_cutoff: string
  devices?: DeviceHealth[]
  devices_ok?: number
  devices_total?: number
  auth_disabled?: boolean
  client_id?: string
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json()
    if (data?.detail?.message) return data.detail.message as string
    if (typeof data?.detail === 'string') return data.detail
    if (Array.isArray(data?.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join('; ')
    }
    return res.statusText || 'Error de API'
  } catch {
    return res.statusText || 'Error de API'
  }
}

async function apiFetch(path: string, init?: RequestInit, retries = 2): Promise<Response> {
  const headers = authHeaders(init?.headers)
  let lastErr: unknown
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(`${API}${path}`, {
        ...init,
        credentials: 'include',
        headers,
      })
      // Retry solo en errores de servidor (5xx), no en auth/cliente
      if (!res.ok && res.status >= 500 && attempt < retries) {
        await new Promise((r) => setTimeout(r, 300 * Math.pow(2, attempt)))
        continue
      }
      return res
    } catch (err) {
      lastErr = err
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, 300 * Math.pow(2, attempt)))
      }
    }
  }
  throw lastErr ?? new Error('Error de red')
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await apiFetch('/health')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function fetchDevices(): Promise<DevicesResponse> {
  const res = await apiFetch('/devices')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function createDevice(body: {
  host: string
  port: number
  location?: string
  device_id?: string
}): Promise<{ device: { device_id: string; host: string; port: number; location?: string }; message: string }> {
  const res = await apiFetch('/devices', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function deleteDevice(deviceId: string): Promise<{ message: string }> {
  const res = await apiFetch(`/devices/${encodeURIComponent(deviceId)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export type SiteInfo = {
  id: string
  code: string
  name: string
  timezone: string
  status: string
  cafeteria_cutoff?: string
  cafeteria_late_end?: string
}

export type SitesResponse = {
  current_site_id: string
  site_code: string
  sites: SiteInfo[]
  agent_version: string
}

export async function fetchSites(): Promise<SitesResponse> {
  const res = await apiFetch('/edge/sites')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

function withSite(params: URLSearchParams, siteId?: string | null) {
  if (siteId) params.set('site_id', siteId)
  return params
}

export async function fetchAttendance(
  fromDate: string,
  toDate: string,
  siteId?: string | null,
): Promise<AttendanceReport> {
  const params = withSite(
    new URLSearchParams({ from_date: fromDate, to_date: toDate }),
    siteId,
  )
  const res = await apiFetch(`/reports/attendance?${params}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function fetchCafeteria(
  date: string,
  siteId?: string | null,
): Promise<CafeteriaReport> {
  const params = withSite(new URLSearchParams({ date }), siteId)
  const res = await apiFetch(`/reports/cafeteria?${params}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function fetchAttendancePdfBlob(
  fromDate: string,
  toDate: string,
  siteId?: string | null,
): Promise<Blob> {
  const params = withSite(
    new URLSearchParams({ from_date: fromDate, to_date: toDate }),
    siteId,
  )
  const res = await apiFetch(`/reports/attendance/pdf?${params}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.blob()
}

export async function fetchCafeteriaPdfBlob(
  date: string,
  siteId?: string | null,
): Promise<Blob> {
  const params = withSite(new URLSearchParams({ date }), siteId)
  const res = await apiFetch(`/reports/cafeteria/pdf?${params}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.blob()
}

export type CafeteriaException = {
  employee_id: string
  date: string
  reason: string
  registered_by: string
}

export type LateCandidate = {
  employee_id: string
  employee_name: string
  department: string
  marked_time: string
  has_exception: boolean
}

export async function fetchCafeteriaExceptions(date: string): Promise<CafeteriaException[]> {
  const params = new URLSearchParams({ date })
  const res = await apiFetch(`/exceptions/cafeteria?${params}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function fetchLateCandidates(date: string): Promise<LateCandidate[]> {
  const params = new URLSearchParams({ date })
  const res = await apiFetch(`/exceptions/cafeteria/candidates?${params}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function createCafeteriaException(body: {
  employee_id: string
  date: string
  reason: string
}): Promise<CafeteriaException> {
  const res = await apiFetch('/exceptions/cafeteria', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...body, registered_by: 'GTH' }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function deleteCafeteriaException(date: string, employeeId: string): Promise<void> {
  const params = new URLSearchParams({ date, employee_id: employeeId })
  const res = await apiFetch(`/exceptions/cafeteria?${params}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await parseError(res))
}

export type BioLinkageItem = {
  employee_id: string
  cedula: string
  full_name: string
  site_id: string | null
  site_name: string
  linked: boolean
  person_external_id: string | null
  linked_at: string | null
  linked_by: string
}

export type BioPersonUnlinked = {
  person_external_id: string
  person_name: string
  employee_code: string
  event_count: number
  last_seen: string | null
  suggested_cedula_match: string
}

export type PresencePerson = {
  employee_id: string
  cedula: string
  full_name: string
  person_external_id: string | null
}

export type PresenceReport = {
  date: string
  core_site_id: string
  biometric_site_ids: string[]
  site_map_missing: boolean
  expected_active: number
  present: PresencePerson[]
  absent: PresencePerson[]
  unlinked_employees: PresencePerson[]
  counts: { present: number; absent: number; unlinked: number }
}

export async function fetchBioLinkageActive(opts?: {
  q?: string
  link_filter?: 'all' | 'linked' | 'unlinked'
  site_id?: string
}): Promise<{ total: number; stats: { active: number; linked: number; unlinked: number }; items: BioLinkageItem[] }> {
  const params = new URLSearchParams()
  if (opts?.q) params.set('q', opts.q)
  if (opts?.link_filter) params.set('link_filter', opts.link_filter)
  if (opts?.site_id) params.set('site_id', opts.site_id)
  const res = await apiFetch(`/person-linkage/active?${params}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function fetchBioPersonsUnlinked(opts?: {
  q?: string
  site_id?: string
}): Promise<{ count: number; items: BioPersonUnlinked[] }> {
  const params = new URLSearchParams()
  if (opts?.q) params.set('q', opts.q)
  if (opts?.site_id) params.set('site_id', opts.site_id)
  const res = await apiFetch(`/person-linkage/persons/unlinked?${params}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function linkBioPerson(employeeId: string, personExternalId: string, notes = '') {
  const res = await apiFetch(`/person-linkage/${encodeURIComponent(employeeId)}/link`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ person_external_id: personExternalId, notes }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function unlinkBioPerson(employeeId: string) {
  const res = await apiFetch(`/person-linkage/${encodeURIComponent(employeeId)}/unlink`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export type CatalogSite = {
  id: string
  name: string
  city?: string | null
  address?: string | null
}

/** Sedes activas GTH (mismo origen portal). */
export async function fetchCatalogSites(): Promise<CatalogSite[]> {
  const res = await fetch('/api/auth/catalog/sites', {
    credentials: 'include',
    headers: authHeaders(),
    cache: 'no-store',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function fetchPresenceReport(opts: {
  date: string
  core_site_id: string
  biometric_site_id?: string
}): Promise<PresenceReport> {
  const params = new URLSearchParams({
    date: opts.date,
    core_site_id: opts.core_site_id,
  })
  if (opts.biometric_site_id) params.set('biometric_site_id', opts.biometric_site_id)
  const res = await apiFetch(`/person-linkage/presence?${params}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

/** Fecha visible: día/mes/año (ej. 15/07/2026). Acepta YYYY-MM-DD o ISO. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const raw = value.includes('T') ? value.slice(0, 10) : value.slice(0, 10)
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw)
  if (match) return `${match[3]}/${match[2]}/${match[1]}`
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  const day = String(d.getDate()).padStart(2, '0')
  const month = String(d.getMonth() + 1).padStart(2, '0')
  return `${day}/${month}/${d.getFullYear()}`
}

export function formatTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) {
    const part = iso.includes('T') ? iso.split('T')[1] : iso
    return part.slice(0, 8)
  }
  return d.toLocaleTimeString('es-VE', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
