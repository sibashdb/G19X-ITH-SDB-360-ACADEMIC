import { useQuery } from "@tanstack/react-query"
import { pedir } from "@/api"
import { useToken } from "@/auth"
import type { EstadoSistema, PaginaActividad } from "@/tipos"

/** Estado de los servicios, compartido por el Panel y la página de estado; se renueva cada 30 s. */
export function useEstadoSistema() {
  const token = useToken()
  return useQuery({
    queryKey: ["estado-sistema"],
    queryFn: () => pedir<EstadoSistema>("/administracion/estado", token),
    enabled: Boolean(token),
    refetchInterval: 30_000,
  })
}

/** Últimos registros de la bitácora con los parámetros dados (p. ej. tipo y tamaño). */
export function useRegistros(parametros: Record<string, string>) {
  const token = useToken()
  return useQuery({
    queryKey: ["actividad", "ultimos", parametros],
    queryFn: () =>
      pedir<PaginaActividad>(
        `/administracion/actividad?${new URLSearchParams(parametros)}`,
        token
      ),
    enabled: Boolean(token),
  })
}
