import { useEffect, useState } from 'react'
import type { CafeteriaReport } from '../api'
import { formatDate } from '../api'
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

  useEffect(() => {
    setPage(1)
  }, [report?.date, report?.employees.length, pageSize])

  if (loading) {
    return (
      <div className="loading">
        <span className="spinner" />
        Cerrando comedor…
      </div>
    )
  }

  if (error) {
    return <div className="error">{error}</div>
  }

  if (!report) {
    return <div className="empty">Sin listado. Entra a la vista o pulsa Generar.</div>
  }

  if (report.employees.length === 0) {
    return <div className="empty">Nadie marcó antes del corte {report.cutoff}.</div>
  }

  const totalPages = Math.max(1, Math.ceil(report.employees.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const start = (safePage - 1) * pageSize
  const slice = report.employees.slice(start, start + pageSize)
  const excCount = report.exceptions_count ?? report.employees.filter((e) => e.has_exception).length

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
                {!hideGthDetails && (
                  <td className="obs-cell">{emp.observation || '—'}</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <PaginationBar
        page={safePage}
        pageSize={pageSize}
        total={report.employees.length}
        onChange={setPage}
      />
    </>
  )
}
