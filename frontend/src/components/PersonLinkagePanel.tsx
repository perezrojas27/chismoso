import { useCallback, useEffect, useState } from 'react'
import {
  fetchBioLinkageActive,
  fetchBioPersonsUnlinked,
  fetchPresenceReport,
  linkBioPerson,
  unlinkBioPerson,
  type BioLinkageItem,
  type BioPersonUnlinked,
  type PresenceReport,
} from '../api'
import { todayISO } from '../periodRange'
import { useDebounce } from '../useDebounce'

type Props = {
  biometricSiteId?: string
}

export function PersonLinkagePanel({ biometricSiteId }: Props) {
  const [q, setQ] = useState('')
  const debouncedQ = useDebounce(q, 350)
  const [filter, setFilter] = useState<'all' | 'linked' | 'unlinked'>('unlinked')

  const [items, setItems] = useState<BioLinkageItem[]>([])
  const [stats, setStats] = useState({ active: 0, linked: 0, unlinked: 0 })
  const [persons, setPersons] = useState<BioPersonUnlinked[]>([])

  // Empleado GTH seleccionado y persona biométrica a vincular
  const [selectedEmp, setSelectedEmp] = useState('')
  const [selectedPerson, setSelectedPerson] = useState('')
  const [manualPersonId, setManualPersonId] = useState('')

  // Presencia
  const [presenceDate, setPresenceDate] = useState(() => todayISO())
  const [coreSiteId, setCoreSiteId] = useState('')
  const [presence, setPresence] = useState<PresenceReport | null>(null)

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  // Usa debouncedQ para no disparar 2 requests por cada pulsación
  const refresh = useCallback(async () => {
    setError(null)
    const [emp, pers] = await Promise.all([
      fetchBioLinkageActive({
        q: debouncedQ || undefined,
        link_filter: filter,
      }),
      fetchBioPersonsUnlinked({
        q: debouncedQ || undefined,
        site_id: biometricSiteId || undefined,
      }),
    ])
    setItems(emp.items)
    setStats(emp.stats)
    setPersons(pers.items)
    setSelectedEmp((prev) => {
      if (prev && emp.items.some((i) => i.employee_id === prev)) return prev
      const firstUnlinked = emp.items.find((i) => !i.linked)
      return (firstUnlinked || emp.items[0])?.employee_id || ''
    })
  }, [debouncedQ, filter, biometricSiteId])

  useEffect(() => {
    void refresh().catch((err: unknown) => {
      setError(err instanceof Error ? err.message : 'Error al cargar vínculos')
    })
  }, [refresh])

  async function handleLink() {
    const personId = manualPersonId.trim() || selectedPerson
    if (!selectedEmp || !personId) {
      setError('Elija un empleado GTH y seleccione o escriba un ID biométrico')
      return
    }
    setBusy(true)
    setError(null)
    setMsg(null)
    try {
      await linkBioPerson(selectedEmp, personId)
      setMsg('Vínculo guardado correctamente')
      setSelectedPerson('')
      setManualPersonId('')
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo vincular')
    } finally {
      setBusy(false)
    }
  }

  async function handleUnlink(employeeId: string) {
    setBusy(true)
    setError(null)
    setMsg(null)
    try {
      await unlinkBioPerson(employeeId)
      setMsg('Vínculo eliminado')
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo desvincular')
    } finally {
      setBusy(false)
    }
  }

  async function handlePresence() {
    if (!coreSiteId.trim()) {
      setError('Indique el UUID de sede GTH (core.sites) para el reporte de presencia')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const rep = await fetchPresenceReport({
        date: presenceDate,
        core_site_id: coreSiteId.trim(),
        biometric_site_id: biometricSiteId || undefined,
      })
      setPresence(rep)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo calcular presencia')
      setPresence(null)
    } finally {
      setBusy(false)
    }
  }

  const selectedEmpData = items.find((i) => i.employee_id === selectedEmp)
  const effectivePerson = manualPersonId.trim() || selectedPerson

  return (
    <section className="glass panel">
      <h2 className="panel__title">Vínculo GTH ↔ biométrico</h2>
      <p style={{ fontSize: '0.85rem', color: 'var(--ink-soft)', marginBottom: '1.25rem' }}>
        El reloj identifica personas con <code>employeeNo</code> (ID propio). Para saber quién
        faltó por marcar en una sede hay que vincular ese ID con el empleado de GTH (cédula /
        ficha), igual que la vinculación de correo corporativo.
      </p>

      {/* ── Controles de búsqueda ── */}
      <div className="controls">
        <div className="field">
          <label htmlFor="bio-link-q">Buscar</label>
          <input
            id="bio-link-q"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Cédula o nombre…"
          />
        </div>
        <div className="field">
          <label htmlFor="bio-link-filter">Filtro</label>
          <select
            id="bio-link-filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value as typeof filter)}
          >
            <option value="all">Todos</option>
            <option value="unlinked">Sin vínculo</option>
            <option value="linked">Vinculados</option>
          </select>
        </div>
        <div className="actions">
          <button
            type="button"
            className="btn btn--ghost"
            disabled={busy}
            onClick={() => void refresh()}
          >
            Actualizar
          </button>
        </div>
      </div>

      {/* ── Estadísticas ── */}
      <div className="stats">
        <div className="stat">
          <span className="stat__label">Activos GTH</span>
          <span className="stat__value">{stats.active}</span>
        </div>
        <div className="stat">
          <span className="stat__label">Vinculados</span>
          <span className="stat__value stat__value--soft-ok">{stats.linked}</span>
        </div>
        <div className="stat">
          <span className="stat__label">Sin vínculo</span>
          <span className="stat__value stat__value--soft-warn">{stats.unlinked}</span>
        </div>
      </div>

      {error && (
        <div className="error" role="alert" style={{ marginBottom: '12px' }}>
          {error}
        </div>
      )}
      {msg && (
        <p
          className="period-anchor-hint"
          role="status"
          style={{ marginBottom: '12px', color: 'var(--accent)' }}
        >
          {msg}
        </p>
      )}

      {/* ── Tablas de vinculación ── */}
      <div className="linkage-grid">
        {/* Columna izquierda: Empleados GTH */}
        <div className="linkage-col">
          <p className="linkage-col__heading">Empleados GTH</p>
          <div className="table-wrap linkage-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Cédula</th>
                  <th>Nombre</th>
                  <th>Estado / Bio ID</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => (
                  <tr
                    key={it.employee_id}
                    className={`${it.linked ? 'row-tone--exception' : ''} ${
                      selectedEmp === it.employee_id ? 'row--selected' : ''
                    }`}
                    style={{ cursor: 'pointer' }}
                    onClick={() => setSelectedEmp(it.employee_id)}
                    title={it.linked ? `Vinculado → ${it.person_external_id ?? ''}` : 'Sin vínculo'}
                  >
                    <td style={{ fontVariantNumeric: 'tabular-nums' }}>{it.cedula}</td>
                    <td>{it.full_name}</td>
                    <td>
                      {it.linked ? (
                        <span className="linkage-badge linkage-badge--ok">
                          {it.person_external_id}
                        </span>
                      ) : (
                        <span className="linkage-badge linkage-badge--warn">Sin vínculo</span>
                      )}
                    </td>
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={3} className="empty">
                      Sin resultados
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {selectedEmpData?.linked && (
            <button
              type="button"
              className="btn btn--ghost btn--page"
              style={{ marginTop: '8px', width: '100%' }}
              disabled={busy}
              onClick={() => void handleUnlink(selectedEmp)}
            >
              Desvincular seleccionado
            </button>
          )}
        </div>

        {/* Columna derecha: IDs biométricos sin vínculo */}
        <div className="linkage-col">
          <p className="linkage-col__heading">IDs biométricos sin vínculo</p>
          <div className="table-wrap linkage-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>EmployeeNo</th>
                  <th>Nombre en reloj</th>
                  <th style={{ textAlign: 'right' }}>Eventos</th>
                </tr>
              </thead>
              <tbody>
                {persons.map((p) => (
                  <tr
                    key={p.person_external_id}
                    className={
                      selectedPerson === p.person_external_id ? 'row--selected' : undefined
                    }
                    style={{ cursor: 'pointer' }}
                    onClick={() => {
                      setSelectedPerson(p.person_external_id)
                      setManualPersonId('')
                    }}
                  >
                    <td style={{ fontVariantNumeric: 'tabular-nums' }}>
                      {p.person_external_id}
                    </td>
                    <td>
                      {p.person_name || (
                        <em style={{ color: 'var(--ink-soft)' }}>sin nombre</em>
                      )}
                    </td>
                    <td style={{ textAlign: 'right' }}>{p.event_count}</td>
                  </tr>
                ))}
                {persons.length === 0 && (
                  <tr>
                    <td colSpan={3} className="empty">
                      Sin IDs biométricos pendientes
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="field" style={{ marginTop: '10px' }}>
            <label htmlFor="bio-manual-id">O escribir EmployeeNo manualmente</label>
            <input
              id="bio-manual-id"
              value={manualPersonId}
              onChange={(e) => {
                setManualPersonId(e.target.value)
                if (e.target.value) setSelectedPerson('')
              }}
              placeholder="ID del reloj"
            />
          </div>
        </div>
      </div>

      {/* ── Barra de acción de vínculo ── */}
      <div className="linkage-action">
        <span className="linkage-action__info">
          <strong>
            {selectedEmpData
              ? `${selectedEmpData.cedula} — ${selectedEmpData.full_name}`
              : 'Ningún empleado GTH seleccionado'}
          </strong>
          {' → '}
          <span style={{ color: effectivePerson ? 'var(--accent)' : 'var(--ink-soft)' }}>
            {effectivePerson || '— ID biométrico —'}
          </span>
        </span>
        <button
          type="button"
          className="btn btn--primary"
          disabled={busy || !selectedEmp || !effectivePerson}
          onClick={() => void handleLink()}
        >
          Vincular
        </button>
      </div>

      <hr className="linkage-divider" />

      {/* ── Sección de Presencia ── */}
      <h3 className="linkage-section-title">Presencia por sede GTH</h3>
      <p style={{ fontSize: '0.8rem', color: 'var(--ink-soft)', marginBottom: '1rem' }}>
        Compara empleados activos de <code>hr.employees.site_id</code> con marcajes del día.
        Requiere vínculos configurados y, idealmente, fila en{' '}
        <code>biometrico.site_map</code> (sede edge ↔ core.sites).
      </p>

      <div className="controls">
        <div className="field">
          <label htmlFor="presence-date">Fecha</label>
          <input
            id="presence-date"
            type="date"
            value={presenceDate}
            onChange={(e) => setPresenceDate(e.target.value)}
          />
        </div>
        <div className="field" style={{ minWidth: '280px' }}>
          <label htmlFor="core-site">UUID sede GTH (core.sites)</label>
          <input
            id="core-site"
            value={coreSiteId}
            onChange={(e) => setCoreSiteId(e.target.value)}
            placeholder="uuid de la sede"
          />
        </div>
        <div className="actions">
          <button
            type="button"
            className="btn btn--primary"
            disabled={busy}
            onClick={() => void handlePresence()}
          >
            Calcular
          </button>
        </div>
      </div>

      {presence && (
        <>
          {/* Stats de presencia */}
          <div className="stats">
            <div className="stat">
              <span className="stat__label">Presentes</span>
              <span className="stat__value stat__value--soft-ok">{presence.counts.present}</span>
            </div>
            <div className="stat">
              <span className="stat__label">Ausentes</span>
              <span className="stat__value stat__value--soft-late">{presence.counts.absent}</span>
            </div>
            <div className="stat">
              <span className="stat__label">Sin vínculo</span>
              <span className="stat__value stat__value--soft-warn">
                {presence.counts.unlinked}
              </span>
            </div>
          </div>

          {presence.site_map_missing && (
            <div
              className="error"
              role="alert"
              style={{ fontSize: '0.85rem', marginBottom: '12px' }}
            >
              Sin mapa de sede: se usaron marcajes de todas las sedes del día (menos preciso).
            </div>
          )}

          {presence.absent.length > 0 && (
            <>
              <p className="linkage-section-subtitle">No marcaron ({presence.absent.length})</p>
              <div className="table-wrap" style={{ marginBottom: '14px' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Cédula</th>
                      <th>Nombre</th>
                      <th>ID Biométrico</th>
                    </tr>
                  </thead>
                  <tbody>
                    {presence.absent.map((a) => (
                      <tr key={a.employee_id} className="row-tone--late">
                        <td style={{ fontVariantNumeric: 'tabular-nums' }}>{a.cedula}</td>
                        <td>{a.full_name}</td>
                        <td style={{ color: 'var(--ink-soft)' }}>
                          {a.person_external_id || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {presence.unlinked_employees.length > 0 && (
            <>
              <p className="linkage-section-subtitle">
                Activos sin vínculo ({presence.unlinked_employees.length}
                {presence.unlinked_employees.length > 30 ? ', mostrando 30' : ''})
              </p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Cédula</th>
                      <th>Nombre</th>
                    </tr>
                  </thead>
                  <tbody>
                    {presence.unlinked_employees.slice(0, 30).map((a) => (
                      <tr key={a.employee_id} className="row-tone--missing-exit">
                        <td style={{ fontVariantNumeric: 'tabular-nums' }}>{a.cedula}</td>
                        <td>{a.full_name}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </section>
  )
}
