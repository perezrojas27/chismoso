import { useEffect, useState } from 'react'

/**
 * Retrasa la actualización de un valor hasta que el usuario deja de escribir.
 * Evita disparar efectos/peticiones API en cada pulsación de teclado.
 */
export function useDebounce<T>(value: T, delayMs = 350): T {
  const [debounced, setDebounced] = useState<T>(value)

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(id)
  }, [value, delayMs])

  return debounced
}
