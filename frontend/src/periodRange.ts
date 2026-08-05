/** Rangos de consulta de asistencia + validación sin fechas futuras. */

export type AttendancePeriod =
  | 'day'
  | 'week'
  | 'fortnight'
  | 'month'
  | 'quarter'
  | 'semester'

export const ATTENDANCE_PERIODS: { id: AttendancePeriod; label: string }[] = [
  { id: 'day', label: 'Día' },
  { id: 'week', label: 'Semana' },
  { id: 'fortnight', label: 'Quincena' },
  { id: 'month', label: 'Mes' },
  { id: 'quarter', label: 'Trimestre' },
  { id: 'semester', label: 'Semestre' },
]

export const MONTH_NAMES = [
  'Enero',
  'Febrero',
  'Marzo',
  'Abril',
  'Mayo',
  'Junio',
  'Julio',
  'Agosto',
  'Septiembre',
  'Octubre',
  'Noviembre',
  'Diciembre',
] as const

export const QUARTER_LABELS = ['1T (Ene–Mar)', '2T (Abr–Jun)', '3T (Jul–Sep)', '4T (Oct–Dic)'] as const

export const SEMESTER_LABELS = ['1S (Ene–Jun)', '2S (Jul–Dic)'] as const

export type FortnightHalf = '1Q' | '2Q'
export type QuarterIndex = 0 | 1 | 2 | 3
export type SemesterIndex = 0 | 1

