import { useEffect, useMemo, useState } from 'react'
import type { AttendanceReport } from '../api'
import { formatDate, formatTime } from '../api'
import {
  exitLabel,
  formatDelay,
  getAttendanceFlags,
  rowToneClass,
} from '../attendanceFlags'
import { downloadCSV } from '../csvExport'
import { formatEmployeeName } from '../formatEmployeeName'
import { todayISO } from '../periodRange'
import { usePageSize } from '../usePageSize'
import { PaginationBar } from './PaginationBar'

type Props = {
  report: AttendanceReport | null
  loading: boolean
  error: string | null
}

export function AttendanceTable({ report, loading, error }: Props) {
  const pageSize = usePageSize(25, 10)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')

  // Resetear búsqueda y página al cargar un nuevo reporte
  useEffect(() => {
    setPage(1)
    setSearch('')
  }, [report?.from_date, report?.to_date])

  // Resetear página al cambiar búsqueda o tamaño
  useEffect(() => {
    setPage(1)
  }, [search, pageSize])

  const summary = useMemo(() => {
    if (!report) return { late: 0, missingExit: 0 }
    const today = todayISO()
    let late = 0
    let missingExit = 0
    for (const row of report.rows) {
      const flags = getAttendanceFlags(row.first_seen_at, row.last_seen_at, row.date, today)
      if (flags.isLate) late += 1
      if (flags.missingExit) missingExit += 1
    }
    return { late, missingExit }
  }, [report])

  /** Filas filtradas por búsqueda local */
  const filtered = useMemo(() => {
    if (!report) return []
    if (!search.trim()) return report.rows
    const q = search.toLowerCase().trim()
    return report.rows.filter(
      (row) =>
        formatEmployeeName(row.employee_name).toLowerCase().includes(q) ||
        row.employee_id.toLowerCase().includes(q) ||
        (row.department?.toLowerCase() ?? '').includes(q),
    )
  }, [report, search])

  function handleCSV() {
    if (!report) return
    downloadCSV(
      `asistencia_${report.from_date}_${report.to_date}.csv`,
      ['#', 'Fecha', 'Empleado', 'ID', 'Departamento', 'Entrada', 'Demora (min)', 'Salida'],
      filtered.map((row, i) => {
        const flags = getAttendanceFlags(row.first_seen_at, row.last_seen_at, row.date)
        return [
          i + 1,
          row.date,
          formatEmployeeName(row.employee_name),
          row.employee_id,
          row.department || '',
          formatTime(row.first_seen_at),
          flags.delayMinutes ?? '',
          row.last_seen_at
            ? formatTime(row.last_seen_at)
            : flags.missingExit
              ? 'Sin marca'
              : flags.dayInProgress
                ? 'Día en curso'
                : '',
        ]
      }),
    )
  }

  if (loading) {
    return (
      <div className="loading">
        <span className="spinner" />
        Generando asistencia…
      </div>
    )
  }

  if (error) {
    return (
      <div className="error" role="alert">
        {error}
      </div>
    )
  }

  if (!report) {
    return <div className="empty">Sin listado. Entra a la vista o pulsa Generar.</div>
  }

  if (report.rows.length === 0) {
    return <div className="empty">Sin marcas en el periodo indicado.</div>
  }

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const start = (safePage - 1) * pageSize
  const slice = filtered.slice(start, start + pageSize)

  return (
    <>
      <div className="stats">
        <div className="stat">
          <span className="stat__label">Total</span>
          <span className="stat__value">{report.rows.length}</span>
        </div>
        <div className="stat">
          <span className="stat__label">Desde</span>
          <span className="stat__value" style={{ fontSize: '1.1rem' }}>
            {formatDate(report.from_date)}
          </span>
        </div>
        <div className="stat">
          <span className="stat__label">Hasta</span>
          <span className="stat__value" style={{ fontSize: '1.1rem' }}>
            {formatDate(report.to_date)}
          </span>
        </div>
        <div className="stat">
          <span className="stat__label">Tarde (&gt;9:00)</span>
          <span className="stat__value stat__value--soft-late">{summary.late}</span>
        </div>
        {summary.missingExit > 0 && (
          <div className="stat">
            <span className="stat__label">Sin salida</span>
            <span className="stat__value stat__value--soft-warn">{summary.missingExit}</span>
          </div>
        )}
      </div>

      {/* Barra de búsqueda + CSV */}
      <div className="table-toolbar">
        <input
          className="table-search"
          type="search"
          placeholder="Buscar nombre, cédula, departamento…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Filtrar registros de asistencia"
        />
        <div className="table-toolbar__right">
          {search.trim() !== '' && (
            <span className="table-toolbar__count" aria-live="polite">
              {filtered.length} de {report.rows.length}
            </span>
          )}
          <button
            type="button"
            className="btn btn--ghost btn--page"
            onClick={handleCSV}
            title="Exportar registros visibles a CSV"
          >
            CSV ↓
          </button>
        </div>
      </div>

      <p className="attendance-legend" aria-hidden>
        <span className="legend-swatch legend-swatch--late" /> Tarde (después de 09:00)
        <span className="legend-swatch legend-swatch--warn" /> Sin marca de salida
        <span className="legend-swatch legend-swatch--both" /> Tarde + sin marca
      </p>

      <div className="table-wrap">
        <table className="data-table data-table--attendance">
          <thead>
            <tr>
              <th>#</th>
              <th>Fecha</th>
              <th>Empleado</th>
              <th className="col-hide-md">Departamento</th>
              <th>Entrada</th>
              <th>Demora</th>
              <th>Salida</th>
            </tr>
          </thead>
          <tbody>
            {slice.map((row, i) => {
              const flags = getAttendanceFlags(row.first_seen_at, row.last_seen_at, row.date)
              const tone = rowToneClass(flags)
              const salida = exitLabel(flags, row.last_seen_at, formatTime)
              return (
                <tr
                  key={`${row.date}-${row.employee_id}-${i}`}
                  className={tone}
                  style={{ animationDelay: `${i * 12}ms` }}
                >
                  <td>
                    <span className="order-badge">{start + i + 1}</span>
                  </td>
                  <td>{formatDate(row.date)}</td>
                  <td>{formatEmployeeName(row.employee_name)}</td>
                  <td className="col-hide-md">{row.department || '—'}</td>
                  <td>{formatTime(row.first_seen_at)}</td>
                  <td>
                    <span className={flags.isLate ? 'delay-pill delay-pill--late' : 'delay-pill'}>
                      {formatDelay(flags.delayMinutes)}
                    </span>
                  </td>
                  <td>
                    <span
                      className={
                        flags.missingExit
                          ? 'exit-pill exit-pill--warn'
                          : flags.dayInProgress
                            ? 'exit-pill exit-pill--progress'
                            : undefined
                      }
                    >
                      {salida}
                    </span>
                  </td>
                </tr>
              )
            })}
            {slice.length === 0 && (
              <tr>
                <td colSpan={7} className="empty">
                  Sin resultados para &ldquo;{search}&rdquo;
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <PaginationBar
        page={safePage}
        pageSize={pageSize}
        total={filtered.length}
        onChange={setPage}
      />
    </>
  )
}
