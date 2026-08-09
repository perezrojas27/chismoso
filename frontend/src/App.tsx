import { useEffect, useMemo, useState } from 'react'
import {
  fetchAttendance,
  fetchAttendancePdfBlob,
  fetchCafeteria,
  fetchCafeteriaPdfBlob,
  fetchHealth,
  fetchSites,
  formatDate,
  type AttendanceReport,
  type CafeteriaReport,
  type HealthResponse,
  type SiteInfo,
} from './api'
import { AttendanceTable } from './components/AttendanceTable'
import { CafeteriaTable } from './components/CafeteriaTable'
import { DevicesPanel } from './components/DevicesPanel'
import { GthExceptionPanel } from './components/GthExceptionPanel'
import { PersonLinkagePanel } from './components/PersonLinkagePanel'
import { PdfPreviewModal } from './components/PdfPreviewModal'
import {
  ATTENDANCE_PERIODS,
  MONTH_NAMES,
  QUARTER_LABELS,
  SEMESTER_LABELS,
  anchorForFortnight,
  anchorForMonth,
  anchorForQuarter,
  anchorForSemester,
  clampToToday,
  clampRangeToToday,
  fortnightHalfFromISO,
  maxSelectableYear,
  monthIndexFromISO,
  quarterIndexFromISO,
  rangeForPeriod,
  selectableFortnightHalves,
  selectableMonthIndexes,
  selectableQuarterIndexes,
  selectableSemesterIndexes,
  selectableYears,
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

export default function App() {
  const maxDate = todayISO()
  const [devRole, setDevRoleState] = useState<AppRole>(() => getDevRole())
  const [tab, setTab] = useState<Tab>('cafeteria')
  const [health, setHealth] = useState<HealthResponse | null>(null)

  const [period, setPeriod] = useState<AttendancePeriod>('day')
  const initialRange = rangeForPeriod('day', maxDate)
  const [anchorDate, setAnchorDate] = useState(maxDate)
  const [fromDate, setFromDate] = useState(initialRange.from)
  const [toDate, setToDate] = useState(initialRange.to)
  const [cafeDate, setCafeDate] = useState(maxDate)

  const [attendance, setAttendance] = useState<AttendanceReport | null>(null)
  const [cafeteria, setCafeteria] = useState<CafeteriaReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<PreviewState>(PREVIEW_CLOSED)
  /** Se incrementa al entrar a una vista para forzar regeneración del listado. */
  const [listEntryKey, setListEntryKey] = useState(0)
  const [sites, setSites] = useState<SiteInfo[]>([])
  const [siteId, setSiteId] = useState<string>('')

  const years = useMemo(() => selectableYears(), [maxDate])
  const monthIndexes = useMemo(
    () => selectableMonthIndexes(yearFromISO(anchorDate)),
    [anchorDate],
  )
  const fortnightHalves = useMemo(
    () => selectableFortnightHalves(yearFromISO(anchorDate), monthIndexFromISO(anchorDate)),
    [anchorDate],
  )
  const quarterIndexes = useMemo(
    () => selectableQuarterIndexes(yearFromISO(anchorDate)),
    [anchorDate],
  )
  const semesterIndexes = useMemo(
    () => selectableSemesterIndexes(yearFromISO(anchorDate)),
    [anchorDate],
  )
  const attendanceRangeError = useMemo(
    () => validateDateRange(fromDate, toDate, maxDate),
    [fromDate, toDate, maxDate],
  )
  const cafeteriaDateError = useMemo(() => {
    if (cafeDate > maxDate) {
      return validateDateRange(cafeDate, cafeDate, maxDate)
    }
    return null
  }, [cafeDate, maxDate])

  function clampYear(year: number): number {
    return Math.min(year, maxSelectableYear())
  }

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
  }, [])

  // Si el rol local cambia, corregir pestaña activa
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

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const data = await fetchSites()
        if (cancelled) return
        setSites(data.sites)
        setSiteId((prev) => prev || data.current_site_id || data.sites[0]?.id || '')
      } catch {
        /* sede opcional en local */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  // Al entrar a cada vista: regenerar siempre. Si falla o no aplica, no queda listado previo.
  useEffect(() => {
    let cancelled = false

    async function regenerate() {
      if (tab === 'devices') {
        setAttendance(null)
        setCafeteria(null)
        setError(null)
        setLoading(false)
        return
      }

      setLoading(true)
      setError(null)
      setAttendance(null)
      setCafeteria(null)

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
    return () => {
      cancelled = true
    }
    // Al cambiar de vista, sede o al forzar regeneración
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, listEntryKey, siteId])

  useEffect(() => {
    return () => {
      if (preview.blobUrl) URL.revokeObjectURL(preview.blobUrl)
    }
  }, [preview.blobUrl])

  function clearListings() {
    setAttendance(null)
    setCafeteria(null)
    setError(null)
  }

  function applyPeriod(nextPeriod: AttendancePeriod, nextAnchor?: string) {
    // Sin ancla explícita → periodo actual (hoy)
    let anchor = clampToToday(nextAnchor ?? todayISO())
    if (yearFromISO(anchor) > maxSelectableYear()) {
      anchor = todayISO()
    }

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
      if (!months.includes(month)) {
        month = months[months.length - 1] ?? 0
      }
      let half = fortnightHalfFromISO(anchor)
      const halves = selectableFortnightHalves(year, month)
      if (!halves.includes(half)) {
        half = halves[halves.length - 1] ?? '1Q'
      }
      anchor = clampToToday(anchorForFortnight(year, month, half))
    }

    if (nextPeriod === 'quarter') {
      const year = yearFromISO(anchor)
      let quarter = quarterIndexFromISO(anchor)
      const allowed = selectableQuarterIndexes(year)
      if (!allowed.includes(quarter)) {
        quarter = (allowed[allowed.length - 1] ?? 0) as QuarterIndex
      }
      anchor = clampToToday(anchorForQuarter(year, quarter))
    }

    if (nextPeriod === 'semester') {
      const year = yearFromISO(anchor)
      let semester = semesterIndexFromISO(anchor)
      const allowed = selectableSemesterIndexes(year)
      if (!allowed.includes(semester)) {
        semester = (allowed[allowed.length - 1] ?? 0) as SemesterIndex
      }
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

  function selectPeriodMode(nextPeriod: AttendancePeriod) {
    // Siempre al periodo vigente según el día en curso
    applyPeriod(nextPeriod, todayISO())
  }

  async function loadAttendance() {
    setLoading(true)
    setError(null)
    setAttendance(null)
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
    setCafeteria(null)
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

  async function openPreview(
    title: string,
    filename: string,
    loader: () => Promise<Blob>,
  ) {
    if (preview.blobUrl) URL.revokeObjectURL(preview.blobUrl)
    setPreview({
      open: true,
      title,
      filename,
      blobUrl: null,
      loading: true,
      error: null,
    })
    try {
      const blob = await loader()
      const url = URL.createObjectURL(blob)
      setPreview({
        open: true,
        title,
        filename,
        blobUrl: url,
        loading: false,
        error: null,
      })
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
    if (next === 'cafeteria') {
      setCafeDate(todayISO())
    } else if (next === 'attendance') {
      selectPeriodMode(period)
    }
    setListEntryKey((k) => k + 1)
  }

  function onDevRoleChange(role: AppRole) {
    setDevRole(role)
    setDevRoleState(role)
    setTab(role === ROLE_SERVICIOS ? 'cafeteria' : 'cafeteria')
    setListEntryKey((k) => k + 1)
  }

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
          {health?.auth_disabled ? 'Auth local desactivada' : `API · ${health?.client_id ?? 'biometrico'}`}
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
            <h1 className="panel__title visually-hidden">Cierre diario de comedor</h1>

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
            {cafeteriaDateError && <p className="period-anchor-hint" role="alert">{cafeteriaDateError}</p>}
            {!canGenerateReports() && (
              <p className="period-anchor-hint">
                Listado de comedor (corte ≤ 09:00 e inclusiones ya autorizadas por GTH). Solo
                impresión PDF; sin gestión de excepciones.
              </p>
            )}

            <CafeteriaTable
              report={cafeteria}
              loading={loading}
              error={error}
              hideGthDetails={!canOperateGth()}
            />

            {cafeteria && !loading && canOperateGth() && (
              <GthExceptionPanel
                date={clampToToday(cafeDate)}
                onChanged={() => {
                  void loadCafeteria()
                }}
              />
            )}
          </section>
        ) : (
          <section className="glass panel">
            <h1 className="panel__title visually-hidden">Asistencia — primera y última marca</h1>

            <nav className="segmented segmented--periods" aria-label="Periodo de asistencia">
              {ATTENDANCE_PERIODS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`segmented__btn ${period === item.id ? 'is-active' : ''}`}
                  onClick={() => selectPeriodMode(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </nav>

            {(period === 'week' || period === 'quarter' || period === 'semester') && (
              <p className="period-anchor-hint">
                Rango: {formatDate(fromDate)} — {formatDate(toDate)}
              </p>
            )}

            <div className="controls">
              {period === 'month' && (
                <>
                  <div className="field">
                    <label htmlFor="month-select">Mes</label>
                    <select
                      id="month-select"
                      value={monthIndexFromISO(anchorDate)}
                      onChange={(e) => {
                        const monthIndex = Number(e.target.value)
                        applyPeriod('month', anchorForMonth(yearFromISO(anchorDate), monthIndex))
                      }}
                    >
                      {monthIndexes.map((index) => (
                        <option key={MONTH_NAMES[index]} value={index}>
                          {MONTH_NAMES[index]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="year-select">Año</label>
                    <select
                      id="year-select"
                      value={yearFromISO(anchorDate)}
                      onChange={(e) => {
                        const year = clampYear(Number(e.target.value))
                        const months = selectableMonthIndexes(year)
                        const preferred = monthIndexFromISO(anchorDate)
                        const month = months.includes(preferred)
                          ? preferred
                          : (months[months.length - 1] ?? 0)
                        applyPeriod('month', anchorForMonth(year, month))
                      }}
                    >
                      {years.map((year) => (
                        <option key={year} value={year}>
                          {year}
                        </option>
                      ))}
                    </select>
                  </div>
                </>
              )}

              {period === 'quarter' && (
                <>
                  <div className="field field--grow">
                    <label htmlFor="quarter-select">Trimestre</label>
                    <select
                      id="quarter-select"
                      value={quarterIndexFromISO(anchorDate)}
                      onChange={(e) => {
                        const quarter = Number(e.target.value) as QuarterIndex
                        applyPeriod('quarter', anchorForQuarter(yearFromISO(anchorDate), quarter))
                      }}
                    >
                      {quarterIndexes.map((index) => (
                        <option key={QUARTER_LABELS[index]} value={index}>
                          {QUARTER_LABELS[index]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="quarter-year">Año</label>
                    <select
                      id="quarter-year"
                      value={yearFromISO(anchorDate)}
                      onChange={(e) => {
                        const year = clampYear(Number(e.target.value))
                        const allowed = selectableQuarterIndexes(year)
                        const preferred = quarterIndexFromISO(anchorDate)
                        const quarter = (allowed.includes(preferred)
                          ? preferred
                          : (allowed[allowed.length - 1] ?? 0)) as QuarterIndex
                        applyPeriod('quarter', anchorForQuarter(year, quarter))
                      }}
                    >
                      {years.map((year) => (
                        <option key={year} value={year}>
                          {year}
                        </option>
                      ))}
                    </select>
                  </div>
                </>
              )}

              {period === 'semester' && (
                <>
                  <div className="field field--grow">
                    <label htmlFor="semester-select">Semestre</label>
                    <select
                      id="semester-select"
                      value={semesterIndexFromISO(anchorDate)}
                      onChange={(e) => {
                        const semester = Number(e.target.value) as SemesterIndex
                        applyPeriod(
                          'semester',
                          anchorForSemester(yearFromISO(anchorDate), semester),
                        )
                      }}
                    >
                      {semesterIndexes.map((index) => (
                        <option key={SEMESTER_LABELS[index]} value={index}>
                          {SEMESTER_LABELS[index]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="semester-year">Año</label>
                    <select
                      id="semester-year"
                      value={yearFromISO(anchorDate)}
                      onChange={(e) => {
                        const year = clampYear(Number(e.target.value))
                        const allowed = selectableSemesterIndexes(year)
                        const preferred = semesterIndexFromISO(anchorDate)
                        const semester = (allowed.includes(preferred)
                          ? preferred
                          : (allowed[allowed.length - 1] ?? 0)) as SemesterIndex
                        applyPeriod('semester', anchorForSemester(year, semester))
                      }}
                    >
                      {years.map((year) => (
                        <option key={year} value={year}>
                          {year}
                        </option>
                      ))}
                    </select>
                  </div>
                </>
              )}

              {period === 'fortnight' && (
                <>
                  <div className="field field--grow">
                    <label>Quincena</label>
                    <div className="segmented segmented--half" role="group" aria-label="1Q o 2Q">
                      {fortnightHalves.map((half) => (
                        <button
                          key={half}
                          type="button"
                          className={`segmented__btn ${fortnightHalfFromISO(anchorDate) === half ? 'is-active' : ''}`}
                          onClick={() =>
                            applyPeriod(
                              'fortnight',
                              anchorForFortnight(
                                yearFromISO(anchorDate),
                                monthIndexFromISO(anchorDate),
                                half,
                              ),
                            )
                          }
                        >
                          {half}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="field">
                    <label htmlFor="fortnight-month">Mes</label>
                    <select
                      id="fortnight-month"
                      value={monthIndexFromISO(anchorDate)}
                      onChange={(e) => {
                        const monthIndex = Number(e.target.value)
                        const halves = selectableFortnightHalves(
                          yearFromISO(anchorDate),
                          monthIndex,
                        )
                        const preferred = fortnightHalfFromISO(anchorDate)
                        const half = halves.includes(preferred)
                          ? preferred
                          : (halves[halves.length - 1] ?? '1Q')
                        applyPeriod(
                          'fortnight',
                          anchorForFortnight(yearFromISO(anchorDate), monthIndex, half),
                        )
                      }}
                    >
                      {monthIndexes.map((index) => (
                        <option key={MONTH_NAMES[index]} value={index}>
                          {MONTH_NAMES[index]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="fortnight-year">Año</label>
                    <select
                      id="fortnight-year"
                      value={yearFromISO(anchorDate)}
                      onChange={(e) => {
                        const year = clampYear(Number(e.target.value))
                        const months = selectableMonthIndexes(year)
                        const preferredMonth = monthIndexFromISO(anchorDate)
                        const month = months.includes(preferredMonth)
                          ? preferredMonth
                          : (months[months.length - 1] ?? 0)
                        const halves = selectableFortnightHalves(year, month)
                        const preferredHalf = fortnightHalfFromISO(anchorDate)
                        const half = halves.includes(preferredHalf)
                          ? preferredHalf
                          : (halves[halves.length - 1] ?? '1Q')
                        applyPeriod('fortnight', anchorForFortnight(year, month, half))
                      }}
                    >
                      {years.map((year) => (
                        <option key={year} value={year}>
                          {year}
                        </option>
                      ))}
                    </select>
                  </div>
                </>
              )}

              {(period === 'day' || period === 'week') && (
                <div className="field">
                  <label htmlFor="anchor-date">
                    {period === 'day' ? 'Fecha específica' : 'Semana (elige un día)'}
                  </label>
                  <input
                    id="anchor-date"
                    type="date"
                    max={maxDate}
                    value={anchorDate}
                    onChange={(e) => applyPeriod(period, e.target.value)}
                  />
                </div>
              )}

              {period === 'week' && (
                <>
                  <div className="field">
                    <label htmlFor="from-date">Desde</label>
                    <input
                      id="from-date"
                      type="date"
                      value={fromDate}
                      readOnly
                      disabled
                      title="Se calcula automáticamente según la semana"
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="to-date">Hasta</label>
                    <input
                      id="to-date"
                      type="date"
                      value={toDate}
                      readOnly
                      disabled
                      title="Hasta hoy si la semana aún no termina"
                    />
                  </div>
                </>
              )}

              <div className="actions">
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
            </div>
            {attendanceRangeError && (
              <p className="period-anchor-hint" role="alert">
                {attendanceRangeError}
              </p>
            )}

            <AttendanceTable report={attendance} loading={loading} error={error} />
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