function toISO(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function parseISO(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function todayISO(): string {
  return toISO(new Date())
}

/** Limita una fecha ISO a como máximo hoy. */
export function clampToToday(iso: string): string {
  const today = todayISO()
  return iso > today ? today : iso
}

function minISO(a: string, b: string): string {
  return a <= b ? a : b
}

function startOfWeekMonday(d: Date): Date {
  const copy = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const day = copy.getDay()
  const diff = day === 0 ? -6 : 1 - day
  copy.setDate(copy.getDate() + diff)
  return copy
}

function endOfWeekSunday(d: Date): Date {
  const start = startOfWeekMonday(d)
  const end = new Date(start)
  end.setDate(start.getDate() + 6)
  return end
}

function fortnightBounds(d: Date): { from: Date; to: Date } {
  const year = d.getFullYear()
  const month = d.getMonth()
  if (d.getDate() <= 15) {
    return {
      from: new Date(year, month, 1),
      to: new Date(year, month, 15),
    }
  }
  const lastDay = new Date(year, month + 1, 0).getDate()
  return {
    from: new Date(year, month, 16),
    to: new Date(year, month, lastDay),
  }
}

function monthBounds(d: Date): { from: Date; to: Date } {
  const year = d.getFullYear()
  const month = d.getMonth()
  return {
    from: new Date(year, month, 1),
    to: new Date(year, month + 1, 0),
  }
}

function quarterBounds(year: number, quarter: QuarterIndex): { from: Date; to: Date } {
  const startMonth = quarter * 3
  return {
    from: new Date(year, startMonth, 1),
    to: new Date(year, startMonth + 3, 0),
  }
}

function semesterBounds(year: number, semester: SemesterIndex): { from: Date; to: Date } {
  const startMonth = semester * 6
  return {
    from: new Date(year, startMonth, 1),
    to: new Date(year, startMonth + 6, 0),
  }
}

export function anchorForMonth(year: number, monthIndex: number): string {
  const m = String(monthIndex + 1).padStart(2, '0')
  return `${year}-${m}-01`
}

export function anchorForFortnight(
  year: number,
  monthIndex: number,
  half: FortnightHalf,
): string {
  const m = String(monthIndex + 1).padStart(2, '0')
  const day = half === '1Q' ? '01' : '16'
  return `${year}-${m}-${day}`
}

export function anchorForQuarter(year: number, quarter: QuarterIndex): string {
  const month = quarter * 3
  return anchorForMonth(year, month)
}

export function anchorForSemester(year: number, semester: SemesterIndex): string {
  const month = semester * 6
  return anchorForMonth(year, month)
}

export function fortnightHalfFromISO(iso: string): FortnightHalf {
  const day = Number(iso.slice(8, 10))
  return day <= 15 ? '1Q' : '2Q'
}

export function quarterIndexFromISO(iso: string): QuarterIndex {
  const month = monthIndexFromISO(iso)
  return Math.floor(month / 3) as QuarterIndex
}

export function semesterIndexFromISO(iso: string): SemesterIndex {
  const month = monthIndexFromISO(iso)
  return (month < 6 ? 0 : 1) as SemesterIndex
}

export function yearFromISO(iso: string): number {
  return Number(iso.slice(0, 4))
}

export function monthIndexFromISO(iso: string): number {
  return Number(iso.slice(5, 7)) - 1
}

/**
 * Calcula Desde/Hasta según el periodo.
 * La fecha fin nunca supera el día de hoy.
 */
export function rangeForPeriod(
  period: AttendancePeriod,
  anchorISO: string,
): { from: string; to: string } {
  const today = todayISO()
  const anchor = parseISO(clampToToday(anchorISO))
  let from: string
  let to: string

  switch (period) {
    case 'day': {
      const day = toISO(anchor)
      from = day
      to = day
      break
    }
    case 'week': {
      from = toISO(startOfWeekMonday(anchor))
      to = toISO(endOfWeekSunday(anchor))
      break
    }
    case 'fortnight': {
      const bounds = fortnightBounds(anchor)
      from = toISO(bounds.from)
      to = toISO(bounds.to)
      break
    }
    case 'month': {
      const bounds = monthBounds(anchor)
      from = toISO(bounds.from)
      to = toISO(bounds.to)
      break
    }
    case 'quarter': {
      const bounds = quarterBounds(anchor.getFullYear(), quarterIndexFromISO(toISO(anchor)))
      from = toISO(bounds.from)
      to = toISO(bounds.to)
      break
    }
    case 'semester': {
      const bounds = semesterBounds(anchor.getFullYear(), semesterIndexFromISO(toISO(anchor)))
      from = toISO(bounds.from)
      to = toISO(bounds.to)
      break
    }
  }

  to = minISO(to, today)
  if (from > to) {
    from = to
  }
  return { from, to }
}

/** Al cambiar de modo, ancla al periodo actual (hoy). */
export function anchorForCurrentPeriod(_period: AttendancePeriod): string {
  return clampToToday(todayISO())
}

/** Años seleccionables: 5 atrás hasta el año actual. */
export function selectableYears(now = new Date()): number[] {
  const current = now.getFullYear()
  const years: number[] = []
  for (let y = current - 4; y <= current; y += 1) years.push(y)
  return years
}

/** Meses 0–11 permitidos para un año (no futuros). */
export function selectableMonthIndexes(year: number, now = new Date()): number[] {
  const currentYear = now.getFullYear()
  const currentMonth = now.getMonth()
  const maxMonth = year < currentYear ? 11 : year > currentYear ? -1 : currentMonth
  const months: number[] = []
  for (let m = 0; m <= maxMonth; m += 1) months.push(m)
  return months
}

/**
 * Quincenas disponibles en un mes/año.
 * 2Q del mes actual solo si hoy ya está en esa quincena (día >= 16).
 */
export function selectableFortnightHalves(
  year: number,
  monthIndex: number,
  now = new Date(),
): FortnightHalf[] {
  const halves: FortnightHalf[] = ['1Q']
  const currentYear = now.getFullYear()
  const currentMonth = now.getMonth()
  const currentDay = now.getDate()

  if (year < currentYear || (year === currentYear && monthIndex < currentMonth)) {
    halves.push('2Q')
    return halves
  }
  if (year === currentYear && monthIndex === currentMonth && currentDay >= 16) {
    halves.push('2Q')
  }
  return halves
}

/** Trimestres ya iniciados / no futuros. */
export function selectableQuarterIndexes(year: number, now = new Date()): QuarterIndex[] {
  const currentYear = now.getFullYear()
  const currentQuarter = Math.floor(now.getMonth() / 3) as QuarterIndex
  const maxQ = year < currentYear ? 3 : year > currentYear ? -1 : currentQuarter
  const list: QuarterIndex[] = []
  for (let q = 0; q <= maxQ; q += 1) list.push(q as QuarterIndex)
  return list
}

/** Semestres ya iniciados / no futuros. */
export function selectableSemesterIndexes(year: number, now = new Date()): SemesterIndex[] {
  const currentYear = now.getFullYear()
  const currentSemester = (now.getMonth() < 6 ? 0 : 1) as SemesterIndex
  const maxS = year < currentYear ? 1 : year > currentYear ? -1 : currentSemester
  const list: SemesterIndex[] = []
  for (let s = 0; s <= maxS; s += 1) list.push(s as SemesterIndex)
  return list
}

export function isFutureISO(iso: string): boolean {
  return iso > todayISO()
}

/** dd/mm/yyyy para mensajes de UI. */
export function formatISOToDMY(iso: string): string {
  const [y, m, d] = iso.split('-')
  if (!y || !m || !d) return iso
  return `${d}/${m}/${y}`
}

/**
 * Valida un rango de consulta (asistencia).
 * Retorna mensaje de error o null si es válido.
 */
export function validateDateRange(
  fromISO: string,
  toISO: string,
  today = todayISO(),
): string | null {
  const isoRe = /^\d{4}-\d{2}-\d{2}$/
  if (!isoRe.test(fromISO) || !isoRe.test(toISO)) {
    return 'Fecha inválida'
  }
  if (fromISO > toISO) {
    return 'La fecha inicial no puede ser posterior a la final'
  }
  if (fromISO > today || toISO > today) {
    return `No se permiten fechas posteriores a hoy (${formatISOToDMY(today)})`
  }
  return null
}

/** Recorta Desde/Hasta para que nunca superen hoy ni se inviertan. */
export function clampRangeToToday(
  fromISO: string,
  toISO: string,
  today = todayISO(),
): { from: string; to: string } {
  let from = fromISO <= today ? fromISO : today
  let to = toISO <= today ? toISO : today
  if (from > to) from = to
  return { from, to }
}

/** Año máximo seleccionable (= año calendario de hoy). */
export function maxSelectableYear(now = new Date()): number {
  return now.getFullYear()
}
