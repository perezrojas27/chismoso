type Props = {
  page: number
  pageSize: number
  total: number
  onChange: (page: number) => void
}

export function PaginationBar({ page, pageSize, total, onChange }: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const safePage = Math.min(Math.max(1, page), totalPages)
  const from = total === 0 ? 0 : (safePage - 1) * pageSize + 1
  const to = Math.min(safePage * pageSize, total)

  if (total <= pageSize) {
    return (
      <div className="pagination">
        <span className="pagination__meta">
          {total} registro{total === 1 ? '' : 's'}
        </span>
      </div>
    )
  }

  return (
    <div className="pagination">
      <span className="pagination__meta">
        {from}–{to} de {total}
      </span>
      <div className="pagination__actions">
        <button
          type="button"
          className="btn btn--ghost btn--page"
          disabled={safePage <= 1}
          onClick={() => onChange(safePage - 1)}
        >
          Anterior
        </button>
        <span className="pagination__page">
          {safePage} / {totalPages}
        </span>
        <button
          type="button"
          className="btn btn--ghost btn--page"
          disabled={safePage >= totalPages}
          onClick={() => onChange(safePage + 1)}
        >
          Siguiente
        </button>
      </div>
    </div>
  )
}
