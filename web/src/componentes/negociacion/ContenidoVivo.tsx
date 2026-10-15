import type { UseQueryResult } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { EstadoCarga, EstadoError } from "@/componentes/Estados"

/**
 * Como ContenidoConsulta, para pantallas que se actualizan solas cada pocos segundos: si una
 * actualización falla, lo que ya se veía se queda en pantalla con un aviso, en vez del error.
 */
export function ContenidoVivo<T>({
  consulta,
  children,
}: {
  consulta: UseQueryResult<T>
  children: (datos: T) => ReactNode
}) {
  if (consulta.isPending) return <EstadoCarga />
  if (consulta.isLoadingError) {
    return (
      <EstadoError
        error={consulta.error}
        alReintentar={() => void consulta.refetch()}
      />
    )
  }
  return (
    <>
      <p
        role="status"
        className={consulta.isRefetchError ? "text-sm text-warning" : "sr-only"}
      >
        {consulta.isRefetchError
          ? "No se pudo actualizar; se volverá a intentar en unos segundos."
          : ""}
      </p>
      {children(consulta.data)}
    </>
  )
}
