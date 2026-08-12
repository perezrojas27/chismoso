/**
 * Generación de CSV en el cliente sin dependencias externas.
 * Incluye BOM UTF-8 para compatibilidad con Excel en Windows.
 */
export function downloadCSV(
  filename: string,
  headers: string[],
  rows: (string | number)[][],
): void {
  const escape = (v: string | number): string =>
    `"${String(v).replace(/"/g, '""')}"`

  const lines = [
    headers.map(escape).join(','),
    ...rows.map((row) => row.map(escape).join(',')),
  ]

  const BOM = '\uFEFF'
  const blob = new Blob([BOM + lines.join('\r\n')], {
    type: 'text/csv;charset=utf-8;',
  })

  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
