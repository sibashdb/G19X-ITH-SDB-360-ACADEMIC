import { useSearchParams } from "react-router"

/** Entero ≥ 1 leído de la URL; cualquier otro valor cuenta como el valor por defecto. */
export function enteroPositivo(
  valor: string | null,
  porDefecto: number,
  maximo = Number.MAX_SAFE_INTEGER
): number {
  const numero = Number(valor)
  if (!valor || !Number.isInteger(numero) || numero < 1) return porDefecto
  return Math.min(numero, maximo)
}

/** El valor solo si está en la lista permitida (la URL se puede editar a mano). */
export function unoDe<T extends string>(valor: string | null, permitidos: readonly T[]): T | null {
  return permitidos.includes(valor as T) ? (valor as T) : null
}

/** Parámetros de búsqueda de la URL y una función para cambiarlos (`null` borra la clave). */
export function useParametros(): [URLSearchParams, (cambios: Record<string, string | null>) => void] {
  const [parametros, setParametros] = useSearchParams()
  function actualizar(cambios: Record<string, string | null>) {
    setParametros((previos) => {
      const siguientes = new URLSearchParams(previos)
      for (const [clave, valor] of Object.entries(cambios)) {
        if (valor) siguientes.set(clave, valor)
        else siguientes.delete(clave)
      }
      return siguientes
    })
  }
  return [parametros, actualizar]
}
