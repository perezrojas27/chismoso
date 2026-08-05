import { useEffect, useState } from 'react'

/** Filas por página: más corto en pantallas estrechas. */
export function usePageSize(desktop = 25, mobile = 10, breakpoint = 640): number {
  const [pageSize, setPageSize] = useState(() =>
    typeof window !== 'undefined' && window.matchMedia(`(max-width: ${breakpoint}px)`).matches
      ? mobile
      : desktop,
  )

  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${breakpoint}px)`)
    const sync = () => setPageSize(mq.matches ? mobile : desktop)
    sync()
    mq.addEventListener('change', sync)
    return () => mq.removeEventListener('change', sync)
  }, [breakpoint, desktop, mobile])

  return pageSize
}
