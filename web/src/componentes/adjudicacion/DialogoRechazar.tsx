import { DialogoMotivo } from "@/componentes/adjudicacion/DialogoMotivo"
import type { Evento } from "@/negociacion"

/**
 * «Rechazar» la propuesta pendiente, con el motivo que queda con la propuesta rechazada (se ve en la
 * evaluación y en el resumen; la Actividad no registra los rechazos). `adjudicacionId` es el
 * de la propuesta que el aprobador revisó (el `vigente.id` de la evaluación en pantalla): si ya no
 * es la vigente, el servicio no decide nada.
 */
export function DialogoRechazar({
  evento,
  adjudicacionId,
  ocupado,
  alRechazar,
  alConflicto,
  alEmpezar,
}: {
  evento: Evento
  adjudicacionId: string
  /** Hay otra decisión en camino: «Rechazar» no abre mientras tanto. */
  ocupado: boolean
  alRechazar: () => void
  /** El texto del servicio ante un 409: la página lo conserva si la propuesta o la negociación cambiaron. */
  alConflicto: (mensaje: string) => void
  alEmpezar: () => void
}) {
  return (
    <DialogoMotivo
      ruta={`/negociacion/eventos/${encodeURIComponent(evento.id)}/adjudicacion/rechazar`}
      datos={{ adjudicacion_id: adjudicacionId }}
      ocupado={ocupado}
      textoAbrir="Rechazar"
      textoEnviar="Rechazar propuesta"
      titulo="Rechazar la propuesta"
      descripcion="La propuesta queda rechazada y la negociación vuelve a evaluación para que el comprador proponga de nuevo. No se puede deshacer."
      etiqueta="Motivo del rechazo"
      ayuda="Queda con la propuesta rechazada."
      alTerminar={alRechazar}
      alConflicto={alConflicto}
      alEmpezar={alEmpezar}
    />
  )
}
