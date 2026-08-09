import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  createDevice,
  deleteDevice,
  fetchDevices,
  type DeviceHealth,
  type DevicesResponse,
} from '../api'

const EMPTY_FORM = {
  host: '',
  port: '80',
  location: 'Torre Sindoni Ascensores Pequeños',
}

function displayName(d: DeviceHealth): string {
  return (d.location || '').trim() || d.host
}

export function DevicesPanel() {
  const [data, setData] = useState<DevicesResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [showForm, setShowForm] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await fetchDevices())
    } catch (err) {
      setData(null)
      setError(err instanceof Error ? err.message : 'No se pudo consultar dispositivos')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    setNotice(null)
    try {
      const port = Number(form.port)
      if (!Number.isFinite(port) || port < 1 || port > 65535) {
        throw new Error('Puerto inválido (1–65535)')
      }
      if (!form.location.trim()) {
        throw new Error('Indique la ubicación del dispositivo')
      }
      const result = await createDevice({
        host: form.host.trim(),
        port,
        location: form.location.trim(),
      })
      setNotice(result.message)
      setForm(EMPTY_FORM)
      setShowForm(false)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo guardar el dispositivo')
    } finally {
      setSaving(false)
    }
  }

  async function onRemove(device: DeviceHealth) {
    if (!device.removable) return
    const ok = window.confirm(`¿Eliminar el dispositivo en ${displayName(device)}?`)
    if (!ok) return
    setSaving(true)
    setError(null)
    setNotice(null)
    try {
      const result = await deleteDevice(device.device_id)
      setNotice(result.message)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo eliminar')
    } finally {
      setSaving(false)
    }
  }

  const readOnly = Boolean(data?.read_only)
  const statusLabel =
    data?.status === 'ok'
      ? 'Todos en línea'
      : data?.status === 'partial'
        ? 'Conexión parcial'
        : data?.status === 'offline'
          ? 'Sin conexión'
          : data?.status === 'mock'
            ? 'Modo mock'
            : data?.status === 'empty'
              ? 'Sin dispositivos'
              : data?.status || '—'

  return (
    <section className="glass panel devices-panel">
      <header className="devices-panel__header">
        <div>
          <p className="devices-panel__eyebrow">Administración TI</p>
          <h2 className="devices-panel__title">Dispositivos biométricos</h2>
          <p className="devices-panel__lead">
            {readOnly
              ? 'Inventario reportado por agentes edge (heartbeat). El alta/baja ISAPI se gestiona en la sede.'
              : 'Monitoreo ISAPI y alta de terminales por ubicación. Los del .env conviven con los agregados aquí.'}
          </p>
        </div>
        <div className="devices-panel__actions">
          {!readOnly && (
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => setShowForm((v) => !v)}
              disabled={saving}
            >
              {showForm ? 'Cancelar' : 'Agregar dispositivo'}
            </button>
          )}
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => void load()}
            disabled={loading || saving}
          >
            {loading ? 'Actualizando…' : readOnly ? 'Actualizar inventario' : 'Probar conexiones'}
          </button>
        </div>
      </header>

      {readOnly && data?.message && (
        <div className="banner-info" role="status">
          {data.message}
        </div>
      )}

      {!readOnly && showForm && (
        <form className="devices-form" onSubmit={(e) => void onSubmit(e)}>
          <div className="devices-form__grid devices-form__grid--no-id">
            <div className="field devices-form__location">
              <label htmlFor="dev-location">Ubicación</label>
              <input
                id="dev-location"
                value={form.location}
                placeholder="Torre Sindoni Ascensores Pequeños"
                maxLength={120}
                required
                onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))}
              />
            </div>
            <div className="field">
              <label htmlFor="dev-host">Host / IP</label>
              <input
                id="dev-host"
                value={form.host}
                placeholder="192.168.10.201"
                required
                onChange={(e) => setForm((f) => ({ ...f, host: e.target.value }))}
              />
            </div>
            <div className="field">
              <label htmlFor="dev-port">Puerto</label>
              <input
                id="dev-port"
                type="number"
                min={1}
                max={65535}
                value={form.port}
                required
                onChange={(e) => setForm((f) => ({ ...f, port: e.target.value }))}
              />
            </div>
          </div>
          <div className="devices-form__foot">
            <p className="period-anchor-hint">
              Credenciales ISAPI: las del backend (<code>HIKVISION_USER</code> / password).
            </p>
            <button type="submit" className="btn btn--primary" disabled={saving}>
              {saving ? 'Guardando…' : 'Guardar'}
            </button>
          </div>
        </form>
      )}

      {(error || notice) && (
        <p
          className={`devices-banner ${error ? 'devices-banner--error' : 'devices-banner--ok'}`}
          role="status"
        >
          {error || notice}
        </p>
      )}

      {data && (
        <>
          <div className="devices-summary-bar">
            <span className={`devices-pill devices-pill--${data.status}`}>{statusLabel}</span>
            <span className="devices-summary-bar__meta">
              <strong>
                {data.devices_ok}/{data.devices_total}
              </strong>{' '}
              en línea · fuente <strong>{data.source}</strong>
            </span>
            {data.message && <span className="devices-summary-bar__hint">{data.message}</span>}
          </div>

          <div className="device-cards">
            {data.devices.length === 0 ? (
              <div className="device-card device-card--empty">
                <p>
                  {readOnly
                    ? 'Sin dispositivos reportados por el agente edge. Verifique enroll/heartbeat.'
                    : 'No hay dispositivos. Agregue un terminal por su ubicación.'}
                </p>
              </div>
            ) : (
              data.devices.map((d) => (
                <article
                  key={`${d.host}-${d.port ?? 80}`}
                  className={`device-card ${d.online ? 'device-card--online' : 'device-card--offline'}`}
                >
                  <div className="device-card__top">
                    <span
                      className={`device-online ${
                        d.online ? 'device-online--ok' : 'device-online--bad'
                      }`}
                    >
                      {d.online ? 'En línea' : 'Fuera de línea'}
                    </span>
                    <span className="device-card__origin">
                      {d.origin === 'managed'
                        ? 'UI'
                        : d.origin === 'discovered'
                          ? 'Detectado'
                          : d.origin === 'agent'
                            ? 'Agente'
                            : '.env'}
                    </span>
                  </div>
                  <h3 className="device-card__place">
                    <span className="device-card__pin" aria-hidden>
                      <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
                        <path
                          d="M12 22s7-7.2 7-12.2A7 7 0 1 0 5 9.8C5 14.8 12 22 12 22Z"
                          stroke="currentColor"
                          strokeWidth="1.8"
                          strokeLinejoin="round"
                        />
                        <circle cx="12" cy="9.5" r="2.4" stroke="currentColor" strokeWidth="1.8" />
                      </svg>
                    </span>
                    <span>{displayName(d)}</span>
                  </h3>
                  <p className="device-card__endpoint">
                    {d.host}
                    <span>:{d.port ?? '—'}</span>
                  </p>
                  {d.connection_established ? (
                    <p className="device-search__ok">Conexión establecida</p>
                  ) : (
                    <p className="device-search__fail">
                      {d.status_message ||
                        (readOnly
                          ? 'Inventario edge (ISAPI pendiente de verificar)'
                          : 'Conexión fallida')}
                      {!readOnly && d.origin === 'discovered' ? ' · no configurado' : ''}
                    </p>
                  )}
                  {!readOnly && d.origin === 'discovered' && (
                    <button
                      type="button"
                      className="btn btn--primary device-card__remove"
                      onClick={() => {
                        setForm({
                          host: d.host,
                          port: String(d.port ?? 80),
                          location: d.location || 'Torre Sindoni Ascensores Pequeños',
                        })
                        setShowForm(true)
                        setNotice(
                          `Dispositivo detectado en ${d.host}. Confirma la ubicación y guarda.`,
                        )
                      }}
                      disabled={saving}
                    >
                      Configurar
                    </button>
                  )}
                  {!readOnly && d.removable && (
                    <button
                      type="button"
                      className="btn btn--ghost device-card__remove"
                      onClick={() => void onRemove(d)}
                      disabled={saving}
                    >
                      Eliminar
                    </button>
                  )}
                </article>
              ))
            )}
          </div>

          <footer className="devices-panel__footer">
            Usuario ISAPI <strong>{data.user}</strong>
            {data.use_https ? ' · HTTPS' : ' · HTTP'} · Corte comedor{' '}
            {data.cafeteria_cutoff.slice(0, 5)} · Excepciones GTH hasta{' '}
            {data.cafeteria_late_end.slice(0, 5)}
          </footer>
        </>
      )}

      {!data && loading && (
        <div className="loading">
          <span className="spinner" />
          Consultando dispositivos…
        </div>
      )}
    </section>
  )
}
