/** Formato corto: PAULO ANTONIO PEREZ ROJAS → PAULO A. PEREZ R. */

const PARTICLES = new Set([
  'DE',
  'DEL',
  'LA',
  'LAS',
  'LOS',
  'Y',
  'DI',
  'DA',
  'SAN',
  'SANTA',
])

function mergeParticles(tokens: string[]): string[] {
  const merged: string[] = []
  let i = 0
  while (i < tokens.length) {
    const parts = [tokens[i]]
    while (i + 1 < tokens.length && PARTICLES.has(tokens[i].toUpperCase())) {
      i += 1
      parts.push(tokens[i])
    }
    merged.push(parts.join(' '))
    i += 1
  }
  return merged
}

function initial(part: string): string {
  for (const ch of part.trim()) {
    if (/[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]/.test(ch)) return ch.toUpperCase()
  }
  return ''
}

export function formatEmployeeName(fullName: string): string {
  const raw = (fullName || '').trim()
  if (!raw) return raw

  const tokens = raw.replace(/,/g, ' ').split(/\s+/).filter(Boolean)
  const parts = mergeParticles(tokens).map((p) => p.toUpperCase())
  if (!parts.length) return raw

  if (parts.length >= 4) {
    return `${parts[0]} ${initial(parts[1])}. ${parts[2]} ${initial(parts[3])}.`
  }
  if (parts.length === 3) {
    return `${parts[0]} ${parts[1]} ${initial(parts[2])}.`
  }
  if (parts.length === 2) {
    return `${parts[0]} ${parts[1]}`
  }
  return parts[0]
}
