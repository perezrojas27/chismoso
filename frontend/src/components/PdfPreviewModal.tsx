type Props = {
  open: boolean
  title: string
  filename: string
  blobUrl: string | null
  loading: boolean
  error: string | null
  onClose: () => void
}

/**
 * Previa del PDF: el usuario decide Imprimir o Guardar (descargar).
 * No fuerza la descarga al abrir el reporte.
 */
export function PdfPreviewModal({
  open,
  title,
  filename,
  blobUrl,
  loading,
  error,
  onClose,
}: Props) {
  if (!open) return null

  function handlePrint() {
    if (!blobUrl) return
    const frame = document.getElementById('pdf-preview-frame') as HTMLIFrameElement | null
    if (frame?.contentWindow) {
      frame.contentWindow.focus()
      frame.contentWindow.print()
      return
    }
    const win = window.open(blobUrl, '_blank')
    win?.addEventListener('load', () => win.print(), { once: true })
  }

  function handleSave() {
    if (!blobUrl) return
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = filename
    a.rel = 'noopener'
    document.body.appendChild(a)
    a.click()
    a.remove()
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="glass modal-sheet"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-sheet__head">
          <div>
            <h2 className="modal-sheet__title">{title}</h2>
          </div>
          <button type="button" className="btn btn--ghost btn--icon" onClick={onClose} aria-label="Cerrar">
            Cerrar
          </button>
        </div>

        <div className="modal-sheet__actions">
          <button
            type="button"
            className="btn btn--primary"
            onClick={handlePrint}
            disabled={!blobUrl || loading}
          >
            Imprimir
          </button>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={handleSave}
            disabled={!blobUrl || loading}
          >
            Guardar PDF
          </button>
        </div>

        <div className="modal-sheet__body">
          {loading && (
            <div className="loading">
              <span className="spinner" />
              Preparando previa…
            </div>
          )}
          {error && <div className="error">{error}</div>}
          {!loading && !error && blobUrl && (
            <iframe
              id="pdf-preview-frame"
              className="pdf-frame"
              title={title}
              src={blobUrl}
            />
          )}
        </div>
      </div>
    </div>
  )
}
