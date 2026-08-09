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

type Props = {
  biometricSiteId?: string
}

export function PersonLinkagePanel({ biometricSiteId }: Props) {
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState<'all' | 'linked' | 'unlinked'>('unlinked')
  const [items, setItems] = useState<BioLinkageItem[]>([])
  const [stats, setStats] = useState({ active: 0, linked: 0, unlinked: 0 })
  const [persons, setPersons] = useState<BioPersonUnlinked[]>([])
  const [selectedEmp, setSelectedEmp] = useState('')
  const [selectedPerson, setSelectedPerson] = useState('')
  const [presenceDate, setPresenceDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [coreSiteId, setCoreSiteId] = useState('')
  const [presence, setPresence] = useState<PresenceReport | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    const [emp, pers] = await Promise.all([
      fetchBioLinkageActive({ q: q || undefined, link_filter: filter }),
      fetchBioPersonsUnlinked({
        q: q || undefined,
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
  }, [q, filter, biometricSiteId])

  useEffect(() => {
    void refresh().catch((err: unknown) => {
      setError(err instanceof Error ? err.message : 'Error al cargar vínculos')
    })
  }, [refresh])

  async function handleLink() {
    if (!selectedEmp || !selectedPerson) {
      setError('Elija empleado GTH e ID biométrico (employeeNo)')
      return
    }
    setBusy(true)
    setError(null)
    setMsg(null)
    try {
      await linkBioPerson(selectedEmp, selectedPerson)
      setMsg('Vínculo guardado')
      setSelectedPerson('')
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
      setError('Indique UUID de sede GTH (core.sites) para el reporte de presencia')
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

  return (
    <section className="glass panel">
      <h2 className="panel__title">Vínculo GTH ↔ biométrico</h2>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
        El reloj identifica personas con <code>employeeNo</code> (ID propio). Para saber quién faltó
        por marcar en una sede hay que vincular ese ID con el empleado de GTH (cédula / ficha), igual
        que la vinculación de correo corporativo.
      </p>

      <div className="controls" style={{ flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1rem' }}>
        <div className="field">
          <label htmlFor="bio-link-q">Buscar</label>
          <input
            id="bio-link-q"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Cédula o nombre"
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
        <button type="button" className="btn" disabled={busy} onClick={() => void refresh()}>
          Actualizar
        </button>
      </div>

      <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        Activos GTH: {stats.active} · Vinculados: {stats.linked} · Sin vínculo: {stats.unlinked}
      </p>

      {error && <p style={{ color: 'var(--danger)', fontSize: '0.85rem' }}>{error}</p>}
      {msg && <p style={{ color: 'var(--accent)', fontSize: '0.85rem' }}>{msg}</p>}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '1rem' }}>
        <div>
          <h3 style={{ fontSize: '0.9rem', marginBottom: '0.5rem' }}>Empleado GTH</h3>
          <select
            value={selectedEmp}
            onChange={(e) => setSelectedEmp(e.target.value)}
            style={{ width: '100%', minHeight: '2.5rem' }}
            size={8}
          >
            {items.map((it) => (
              <option key={it.employee_id} value={it.employee_id}>
                {it.linked ? '● ' : '○ '}
                {it.cedula} — {it.full_name}
                {it.person_external_id ? ` → ${it.person_external_id}` : ''}
              </option>
            ))}
          </select>
        </div>
        <div>
          <h3 style={{ fontSize: '0.9rem', marginBottom: '0.5rem' }}>
            IDs biométricos sin vínculo (desde marcajes)
          </h3>
          <select
            value={selectedPerson}
            onChange={(e) => setSelectedPerson(e.target.value)}
            style={{ width: '100%', minHeight: '2.5rem' }}
            size={8}
          >
            <option value="">— elegir —</option>
            {persons.map((p) => (
              <option key={p.person_external_id} value={p.person_external_id}>
                {p.person_external_id} · {p.person_name || 'sin nombre'} ({p.event_count} evt)
              </option>
            ))}
          </select>
          <div style={{ marginTop: '0.5rem' }}>
            <label style={{ fontSize: '0.75rem', display: 'block' }}>
              O escribir employeeNo manualmente
            </label>
            <input
              value={selectedPerson}
              onChange={(e) => setSelectedPerson(e.target.value)}
              placeholder="ID del reloj"
              style={{ width: '100%' }}
            />
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void handleLink()}>
          Vincular
        </button>
        <button
          type="button"
          className="btn"
          disabled={busy || !selectedEmp}
          onClick={() => selectedEmp && void handleUnlink(selectedEmp)}
        >
          Desvincular seleccionado
        </button>
      </div>

      <hr style={{ margin: '1.5rem 0', borderColor: 'var(--border)' }} />

      <h3 style={{ fontSize: '0.95rem' }}>Presencia por sede GTH</h3>
      <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        Compara empleados activos de <code>hr.employees.site_id</code> con marcajes del día. Requiere
        vínculos y, idealmente, fila en <code>biometrico.site_map</code> (sede edge ↔ core.sites).
      </p>
      <div className="controls" style={{ flexWrap: 'wrap', gap: '0.75rem' }}>
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
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void handlePresence()}>
          Calcular
        </button>
      </div>

      {presence && (
        <div style={{ marginTop: '1rem', fontSize: '0.85rem' }}>
          {presence.site_map_missing && (
            <p style={{ color: 'var(--warning, #c90)' }}>
              Sin mapa de sede: se usaron marcajes de todas las sedes del día (menos preciso).
            </p>
          )}
          <p>
            Presentes: {presence.counts.present} · Ausentes (vinculados): {presence.counts.absent} ·
            Sin vínculo: {presence.counts.unlinked}
          </p>
          {presence.absent.length > 0 && (
            <>
              <h4 style={{ marginTop: '0.75rem' }}>No marcaron</h4>
              <ul>
                {presence.absent.map((a) => (
                  <li key={a.employee_id}>
                    {a.cedula} — {a.full_name} ({a.person_external_id})
                  </li>
                ))}
              </ul>
            </>
          )}
          {presence.unlinked_employees.length > 0 && (
            <>
              <h4 style={{ marginTop: '0.75rem' }}>Activos sin vínculo (no se puede saber)</h4>
              <ul>
                {presence.unlinked_employees.slice(0, 30).map((a) => (
                  <li key={a.employee_id}>
                    {a.cedula} — {a.full_name}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  )
}
