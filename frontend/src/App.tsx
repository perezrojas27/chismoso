import { useEffect, useMemo, useRef, useState } from 'react'
import {
  fetchAttendance,
  fetchAttendancePdfBlob,
  fetchCafeteria,
  fetchCafeteriaPdfBlob,
  fetchHealth,
  fetchSites,
  type AttendanceReport,
  type CafeteriaReport,
  type HealthResponse,
  type SiteInfo,
} from './api'
import { AttendanceTable } from './components/AttendanceTable'
import { CafeteriaTable } from './components/CafeteriaTable'
import { DevicesPanel } from './components/DevicesPanel'
import { GthExceptionPanel } from './components/GthExceptionPanel'
import { PdfPreviewModal } from './components/PdfPreviewModal'
import { PeriodSelector } from './components/PeriodSelector'
import { PersonLinkagePanel } from './components/PersonLinkagePanel'
import {
  anchorForFortnight,
  anchorForMonth,
  anchorForQuarter,
  anchorForSemester,
  clampRangeToToday,
  clampToToday,
  fortnightHalfFromISO,
  maxSelectableYear,
  monthIndexFromISO,
  quarterIndexFromISO,
  rangeForPeriod,
  selectableFortnightHalves,
  selectableMonthIndexes,
  selectableQuarterIndexes,
  selectableSemesterIndexes,
  semesterIndexFromISO,
  todayISO,
  validateDateRange,
  yearFromISO,
  type AttendancePeriod,
  type QuarterIndex,
  type SemesterIndex,
} from './periodRange'
import {
  ROLE_ADMIN,
  ROLE_GTH,
  ROLE_SERVICIOS,
  backToHub,
  canAccessAttendance,
  canAccessCafeteria,
  canGenerateReports,
  canManageDevices,
  canOperateGth,
  displayName,
  getDevRole,
  isAuthRequired,
  roleLabel,
  setDevRole,
  type AppRole,
} from './portalAuth'

// ── SessionStorage helpers ────────────────────────────────────────────────────
function saveSess(key: string, value: unknown) {
  try {
    sessionStorage.setItem(`bio_${key}`, JSON.stringify(value))
  } catch {
    /* ignore */
  }
}
function loadSess<T>(key: string, fallback: T): T {
  try {
    const raw = sessionStorage.getItem(`bio_${key}`)
    if (raw !== null) return JSON.parse(raw) as T
  } catch {
    /* ignore */
  }
  return fallback
}

// ── Tipos ─────────────────────────────────────────────────────────────────────
type Tab = 'attendance' | 'cafeteria' | 'devices' | 'linkage'

type PreviewState = {
  open: boolean
  title: string
  filename: string
  blobUrl: string | null
  loading: boolean
  error: string | null
}

const PREVIEW_CLOSED: PreviewState = {
  open: false,
  title: '',
  filename: '',
  blobUrl: null,
  loading: false,
  error: null,
}

// ── Countdown de corte de comedor ─────────────────────────────────────────────
function computeCafeCountdown(
  cutoff: string | undefined,
): { label: string; urgent: boolean } | null {
  if (!cutoff) return null
  const parts = cutoff.split(':').map(Number)
  const h = parts[0] ?? 0
  const m = parts[1] ?? 0
  const s = parts[2] ?? 0
  const now = new Date()
  const cutoffDate = new Date(now)
  cutoffDate.setHours(h, m, s, 0)
  const diff = cutoffDate.getTime() - now.getTime()
  if (diff <= 0) return null
  const totalSecs = Math.floor(diff / 1000)
  const hours = Math.floor(totalSecs / 3600)
  const mins = Math.floor((totalSecs % 3600) / 60)
  const secs = totalSecs % 60
  const label =
    hours > 0
      ? `${hours}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
      : `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
  return { label, urgent: diff < 10 * 60 * 1000 }
}

