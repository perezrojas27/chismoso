/** Reglas de puntualidad / salida para el listado de asistencia. */

import { todayISO } from './periodRange'

export const ARRIVAL_CUTOFF = { hours: 9, minutes: 0, seconds: 0 }

export type AttendanceFlags = {
  isLate: boolean
  /** Minutos después de las 09:00; null si llegó a tiempo. */
  delayMinutes: number | null
  /** Sin salida en un día ya cerrado (no es hoy). */
  missingExit: boolean
  /** Sin segunda marca y la fila es del día de hoy. */
  dayInProgress: boolean
}

function parseLocalParts(iso: string): { h: number; m: number; s: number } | null {
  const match = /T(\d{2}):(\d{2}):(\d{2})/.exec(iso)
  if (match) {
    return { h: Number(match[1]), m: Number(match[2]), s: Number(match[3]) }
  }
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  return { h: d.getHours(), m: d.getMinutes(), s: d.getSeconds() }
}

function rowDateISO(rowDate: string): string {
  return rowDate.slice(0, 10)
}

export function getAttendanceFlags(
  firstSeenAt: string,
  lastSeenAt: string | null,
  rowDate?: string,
  today: string = todayISO(),
): AttendanceFlags {
  const parts = parseLocalParts(firstSeenAt)
  let isLate = false
  let delayMinutes: number | null = null

  if (parts) {
    const arrivalSecs = parts.h * 3600 + parts.m * 60 + parts.s
    const cutoffSecs =
      ARRIVAL_CUTOFF.hours * 3600 + ARRIVAL_CUTOFF.minutes * 60 + ARRIVAL_CUTOFF.seconds
    if (arrivalSecs > cutoffSecs) {
      isLate = true
      delayMinutes = Math.floor((arrivalSecs - cutoffSecs) / 60)
    }
  }

  const noExit = !lastSeenAt
  const isToday = Boolean(rowDate && rowDateISO(rowDate) === today)
  const dayInProgress = noExit && isToday
  const missingExit = noExit && !isToday

  return {
    isLate,
    delayMinutes,
    missingExit,
    dayInProgress,
  }
}

export function formatDelay(minutes: number | null): string {
  if (minutes == null || minutes <= 0) return '—'
  if (minutes < 60) return `${minutes} min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m ? `${h} h ${m} min` : `${h} h`
}

export function exitLabel(flags: AttendanceFlags, lastSeenAt: string | null, formatTime: (iso: string) => string): string {
  if (flags.dayInProgress) return 'Día en curso'
  if (flags.missingExit || !lastSeenAt) return 'Sin marca'
  return formatTime(lastSeenAt)
}

export function rowToneClass(flags: AttendanceFlags): string {
  if (flags.isLate && flags.missingExit) return 'row-tone--late-exit'
  if (flags.isLate) return 'row-tone--late'
  if (flags.missingExit) return 'row-tone--missing-exit'
  // Día en curso: no se marca como anomalía de salida
  return ''
}
