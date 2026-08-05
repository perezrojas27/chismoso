import { useEffect, useState } from 'react'
import {
  createCafeteriaException,
  deleteCafeteriaException,
  fetchCafeteriaExceptions,
  fetchLateCandidates,
  formatTime,
  type CafeteriaException,
  type LateCandidate,
} from '../api'

type Props = {
  date: string
  onChanged: () => void
}

/**
 * Panel GTH: registrar permiso de llegada tarde para incluir en comedor.
 */
export function GthExceptionPanel({ date, onChanged }: Props) {
  const [candidates, setCandidates] = useState<LateCandidate[]>([])
  const [exceptions, setExceptions] = useState<CafeteriaException[]>([])
  const [employeeId, setEmployeeId] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    try {
      setError(null)
      const [cands, excs] = await Promise.all([
        fetchLateCandidates(date),
        fetchCafeteriaExceptions(date),
      ])
      setCandidates(cands)
      setExceptions(excs)
      if (!cands.some((c) => c.employee_id === employeeId)) {
        setEmployeeId(cands.find((c) => !c.has_exception)?.employee_id ?? '')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudieron cargar excepciones')
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date])

  async function handleRegister() {
    if (!employeeId || !reason.trim()) {
      setError('Selecciona empleado y escribe el motivo del permiso')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await createCafeteriaException({
        employee_id: employeeId,
        date,
        reason: reason.trim(),
      })
      setReason('')
      await refresh()
      onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo registrar el permiso')
    } finally {
      setBusy(false)
    }
  }

  async function handleRemove(empId: string) {
    setBusy(true)
    setError(null)
    try {
      await deleteCafeteriaException(date, empId)
      await refresh()
      onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo quitar el permiso')
    } finally {
      setBusy(false)
    }
  }

  const pending = candidates.filter((c) => !c.has_exception)

  return (
    <section className="gth-panel" aria-label="Excepciones GTH comedor">
      <div className="gth-panel__head">
        <h2 className="gth-panel__title">Permisos GTH · comedor</h2>
        <p className="gth-panel__meta">
          Personas cuya primera marca fue después de las 09:00 y hasta las 11:00.
          Al registrar el permiso se anexan al listado de comedor; el PDF solo muestra
          quienes ya están incluidos.
        </p>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="gth-panel__form">
        <div className="field field--grow">
          <label htmlFor="gth-emp">Empleado (llegó tarde)</label>
          <select
            id="gth-emp"
            value={employeeId}
            onChange={(e) => setEmployeeId(e.target.value)}
            disabled={busy || pending.length === 0}
          >
            {pending.length === 0 ? (
              <option value="">Sin candidatos pendientes</option>
            ) : (
              pending.map((c) => (
                <option key={c.employee_id} value={c.employee_id}>
                  {c.employee_name} · {formatTime(c.marked_time)}
                </option>
              ))
            )}
          </select>
        </div>
        <div className="field field--grow">
          <label htmlFor="gth-reason">Motivo del permiso</label>
          <input
            id="gth-reason"
            type="text"
            maxLength={200}
            placeholder="Ej. cita médica, gestión bancaria…"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={busy}
          />
        </div>
        <div className="actions">
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => void handleRegister()}
            disabled={busy || pending.length === 0}
          >
            Registrar permiso
          </button>
        </div>
      </div>

      {exceptions.length > 0 && (
        <ul className="gth-panel__list">
          {exceptions.map((ex) => {
            const cand = candidates.find((c) => c.employee_id === ex.employee_id)
            return (
              <li key={`${ex.date}-${ex.employee_id}`} className="gth-panel__item">
                <div>
                  <strong>{cand?.employee_name ?? ex.employee_id}</strong>
                  <span className="gth-panel__reason">{ex.reason}</span>
                </div>
                <button
                  type="button"
                  className="btn btn--ghost btn--page"
                  disabled={busy}
                  onClick={() => void handleRemove(ex.employee_id)}
                >
                  Quitar
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
