import { useMemo } from 'react'
import { formatDate } from '../api'
import {
  ATTENDANCE_PERIODS,
  MONTH_NAMES,
  QUARTER_LABELS,
  SEMESTER_LABELS,
  anchorForFortnight,
  anchorForMonth,
  anchorForQuarter,
  anchorForSemester,
  fortnightHalfFromISO,
  maxSelectableYear,
  monthIndexFromISO,
  quarterIndexFromISO,
  selectableFortnightHalves,
  selectableMonthIndexes,
  selectableQuarterIndexes,
  selectableSemesterIndexes,
  selectableYears,
  semesterIndexFromISO,
  todayISO,
  yearFromISO,
  type AttendancePeriod,
  type QuarterIndex,
  type SemesterIndex,
} from '../periodRange'

type Props = {
  period: AttendancePeriod
  anchorDate: string
  fromDate: string
  toDate: string
  maxDate: string
  /** Callback principal: periodo + ancla elegida */
  onApply: (period: AttendancePeriod, anchor?: string) => void
}

/**
 * Controles de selección de periodo para la vista de Asistencia.
 * Extraído de App.tsx para mantener ese componente manejable.
 */
export function PeriodSelector({ period, anchorDate, fromDate, toDate, maxDate, onApply }: Props) {
  function clampYear(year: number): number {
    return Math.min(year, maxSelectableYear())
  }

  function selectMode(next: AttendancePeriod) {
    onApply(next, todayISO())
  }

  const years = useMemo(() => selectableYears(), [maxDate])

  const monthIndexes = useMemo(
    () => selectableMonthIndexes(yearFromISO(anchorDate)),
    [anchorDate],
  )
  const fortnightHalves = useMemo(
    () => selectableFortnightHalves(yearFromISO(anchorDate), monthIndexFromISO(anchorDate)),
    [anchorDate],
  )
  const quarterIndexes = useMemo(
    () => selectableQuarterIndexes(yearFromISO(anchorDate)),
    [anchorDate],
  )
  const semesterIndexes = useMemo(
    () => selectableSemesterIndexes(yearFromISO(anchorDate)),
    [anchorDate],
  )

  return (
    <>
      <nav className="segmented segmented--periods" aria-label="Periodo de asistencia">
        {ATTENDANCE_PERIODS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`segmented__btn ${period === item.id ? 'is-active' : ''}`}
            onClick={() => selectMode(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {(period === 'week' || period === 'quarter' || period === 'semester') && (
        <p className="period-anchor-hint">
          Rango: {formatDate(fromDate)} — {formatDate(toDate)}
        </p>
      )}

      <div className="controls">
        {period === 'month' && (
          <>
            <div className="field">
              <label htmlFor="month-select">Mes</label>
              <select
                id="month-select"
                value={monthIndexFromISO(anchorDate)}
                onChange={(e) => {
                  const monthIndex = Number(e.target.value)
                  onApply('month', anchorForMonth(yearFromISO(anchorDate), monthIndex))
                }}
              >
                {monthIndexes.map((index) => (
                  <option key={MONTH_NAMES[index]} value={index}>
                    {MONTH_NAMES[index]}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="year-select">Año</label>
              <select
                id="year-select"
                value={yearFromISO(anchorDate)}
                onChange={(e) => {
                  const year = clampYear(Number(e.target.value))
                  const months = selectableMonthIndexes(year)
                  const preferred = monthIndexFromISO(anchorDate)
                  const month = months.includes(preferred)
                    ? preferred
                    : (months[months.length - 1] ?? 0)
                  onApply('month', anchorForMonth(year, month))
                }}
              >
                {years.map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
            </div>
          </>
        )}

        {period === 'quarter' && (
          <>
            <div className="field field--grow">
              <label htmlFor="quarter-select">Trimestre</label>
              <select
                id="quarter-select"
                value={quarterIndexFromISO(anchorDate)}
                onChange={(e) => {
                  const quarter = Number(e.target.value) as QuarterIndex
                  onApply('quarter', anchorForQuarter(yearFromISO(anchorDate), quarter))
                }}
              >
                {quarterIndexes.map((index) => (
                  <option key={QUARTER_LABELS[index]} value={index}>
                    {QUARTER_LABELS[index]}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="quarter-year">Año</label>
              <select
                id="quarter-year"
                value={yearFromISO(anchorDate)}
                onChange={(e) => {
                  const year = clampYear(Number(e.target.value))
                  const allowed = selectableQuarterIndexes(year)
                  const preferred = quarterIndexFromISO(anchorDate)
                  const quarter = (
                    allowed.includes(preferred) ? preferred : (allowed[allowed.length - 1] ?? 0)
                  ) as QuarterIndex
                  onApply('quarter', anchorForQuarter(year, quarter))
                }}
              >
                {years.map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
            </div>
          </>
        )}

        {period === 'semester' && (
          <>
            <div className="field field--grow">
              <label htmlFor="semester-select">Semestre</label>
              <select
                id="semester-select"
                value={semesterIndexFromISO(anchorDate)}
                onChange={(e) => {
                  const semester = Number(e.target.value) as SemesterIndex
                  onApply('semester', anchorForSemester(yearFromISO(anchorDate), semester))
                }}
              >
                {semesterIndexes.map((index) => (
                  <option key={SEMESTER_LABELS[index]} value={index}>
                    {SEMESTER_LABELS[index]}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="semester-year">Año</label>
              <select
                id="semester-year"
                value={yearFromISO(anchorDate)}
                onChange={(e) => {
                  const year = clampYear(Number(e.target.value))
                  const allowed = selectableSemesterIndexes(year)
                  const preferred = semesterIndexFromISO(anchorDate)
                  const semester = (
                    allowed.includes(preferred) ? preferred : (allowed[allowed.length - 1] ?? 0)
                  ) as SemesterIndex
                  onApply('semester', anchorForSemester(year, semester))
                }}
              >
                {years.map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
            </div>
          </>
        )}

        {period === 'fortnight' && (
          <>
            <div className="field field--grow">
              <label>Quincena</label>
              <div className="segmented segmented--half" role="group" aria-label="1Q o 2Q">
                {fortnightHalves.map((half) => (
                  <button
                    key={half}
                    type="button"
                    className={`segmented__btn ${
                      fortnightHalfFromISO(anchorDate) === half ? 'is-active' : ''
                    }`}
                    onClick={() =>
                      onApply(
                        'fortnight',
                        anchorForFortnight(
                          yearFromISO(anchorDate),
                          monthIndexFromISO(anchorDate),
                          half,
                        ),
                      )
                    }
                  >
                    {half}
                  </button>
                ))}
              </div>
            </div>
            <div className="field">
              <label htmlFor="fortnight-month">Mes</label>
              <select
                id="fortnight-month"
                value={monthIndexFromISO(anchorDate)}
                onChange={(e) => {
                  const monthIndex = Number(e.target.value)
                  const halves = selectableFortnightHalves(yearFromISO(anchorDate), monthIndex)
                  const preferred = fortnightHalfFromISO(anchorDate)
                  const half = halves.includes(preferred)
                    ? preferred
                    : (halves[halves.length - 1] ?? '1Q')
                  onApply('fortnight', anchorForFortnight(yearFromISO(anchorDate), monthIndex, half))
                }}
              >
                {monthIndexes.map((index) => (
                  <option key={MONTH_NAMES[index]} value={index}>
                    {MONTH_NAMES[index]}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="fortnight-year">Año</label>
              <select
                id="fortnight-year"
                value={yearFromISO(anchorDate)}
                onChange={(e) => {
                  const year = clampYear(Number(e.target.value))
                  const months = selectableMonthIndexes(year)
                  const preferredMonth = monthIndexFromISO(anchorDate)
                  const month = months.includes(preferredMonth)
                    ? preferredMonth
                    : (months[months.length - 1] ?? 0)
                  const halves = selectableFortnightHalves(year, month)
                  const preferredHalf = fortnightHalfFromISO(anchorDate)
                  const half = halves.includes(preferredHalf)
                    ? preferredHalf
                    : (halves[halves.length - 1] ?? '1Q')
                  onApply('fortnight', anchorForFortnight(year, month, half))
                }}
              >
                {years.map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
            </div>
          </>
        )}

        {(period === 'day' || period === 'week') && (
          <div className="field">
            <label htmlFor="anchor-date">
              {period === 'day' ? 'Fecha específica' : 'Semana (elige un día)'}
            </label>
            <input
              id="anchor-date"
              type="date"
              max={maxDate}
              value={anchorDate}
              onChange={(e) => onApply(period, e.target.value)}
            />
          </div>
        )}

        {period === 'week' && (
          <>
            <div className="field">
              <label htmlFor="from-date">Desde</label>
              <input
                id="from-date"
                type="date"
                value={fromDate}
                readOnly
                disabled
                title="Se calcula automáticamente según la semana"
              />
            </div>
            <div className="field">
              <label htmlFor="to-date">Hasta</label>
              <input
                id="to-date"
                type="date"
                value={toDate}
                readOnly
                disabled
                title="Hasta hoy si la semana aún no termina"
              />
            </div>
          </>
        )}
      </div>
    </>
  )
}
