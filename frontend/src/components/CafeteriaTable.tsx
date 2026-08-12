import { useEffect, useMemo, useState } from 'react'
import type { CafeteriaReport } from '../api'
import { formatDate } from '../api'
import { downloadCSV } from '../csvExport'
import { formatEmployeeName } from '../formatEmployeeName'
import { usePageSize } from '../usePageSize'
import { PaginationBar } from './PaginationBar'

type Props = {
  report: CafeteriaReport | null
  loading: boolean
  error: string | null
  /** Servicios generales: listado limpio sin marcas/obs de excepciones GTH */
  hideGthDetails?: boolean
}

/**
 * Lista de comedor por orden de llegada.
 * Filas verdes = permiso GTH (llegada después del corte), salvo hideGthDetails.
 */
export function CafeteriaTable({ report, loading, error, hideGthDetails = false }: Props) {
  const pageSize = usePageSize(25, 10)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')

  useEffect(() => {
    setPage(1)
    setSearch('')
  }, [report?.date])

  useEffect(() => {
    setPage(1)
  }, [search, pageSize])

  /** Filas filtradas por búsqueda local */
  const filtered = useMemo(() => {
    if (!report) return []
    if (!search.trim()) return report.employees
    const q = search.toLowerCase().trim()
    return report.employees.filter(
      (emp) =>
        formatEmployeeName(emp.employee_name).toLowerCase().includes(q) ||
        emp.employee_id.toLowerCase().includes(q) ||
        (emp.department?.toLowerCase() ?? '').includes(q),
    )
  }, [report, search])

  function handleCSV() {
    if (!report) return
    const cols = hideGthDetails
      ? (['#', 'Empleado', 'ID', 'Departamento'] as string[])
      : (['#', 'Empleado', 'ID', 'Departamento', 'Hora marca', 'Observación'] as string[])

    downloadCSV(
      `comedor_${report.date}.csv`,
      cols,
      filtered.map((emp, i) =>
        hideGthDetails
          ? [i + 1, formatEmployeeName(emp.employee_name), emp.employee_id, emp.department || '']
          : [
              i + 1,
              formatEmployeeName(emp.employee_name),
              emp.employee_id,
              emp.department || '',
              emp.marked_time || '',
              emp.observation || '',
            ],
      ),
    )
  }

  if (loading) {
    return (
      <div className="loading">
        <span className="spinner" />
        Cerrando comedor…
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

  if (report.employees.length === 0) {
    return <div className="empty">Nadie marcó antes del corte {report.cutoff}.</div>
  }

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const start = (safePage - 1) * pageSize
  const slice = filtered.slice(start, start + pageSize)
  const excCount =
    report.exceptions_count ?? report.employees.filter((e) => e.has_exception).length

  return (
    <>
      <div className="stats">
        <div className="stat">
          <span className="stat__label">Total</span>
          <span className="stat__value">{report.headcount}</span>
        </div>
        <div className="stat">
          <span className="stat__label">Fecha</span>
          <span className="stat__value" style={{ fontSize: '1.1rem' }}>
            {formatDate(report.date)}
          </span>
        </div>
        <div className="stat">
          <span className="stat__label">Corte</span>
          <span className="stat__value" style={{ fontSize: '1.1rem' }}>
            ≤ {report.cutoff}
          </span>
        </div>
        {!hideGthDetails && (
          <div className="stat">
            <span className="stat__label">Excepciones GTH</span>
            <span className="stat__value stat__value--soft-ok">{excCount}</span>
          </div>
        )}
      </div>

      {!hideGthDetails && (
        <p className="attendance-legend" aria-hidden>
          <span className="legend-swatch legend-swatch--ok" /> Permiso GTH (llegada después de{' '}
          {report.cutoff.slice(0, 5)})
        </p>
      )}

      {/* Barra de búsqueda + CSV */}
      <div className="table-toolbar">
        <input
          className="table-search"
          type="search"
          placeholder="Buscar nombre, cédula, departamento…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Filtrar listado de comedor"
        />
        <div className="table-toolbar__right">
          {search.trim() !== '' && (
            <span className="table-toolbar__count" aria-live="polite">
              {filtered.length} de {report.employees.length}
            </span>
          )}
          <button
            type="button"
            className="btn btn--ghost btn--page"
            onClick={handleCSV}
            title="Exportar listado visible a CSV"
          >
            CSV ↓
          </button>
        </div>
      </div>

      <div className="table-wrap">
        <table className="data-table data-table--cafeteria">
          <thead>
            <tr>
              <th>#</th>
              <th>Empleado</th>
              <th className="col-hide-md">Departamento</th>
              {!hideGthDetails && <th>Observaciones</th>}
            </tr>
          </thead>
          <tbody>
            {slice.map((emp, i) => (
              <tr
                key={emp.employee_id}
                className={
                  !hideGthDetails && emp.has_exception ? 'row-tone--exception' : undefined
                }
                style={{ animationDelay: `${i * 12}ms` }}
              >
                <td>
                  <span className="order-badge">{start + i + 1}</span>
                </td>
                <td>{formatEmployeeName(emp.employee_name)}</td>
                <td className="col-hide-md">{emp.department || '—'}</td>
                {!hideGthDetails && <td className="obs-cell">{emp.observation || '—'}</td>}
              </tr>
            ))}
            {slice.length === 0 && (
              <tr>
                <td colSpan={hideGthDetails ? 3 : 4} className="empty">
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