// ── Componente principal ──────────────────────────────────────────────────────
export default function App() {
  const maxDate = todayISO()
  const [devRole, setDevRoleState] = useState<AppRole>(() => getDevRole())

  // Restaurar estado desde sessionStorage
  const [tab, setTab] = useState<Tab>(() => loadSess<Tab>('tab', 'cafeteria'))
  const [period, setPeriod] = useState<AttendancePeriod>(() =>
    loadSess<AttendancePeriod>('period', 'day'),
  )
  const initialRange = rangeForPeriod(
    loadSess<AttendancePeriod>('period', 'day'),
    loadSess('anchorDate', maxDate),
  )
  const [anchorDate, setAnchorDate] = useState(() => loadSess('anchorDate', maxDate))
  const [fromDate, setFromDate] = useState(initialRange.from)
  const [toDate, setToDate] = useState(initialRange.to)
  const [cafeDate, setCafeDate] = useState(() => loadSess('cafeDate', maxDate))

  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [attendance, setAttendance] = useState<AttendanceReport | null>(null)
  const [cafeteria, setCafeteria] = useState<CafeteriaReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<PreviewState>(PREVIEW_CLOSED)
  const [listEntryKey, setListEntryKey] = useState(0)
  const [sites, setSites] = useState<SiteInfo[]>([])
  const [siteId, setSiteId] = useState<string>(() => loadSess('siteId', ''))

  // Tick de 1 s para el countdown del comedor
  const [, setTick] = useState(0)

  // Para detectar cambios de pestaña en la carga progresiva
  const prevTabRef = useRef<Tab>(tab)

  const attendanceRangeError = useMemo(
    () => validateDateRange(fromDate, toDate, maxDate),
    [fromDate, toDate, maxDate],
  )
  const cafeteriaDateError = useMemo(() => {
    if (cafeDate > maxDate) return validateDateRange(cafeDate, cafeDate, maxDate)
    return null
  }, [cafeDate, maxDate])

  // Countdown solo si estamos viendo el comedor de hoy
  const cafeCountdown = useMemo(() => {
    if (tab !== 'cafeteria' || cafeDate !== maxDate) return null
    return computeCafeCountdown(health?.cafeteria_cutoff)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, cafeDate, maxDate, health?.cafeteria_cutoff])

  // Persistencia en sessionStorage
  useEffect(() => { saveSess('tab', tab) }, [tab])
  useEffect(() => { saveSess('period', period) }, [period])
  useEffect(() => { saveSess('anchorDate', anchorDate) }, [anchorDate])
  useEffect(() => { saveSess('cafeDate', cafeDate) }, [cafeDate])
  useEffect(() => { saveSess('siteId', siteId) }, [siteId])

  // Tick de 1 s
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000)
    return () => clearInterval(id)
  }, [])

  // Health
  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
  }, [])

  // Corregir pestaña activa si el rol cambia
  useEffect(() => {
    if (tab === 'linkage' && !canOperateGth()) {
      setTab(canAccessCafeteria() ? 'cafeteria' : 'attendance')
    } else if (tab === 'devices' && !canManageDevices()) {
      setTab(canAccessCafeteria() ? 'cafeteria' : 'attendance')
    } else if (tab === 'attendance' && !canAccessAttendance()) {
      setTab('cafeteria')
    } else if (tab === 'cafeteria' && !canAccessCafeteria()) {
      setTab(canAccessAttendance() ? 'attendance' : 'devices')
    }
  }, [devRole, tab])

  // Sedes
  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const data = await fetchSites()
        if (cancelled) return
        setSites(data.sites)
        setSiteId((prev) => prev || data.current_site_id || data.sites[0]?.id || '')
      } catch {
        /* sede opcional */
      }
    })()
    return () => { cancelled = true }
  }, [])

  // Regeneración de datos con carga progresiva
  useEffect(() => {
    const tabChanged = prevTabRef.current !== tab
    prevTabRef.current = tab
    let cancelled = false

    async function regenerate() {
      if (tab === 'devices') {
        setAttendance(null)
        setCafeteria(null)
        setError(null)
        setLoading(false)
        return
      }

      // Si se cambió de pestaña: limpiar datos stale inmediatamente
      if (tabChanged) {
        setAttendance(null)
        setCafeteria(null)
      }
      setLoading(true)
      setError(null)

      try {
        if (tab === 'cafeteria') {
          const safeDate = clampToToday(cafeDate)
          if (safeDate !== cafeDate) setCafeDate(safeDate)
          const cafeErr = validateDateRange(safeDate, safeDate, maxDate)
          if (cafeErr) throw new Error(cafeErr)
          const data = await fetchCafeteria(safeDate, siteId || null)
          if (!cancelled) setCafeteria(data)
        } else if (tab === 'attendance') {
          const safe = clampRangeToToday(fromDate, toDate, maxDate)
          if (safe.from !== fromDate) setFromDate(safe.from)
          if (safe.to !== toDate) setToDate(safe.to)
          const rangeErr = validateDateRange(safe.from, safe.to, maxDate)
          if (rangeErr) throw new Error(rangeErr)
          const data = await fetchAttendance(safe.from, safe.to, siteId || null)
          if (!cancelled) setAttendance(data)
        }
      } catch (err) {
        if (!cancelled) {
          setAttendance(null)
          setCafeteria(null)
          setError(
            err instanceof Error
              ? err.message
              : tab === 'cafeteria'
                ? 'Error al cargar comedor'
                : 'Error al cargar asistencia',
          )
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void regenerate()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, listEntryKey, siteId])

  useEffect(() => {
    return () => {
      if (preview.blobUrl) URL.revokeObjectURL(preview.blobUrl)
    }
  }, [preview.blobUrl])

  // ── Handlers ────────────────────────────────────────────────────────────────

  function clearListings() {
    setAttendance(null)
    setCafeteria(null)
    setError(null)
  }

  function applyPeriod(nextPeriod: AttendancePeriod, nextAnchor?: string) {
    let anchor = clampToToday(nextAnchor ?? todayISO())
    if (yearFromISO(anchor) > maxSelectableYear()) anchor = todayISO()

    if (nextPeriod === 'month') {
      const year = yearFromISO(anchor)
      let month = monthIndexFromISO(anchor)
      const allowed = selectableMonthIndexes(year)
      if (!allowed.includes(month)) {
        month = allowed[allowed.length - 1] ?? 0
        anchor = anchorForMonth(year, month)
      }
    }

    if (nextPeriod === 'fortnight') {
      const year = yearFromISO(anchor)
      let month = monthIndexFromISO(anchor)
      const months = selectableMonthIndexes(year)
      if (!months.includes(month)) month = months[months.length - 1] ?? 0
      let half = fortnightHalfFromISO(anchor)
      const halves = selectableFortnightHalves(year, month)
      if (!halves.includes(half)) half = halves[halves.length - 1] ?? '1Q'
      anchor = clampToToday(anchorForFortnight(year, month, half))
    }

    if (nextPeriod === 'quarter') {
      const year = yearFromISO(anchor)
      let quarter = quarterIndexFromISO(anchor)
      const allowed = selectableQuarterIndexes(year)
      if (!allowed.includes(quarter)) quarter = (allowed[allowed.length - 1] ?? 0) as QuarterIndex
      anchor = clampToToday(anchorForQuarter(year, quarter))
    }

    if (nextPeriod === 'semester') {
      const year = yearFromISO(anchor)
      let semester = semesterIndexFromISO(anchor)
      const allowed = selectableSemesterIndexes(year)
      if (!allowed.includes(semester))
        semester = (allowed[allowed.length - 1] ?? 0) as SemesterIndex
      anchor = clampToToday(anchorForSemester(year, semester))
    }

    const computed = rangeForPeriod(nextPeriod, anchor)
    const safe = clampRangeToToday(computed.from, computed.to)
    setPeriod(nextPeriod)
    setAnchorDate(clampToToday(anchor))
    setFromDate(safe.from)
    setToDate(safe.to)
    clearListings()
  }

  async function loadAttendance() {
    setLoading(true)
    setError(null)
    try {
      const safe = clampRangeToToday(fromDate, toDate, maxDate)
      if (safe.from !== fromDate) setFromDate(safe.from)
      if (safe.to !== toDate) setToDate(safe.to)
      const rangeErr = validateDateRange(safe.from, safe.to, maxDate)
      if (rangeErr) throw new Error(rangeErr)
      const data = await fetchAttendance(safe.from, safe.to, siteId || null)
      setAttendance(data)
    } catch (err) {
      setAttendance(null)
      setError(err instanceof Error ? err.message : 'Error al cargar asistencia')
    } finally {
      setLoading(false)
    }
  }

  async function loadCafeteria() {
    setLoading(true)
    setError(null)
    try {
      const safeDate = clampToToday(cafeDate)
      if (safeDate !== cafeDate) setCafeDate(safeDate)
      const cafeErr = validateDateRange(safeDate, safeDate, maxDate)
      if (cafeErr) throw new Error(cafeErr)
      const data = await fetchCafeteria(safeDate, siteId || null)
      setCafeteria(data)
    } catch (err) {
      setCafeteria(null)
      setError(err instanceof Error ? err.message : 'Error al cargar comedor')
    } finally {
      setLoading(false)
    }
  }

  async function openPreview(title: string, filename: string, loader: () => Promise<Blob>) {
    if (preview.blobUrl) URL.revokeObjectURL(preview.blobUrl)
    setPreview({ open: true, title, filename, blobUrl: null, loading: true, error: null })
    try {
      const blob = await loader()
      const url = URL.createObjectURL(blob)
      setPreview({ open: true, title, filename, blobUrl: url, loading: false, error: null })
    } catch (err) {
      setPreview({
        open: true,
        title,
        filename,
        blobUrl: null,
        loading: false,
        error: err instanceof Error ? err.message : 'No se pudo generar el PDF',
      })
    }
  }

  function closePreview() {
    if (preview.blobUrl) URL.revokeObjectURL(preview.blobUrl)
    setPreview(PREVIEW_CLOSED)
  }

  const pageTitle =
    tab === 'cafeteria'
      ? 'Cierre diario de comedor'
      : tab === 'devices'
        ? 'Dispositivos biométricos'
        : tab === 'linkage'
          ? 'Vínculo GTH ↔ biométrico'
          : 'Asistencia — primera y última marca'

  function goTab(next: Tab) {
    setTab(next)
    setError(null)
    if (next === 'cafeteria') setCafeDate(todayISO())
    else if (next === 'attendance') applyPeriod(period)
    setListEntryKey((k) => k + 1)
  }

  function onDevRoleChange(role: AppRole) {
    setDevRole(role)
    setDevRoleState(role)
    setTab(role === ROLE_SERVICIOS ? 'cafeteria' : canAccessAttendance() ? 'attendance' : 'cafeteria')
    setListEntryKey((k) => k + 1)
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <>
      <aside className="sidebar">
        <div className="sidebar-header">
          <img
            src="/assets/brand/logo-integrado-mark.svg"
            alt="Albatros INTEGRADO"
            data-brand-logo="true"
            data-integrado-mark="true"
          />
        </div>
        <nav aria-label="Secciones">
          {canAccessCafeteria() && (
            <button
              type="button"
              className={`nav-item ${tab === 'cafeteria' ? 'active' : ''}`}
              onClick={() => goTab('cafeteria')}
            >
              Comedor
            </button>
          )}
          {canAccessAttendance() && (
            <button
              type="button"
              className={`nav-item ${tab === 'attendance' ? 'active' : ''}`}
              onClick={() => goTab('attendance')}
            >
              Asistencia
            </button>
          )}
          {canManageDevices() && (
            <button
              type="button"
              className={`nav-item ${tab === 'devices' ? 'active' : ''}`}
              onClick={() => goTab('devices')}
            >
              Dispositivos
            </button>
          )}
          {canOperateGth() && (
            <button
              type="button"
              className={`nav-item ${tab === 'linkage' ? 'active' : ''}`}
              onClick={() => goTab('linkage')}
            >
              Vínculo GTH
            </button>
          )}
        </nav>
        <div className="sidebar-foot">
          {health?.auth_disabled
            ? 'Auth local desactivada'
            : `API · ${health?.client_id ?? 'biometrico'}`}
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="topbar-title-wrap">
            <h1>{pageTitle}</h1>
            <div className="topbar-sub">Control de Biométricos</div>
          </div>
          <div className="topbar-tools">
            {sites.length > 0 && (
              <label className="dev-role">
                <span className="visually-hidden">Sede</span>
                <select
                  value={siteId}
                  onChange={(e) => setSiteId(e.target.value)}
                  title="Sede (multi-sede)"
                >
                  {sites.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{displayName()}</span>
            {!isAuthRequired() && (
              <label className="dev-role">
                <span className="visually-hidden">Rol local</span>
                <select
                  value={devRole}
                  onChange={(e) => onDevRoleChange(e.target.value as AppRole)}
                  title="Simular rol (solo desarrollo local)"
                >
                  <option value={ROLE_ADMIN}>{roleLabel(ROLE_ADMIN)}</option>
                  <option value={ROLE_GTH}>{roleLabel(ROLE_GTH)}</option>
                  <option value={ROLE_SERVICIOS}>{roleLabel(ROLE_SERVICIOS)}</option>
                </select>
              </label>
            )}
            <div className="status-chip status-chip--compact">
              <span
                className={`status-dot ${
                  health?.status === 'ok'
                    ? ''
                    : health?.status === 'partial'
                      ? 'status-dot--warn'
                      : health?.status === 'degraded'
                        ? 'status-dot--bad'
                        : ''
                }`}
              />
              {health
                ? health.source === 'hikvision' && health.devices
                  ? `Hikvision · ${health.devices_ok ?? 0}/${health.devices_total ?? health.devices.length}`
                  : `${health.source}`
                : 'API…'}
            </div>
            <button type="button" className="btn btn-hub" onClick={() => backToHub()}>
              ← Hub
            </button>
          </div>
        </header>

        <div className="content module-fluid">
          <div className="layout">
            {tab === 'linkage' ? (
              <PersonLinkagePanel biometricSiteId={siteId || undefined} />
            ) : tab === 'devices' ? (
              <DevicesPanel />
            ) : tab === 'cafeteria' ? (
              <section className="glass panel">
                <h2 className="panel__title visually-hidden">Cierre diario de comedor</h2>

                <div className="controls">
                  <div className="field">
                    <label htmlFor="cafe-date">Fecha</label>
                    <input
                      id="cafe-date"
                      type="date"
                      max={maxDate}
                      value={cafeDate}
                      onChange={(e) => {
                        setCafeDate(clampToToday(e.target.value))
                        setCafeteria(null)
                        setError(null)
                      }}
                    />
                  </div>

                  {/* Countdown de corte de comedor */}
                  {cafeCountdown && (
                    <div className={`cafe-countdown ${cafeCountdown.urgent ? 'cafe-countdown--urgent' : ''}`}
                         aria-live="off">
                      <span className="cafe-countdown__label">Corte en</span>
                      <span className="cafe-countdown__time">{cafeCountdown.label}</span>
                    </div>
                  )}

                  <div className="actions">
                    {canGenerateReports() && (
                      <button
                        type="button"
                        className="btn btn--primary"
                        onClick={() => void loadCafeteria()}
                        disabled={loading || !!cafeteriaDateError}
                      >
                        Generar
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn--ghost"
                      onClick={() =>
                        void openPreview(
                          'Cierre Diario — Comedor',
                          `comedor_${clampToToday(cafeDate)}.pdf`,
                          () => {
                            const safeDate = clampToToday(cafeDate)
                            const cafeErr = validateDateRange(safeDate, safeDate, maxDate)
                            if (cafeErr) return Promise.reject(new Error(cafeErr))
                            return fetchCafeteriaPdfBlob(safeDate, siteId || null)
                          },
                        )
                      }
                      disabled={!cafeteria || !!cafeteriaDateError}
                    >
                      PDF
                    </button>
                  </div>
                </div>

                {cafeteriaDateError && (
                  <p className="period-anchor-hint" role="alert">
                    {cafeteriaDateError}
                  </p>
                )}
                {!canGenerateReports() && (
                  <p className="period-anchor-hint">
                    Listado de comedor (corte ≤ 09:00 e inclusiones ya autorizadas por GTH). Solo
                    impresión PDF; sin gestión de excepciones.
                  </p>
                )}

                {/* Carga progresiva: overlay cuando ya hay data y se está recargando */}
                <div className="table-progressive-wrap">
                  <CafeteriaTable
                    report={cafeteria}
                    loading={loading && !cafeteria}
                    error={!loading ? error : null}
                    hideGthDetails={!canOperateGth()}
                  />
                  {loading && cafeteria && (
                    <div className="table-progressive-overlay" aria-busy="true">
                      <span className="spinner" aria-hidden="true" />
                    </div>
                  )}
                </div>

                {cafeteria && !loading && canOperateGth() && (
                  <GthExceptionPanel
                    date={clampToToday(cafeDate)}
                    onChanged={() => { void loadCafeteria() }}
                  />
                )}
              </section>
            ) : (
              <section className="glass panel">
                <h2 className="panel__title visually-hidden">
                  Asistencia — primera y última marca
                </h2>

                {/* Selector de periodo (extraído) */}
                <PeriodSelector
                  period={period}
                  anchorDate={anchorDate}
                  fromDate={fromDate}
                  toDate={toDate}
                  maxDate={maxDate}
                  onApply={applyPeriod}
                />

                <div className="actions" style={{ marginTop: '4px', marginBottom: '18px' }}>
                  {canGenerateReports() && (
                    <button
                      type="button"
                      className="btn btn--primary"
                      onClick={() => void loadAttendance()}
                      disabled={loading || !!attendanceRangeError}
                    >
                      Generar
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn btn--ghost"
                    onClick={() =>
                      void openPreview(
                        'Control de Asistencia',
                        `asistencia_${fromDate}_${toDate}.pdf`,
                        () => {
                          const safe = clampRangeToToday(fromDate, toDate, maxDate)
                          const rangeErr = validateDateRange(safe.from, safe.to, maxDate)
                          if (rangeErr) return Promise.reject(new Error(rangeErr))
                          return fetchAttendancePdfBlob(safe.from, safe.to, siteId || null)
                        },
                      )
                    }
                    disabled={!attendance || !!attendanceRangeError}
                  >
                    PDF
                  </button>
                </div>

                {attendanceRangeError && (
                  <p className="period-anchor-hint" role="alert">
                    {attendanceRangeError}
                  </p>
                )}

                {/* Carga progresiva: overlay cuando ya hay data y se está recargando */}
                <div className="table-progressive-wrap">
                  <AttendanceTable
                    report={attendance}
                    loading={loading && !attendance}
                    error={!loading ? error : null}
                  />
                  {loading && attendance && (
                    <div className="table-progressive-overlay" aria-busy="true">
                      <span className="spinner" aria-hidden="true" />
                    </div>
                  )}
                </div>
              </section>
            )}
          </div>
        </div>
      </main>

      <PdfPreviewModal
        open={preview.open}
        title={preview.title}
        filename={preview.filename}
        blobUrl={preview.blobUrl}
        loading={preview.loading}
        error={preview.error}
        onClose={closePreview}
      />
    </>
  )
}
