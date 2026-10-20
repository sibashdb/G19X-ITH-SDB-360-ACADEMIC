import { DialogoMotivo } from "@/componentes/adjudicacion/DialogoMotivo"
import { Termino } from "@/componentes/Termino"
import type { Evento } from "@/negociacion"

/** «Declarar desierta» la negociación en evaluación, con el motivo que queda en la bitácora y en la Actividad. */
export function DialogoDesierta({
  evento,
  alDeclarar,
  alConflicto,
  alEmpezar,
}: {
  evento: Evento
  alDeclarar: () => void
  /** El texto del servicio ante un 409: la página lo conserva si la negociación ya no está en evaluación. */
  alConflicto: (mensaje: string) => void
  alEmpezar: () => void
}) {
  return (
    <DialogoMotivo
      ruta={`/negociacion/eventos/${encodeURIComponent(evento.id)}/desierta`}
      textoAbrir="Declarar desierta"
      textoEnviar="Declarar desierta"
      titulo="Declarar desierta la negociación"
      descripcion={
        <>
          Al declararla <Termino clave="desierta">desierta</Termino>, la
          negociación termina sin adjudicar a ningún proveedor y se les avisa
          por correo. No se puede deshacer.
        </>
      }
      etiqueta="Motivo"
      ayuda="Queda en la bitácora y en la Actividad."
      alTerminar={alDeclarar}
      alConflicto={alConflicto}
      alEmpezar={alEmpezar}
    />
  )
}
