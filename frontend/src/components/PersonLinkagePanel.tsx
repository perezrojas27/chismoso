import { useCallback, useEffect, useState } from 'react'
import {
  fetchBioLinkageActive,
  fetchBioPersonsUnlinked,
  fetchCatalogSites,
  fetchPresenceReport,
  linkBioPerson,
  unlinkBioPerson,
  type BioLinkageItem,
  type BioPersonUnlinked,
  type CatalogSite,
  type PresenceReport,
} from '../api'
import { todayISO } from '../periodRange'
import { useDebounce } from '../useDebounce'

type Props = {
  biometricSiteId?: string
}

export function PersonLinkagePanel({ biometricSiteId }: Props) {
  const [qEmp, setQEmp] = useState('')
  const [qBio, setQBio] = useState('')
  const debouncedQEmp = useDebounce(qEmp, 350)
  const debouncedQBio = useDebounce(qBio, 350)
  const [filter, setFilter] = useState<'all' | 'linked' | 'unlinked'>('unlinked')

  const [items, setItems] = useState<BioLinkageItem[]>([])
  const [stats, setStats] = useState({ active: 0, linked: 0, unlinked: 0 })
  const [persons, setPersons] = useState<BioPersonUnlinked[]>([])

  const [selectedEmp, setSelectedEmp] = useState('')
  const [selectedPerson, setSelectedPerson] = useState('')
  const [manualPersonId, setManualPersonId] = useState('')
  const [confirmOpen, setConfirmOpen] = useState(false)

  const [presenceDate, setPresenceDate] = useState(() => todayISO())
  const [coreSiteId, setCoreSiteId] = useState('')
  const [sites, setSites] = useState<CatalogSite[]>([])
  const [presence, setPresence] = useState<PresenceReport | null>(null)

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    const [emp, pers] = await Promise.all([
      fetchBioLinkageActive({
        q: debouncedQEmp || undefined,
        link_filter: filter,
      }),
      fetchBioPersonsUnlinked({
        q: debouncedQBio || undefined,
        site_id: biometricSiteId || undefined,
      }),
    ])
    setItems(emp.items)
    setStats(emp.stats)
    setPersons(pers.items)
    setSelectedEmp((prev) =>
      prev && emp.items.some((i) => i.employee_id === prev) ? prev : '',
    )
    setSelectedPerson((prev) =>
      prev && pers.items.some((p) => p.person_external_id === prev) ? prev : '',
    )
  }, [debouncedQEmp, debouncedQBio, filter, biometricSiteId])

  useEffect(() => {
    void refresh().catch((err: unknown) => {
      setError(err instanceof Error ? err.message : 'Error al cargar vínculos')
    })
  }, [refresh])

  useEffect(() => {
    void fetchCatalogSites()
      .then(setSites)
      .catch(() => setSites([]))
  }, [])

  const selectedEmpData = items.find((i) => i.employee_id === selectedEmp)
  const selectedPersonData = persons.find((p) => p.person_external_id === selectedPerson)
  const effectivePerson = manualPersonId.trim() || selectedPerson
  const personLabel =
    manualPersonId.trim() ||
    (selectedPersonData
      ? `${selectedPersonData.person_external_id}${
          selectedPersonData.person_name ? ` — ${selectedPersonData.person_name}` : ''
        }`
      : effectivePerson)

  async function handleLinkConfirmed() {
    if (!selectedEmp || !effectivePerson) {
      setError('Elija un empleado GTH y un ID biométrico')
      return
    }
    setBusy(true)
    setError(null)
    setMsg(null)
    try {
      await linkBioPerson(selectedEmp, effectivePerson)
      setMsg('Vínculo guardado correctamente')
      setSelectedPerson('')
      setManualPersonId('')
      setConfirmOpen(false)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo vincular')
    } finally {
      setBusy(false)
    }
  }

  async function handleUnlink(employeeId: string) {
    const row = items.find((i) => i.employee_id === employeeId)
    const ok = window.confirm(
      row
        ? `¿Desvincular a ${row.full_name} (${row.cedula}) del ID ${row.person_external_id}?`
        : '¿Desvincular el empleado seleccionado?',
    )
    if (!ok) return
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
      setError('Seleccione la sede GTH para el reporte de presencia')
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

  const step =
    !selectedEmp ? 1 : !effectivePerson ? 2 : confirmOpen ? 3 : 2

  return (
    <section className="glass panel">
      <h2 className="panel__title">Vínculo GTH ↔ biométrico</h2>
      <p style={{ fontSize: '0.85rem', color: 'var(--ink-soft)', marginBottom: '1rem' }}>
        El reloj identifica personas con <code>employeeNo</code> (ID propio). Vincule ese ID con
        la ficha GTH (cédula), en tres pasos: elegir empleado → elegir ID → confirmar.
      </p>

      <ol
        className="linkage-steps"
        style={{
          display: 'flex',
          gap: '0.75rem',
          listStyle: 'none',
          padding: 0,
          margin: '0 0 1rem',
          fontSize: '0.8rem',
          flexWrap: 'wrap',
        }}
      >
        {[
          { n: 1, label: 'Empleado GTH' },
          { n: 2, label: 'ID biométrico' },
          { n: 3, label: 'Confirmar' },
        ].map((s) => (
          <li
            key={s.n}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: 8,
              border: '1px solid var(--border, #333)',
              background: step === s.n ? 'rgba(59,130,246,0.2)' : 'transparent',
              fontWeight: step === s.n ? 600 : 400,
            }}
          >
            {s.n}. {s.label}
          </li>
        ))}
      </ol>

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

      <div className="linkage-grid">
        <div className="linkage-col">
          <p className="linkage-col__heading">1 · Empleados GTH</p>
          <div className="controls" style={{ marginBottom: '0.75rem' }}>
            <div className="field">
              <label htmlFor="bio-link-q-emp">Buscar empleado</label>
              <input
                id="bio-link-q-emp"
                value={qEmp}
                onChange={(e) => setQEmp(e.target.value)}
                placeholder="Cédula o nombre…"
              />
            </div>
            <div className="field">
              <label htmlFor="bio-link-filter">Filtro vínculo</label>
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
          </div>
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
                    onClick={() => {
                      setSelectedEmp(it.employee_id)
                      setConfirmOpen(false)
                    }}
                    title={
                      it.linked ? `Vinculado → ${it.person_external_id ?? ''}` : 'Sin vínculo'
                    }
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
                      Sin resultados en GTH
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

        <div className="linkage-col">
          <p className="linkage-col__heading">2 · IDs biométricos sin vínculo</p>
          <div className="controls" style={{ marginBottom: '0.75rem' }}>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="bio-link-q-bio">Buscar ID / nombre en reloj</label>
              <input
                id="bio-link-q-bio"
                value={qBio}
                onChange={(e) => setQBio(e.target.value)}
                placeholder="EmployeeNo o nombre…"
              />
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
                      setConfirmOpen(false)
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
                setConfirmOpen(false)
              }}
              placeholder="ID del reloj"
            />
          </div>
        </div>
      </div>

      <div className="linkage-action">
        <span className="linkage-action__info">
          <strong>
            {selectedEmpData
              ? `${selectedEmpData.cedula} — ${selectedEmpData.full_name}`
              : 'Ningún empleado GTH seleccionado'}
          </strong>
          {' → '}
          <span style={{ color: effectivePerson ? 'var(--accent)' : 'var(--ink-soft)' }}>
            {personLabel || '— ID biométrico —'}
          </span>
        </span>
        {!confirmOpen ? (
          <button
            type="button"
            className="btn btn--primary"
            disabled={busy || !selectedEmp || !effectivePerson}
            onClick={() => {
              setError(null)
              setConfirmOpen(true)
            }}
          >
            Revisar vínculo…
          </button>
        ) : (
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn btn--ghost"
              disabled={busy}
              onClick={() => setConfirmOpen(false)}
            >
              Cancelar
            </button>
            <button
              type="button"
              className="btn btn--primary"
              disabled={busy || !selectedEmp || !effectivePerson}
              onClick={() => void handleLinkConfirmed()}
            >
              Confirmar vínculo
            </button>
          </div>
        )}
      </div>

      {confirmOpen && selectedEmpData && effectivePerson && (
        <div
          role="region"
          aria-label="Confirmación de vínculo"
          style={{
            marginTop: '0.75rem',
            padding: '0.9rem 1rem',
            borderRadius: 10,
            border: '1px solid var(--border, #444)',
            background: 'rgba(59,130,246,0.08)',
            fontSize: '0.9rem',
          }}
        >
          <p style={{ margin: '0 0 0.35rem', fontWeight: 600 }}>3 · Confirme antes de guardar</p>
          <p style={{ margin: 0 }}>
            Se vinculará <strong>{selectedEmpData.full_name}</strong> (cédula{' '}
            {selectedEmpData.cedula}) con el ID biométrico <strong>{effectivePerson}</strong>
            {selectedPersonData?.person_name
              ? ` (${selectedPersonData.person_name} en el reloj)`
              : ''}
            .
            {selectedEmpData.linked
              ? ` Este empleado ya tenía el ID ${selectedEmpData.person_external_id}; se reemplazará.`
              : ''}
          </p>
        </div>
      )}

      <hr className="linkage-divider" />

      <h3 className="linkage-section-title">Presencia por sede GTH</h3>
      <p style={{ fontSize: '0.8rem', color: 'var(--ink-soft)', marginBottom: '1rem' }}>
        Compara empleados activos de <code>hr.employees.site_id</code> con marcajes del día.
        Idealmente exista fila en <code>biometrico.site_map</code> (sede edge ↔ core.sites).
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
          <label htmlFor="core-site">Sede GTH</label>
          <select
            id="core-site"
            value={coreSiteId}
            onChange={(e) => setCoreSiteId(e.target.value)}
          >
            <option value="">— Seleccione sede —</option>
            {sites.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
                {s.city ? ` (${s.city})` : ''}
              </option>
            ))}
          </select>
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
