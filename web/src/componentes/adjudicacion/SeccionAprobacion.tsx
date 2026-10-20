import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useId } from "react"
import { NOMBRES_MOTIVO, useEvaluacion, type Evaluacion } from "@/adjudicacion"
import { ErrorApi, enviarJson, pedir } from "@/api"
import { useRoles, useToken, useUsuarioId } from "@/auth"
import { DialogoRechazar } from "@/componentes/adjudicacion/DialogoRechazar"
import { Explicacion } from "@/componentes/adjudicacion/Explicacion"
import { TablaCandidatos } from "@/componentes/adjudicacion/TablaCandidatos"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Button } from "@/components/ui/button"
import { formatoFechaHora } from "@/fechas"
import type { Evento } from "@/negociacion"

/**
 * La propuesta de adjudicación que espera aprobación: la evaluación guardada al proponer, con la
 * propuesta marcada. Otra persona con el rol de aprobador la aprueba o la rechaza; quien la propuso
 * y los demás solo ven que espera. `alAvisar` recibe el resultado para el aviso de la página,
 * `alConflicto` el texto de un 409 y `alEmpezar` avisa de que se abrió un diálogo o empezó una
 * decisión (el aviso de un conflicto anterior ya no viene al caso).
 */
export function SeccionAprobacion({
  evento,
  alAvisar,
  alConflicto,
  alEmpezar,
}: {
  evento: Evento
  alAvisar: (texto: string) => void
  alConflicto: (texto: string) => void
  alEmpezar: () => void
}) {
  const token = useToken()
  const cliente = useQueryClient()
  const idMotivos = useId()
  const esAprobador = useRoles().includes("aprobador")
  const usuarioId = useUsuarioId()
  // Fuera de «En evaluación» el servicio devuelve la foto de la propuesta y no usa `pesos`.
  const consulta = useEvaluacion(evento.id, null)
  const vigente = consulta.data?.vigente
  const aprobar = useMutation({
    // Sin red, que falle de inmediato y el botón quede libre: por omisión la solicitud se
    // quedaría en espera.
    networkMode: "always",
    mutationFn: (adjudicacionId: string) =>
      pedir<Evaluacion>(
        `/negociacion/eventos/${encodeURIComponent(evento.id)}/adjudicacion/aprobar`,
        token,
        enviarJson("POST", { adjudicacion_id: adjudicacionId })
      ),
    onSuccess: async () => {
      alAvisar("Se aprobó la adjudicación.")
      // La negociación sale de «Pendiente de aprobación» y el botón desaparece: el foco pasa al
      // contenido y no a <body> (ver DialogoCancelar).
      document.getElementById("contenido")?.focus()
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
    },
    onError: (error) => {
      // Un 409 es que la propuesta o la negociación ya cambiaron: no se decidió nada y se
      // actualiza lo que se ve. Si la sección desaparece, el foco ya está en el contenido.
      if (error instanceof ErrorApi && error.estado === 409) {
        alConflicto(error.message)
        document.getElementById("contenido")?.focus()
        void cliente.invalidateQueries({ queryKey: ["negociacion"] })
      }
    },
  })
  // Los 409 van al aviso de la página; cualquier otro error, aquí.
  const error =
    aprobar.isError &&
    !(aprobar.error instanceof ErrorApi && aprobar.error.estado === 409)
      ? aprobar.error.message
      : ""

  let cuerpo
  if (consulta.isPending) {
    cuerpo = <EstadoCarga />
  } else if (consulta.isLoadingError) {
    cuerpo = (
      <EstadoError
        error={consulta.error}
        alReintentar={() => void consulta.refetch()}
      />
    )
  } else if (!vigente) {
    // Con la evaluación anterior en caché (sin propuesta), la nueva está en camino.
    cuerpo = consulta.isFetching ? (
      <EstadoCarga />
    ) : (
      <EstadoVacio
        titulo="No hay una propuesta pendiente."
        descripcion="La negociación cambió de estado; actualice la página para ver el estado más reciente."
      />
    )
  } else {
    const propuso = vigente.propuesta_por_id === usuarioId
    cuerpo = (
      <div className="space-y-6">
        <div className="space-y-2 text-sm">
          <p>
            Propuesta de {vigente.propuesta_por_nombre},{" "}
            {formatoFechaHora(vigente.propuesta_en)}
          </p>
          {vigente.justificacion && (
            <p>
              <span className="font-medium">Justificación:</span>{" "}
              {vigente.justificacion}
            </p>
          )}
          {vigente.motivo_aprobacion.length > 0 && (
            <div>
              <p id={idMotivos} className="font-medium">
                Por qué requiere aprobación
              </p>
              <ul aria-labelledby={idMotivos} className="list-disc pl-5">
                {vigente.motivo_aprobacion.map((motivo) => (
                  <li key={motivo}>{NOMBRES_MOTIVO[motivo]}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <TablaCandidatos
          recomendacion={vigente.recomendacion}
          evento={evento}
          destacada={vigente.sesion_id}
        />
        <Explicacion recomendacion={vigente.recomendacion} />
        {propuso ? (
          <p className="text-sm text-muted-foreground">
            Usted propuso esta adjudicación; la aprueba otra persona.
          </p>
        ) : esAprobador ? (
          <div className="flex flex-wrap justify-end gap-2">
            <DialogoRechazar
              evento={evento}
              adjudicacionId={vigente.id}
              alConflicto={alConflicto}
              alEmpezar={alEmpezar}
              alRechazar={() =>
                alAvisar(
                  "Se rechazó la propuesta; la negociación vuelve a evaluación."
                )
              }
            />
            <Button
              type="button"
              aria-disabled={aprobar.isPending}
              onClick={() => {
                if (aprobar.isPending) return
                alEmpezar()
                aprobar.mutate(vigente.id)
              }}
            >
              Aprobar
            </Button>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Esperando aprobación de un aprobador.
          </p>
        )}
        <p
          role="alert"
          className={error ? "text-sm text-destructive" : "sr-only"}
        >
          {error}
        </p>
      </div>
    )
  }

  return (
    <Seccion
      titulo="Propuesta pendiente de aprobación"
      descripcion="Un aprobador revisa la propuesta del comprador y la aprueba o la rechaza."
    >
      {cuerpo}
    </Seccion>
  )
}
