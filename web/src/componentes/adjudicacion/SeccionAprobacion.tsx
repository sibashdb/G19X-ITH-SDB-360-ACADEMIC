import {
  useIsMutating,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query"
import { TriangleAlert } from "lucide-react"
import { useEffect, useId, useRef, useState, type ReactNode } from "react"
import {
  DECISION,
  useEvaluacion,
  type Evaluacion,
  type MotivoAprobacion,
} from "@/adjudicacion"
import { ErrorApi, enviarJson, pedir } from "@/api"
import { useRoles, useToken, useUsuarioId } from "@/auth"
import { DialogoRechazar } from "@/componentes/adjudicacion/DialogoRechazar"
import { Explicacion } from "@/componentes/adjudicacion/Explicacion"
import { TablaCandidatos } from "@/componentes/adjudicacion/TablaCandidatos"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Termino } from "@/componentes/Termino"
import { Button } from "@/components/ui/button"
import { formatoFechaHora } from "@/fechas"
import type { Evento } from "@/negociacion"

/** Por qué una propuesta necesita aprobación, con sus términos del glosario. */
const MOTIVOS: Record<MotivoAprobacion, ReactNode> = {
  umbral: (
    <>
      Supera el <Termino clave="umbralAprobacion">umbral de aprobación</Termino>
    </>
  ),
  fuera_de_limites: <Termino clave="fueraDeLimites" />,
}

/**
 * La propuesta de adjudicación que espera aprobación: la evaluación guardada al proponer, con la
 * propuesta marcada. Otra persona con el rol de aprobador la aprueba o la rechaza; quien la propuso
 * y los demás solo ven que espera. `alAvisar` recibe el resultado para el aviso de la página,
 * `alConflicto` el texto de un 409 y `alEmpezar` avisa de que se abrió un diálogo o empezó una
 * decisión (el aviso de un conflicto anterior ya no viene al caso).
 *
 * Quien aprueba solo decide sobre la propuesta que ha estado revisando. Si la evaluación se
 * actualiza y trae otra, las acciones se reemplazan por un aviso con «Revisar la propuesta nueva»:
 * así un segundo clic apresurado no aprueba, en el mismo lugar, lo que nadie revisó.
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
  const idCambio = useId()
  const esAprobador = useRoles().includes("aprobador")
  const usuarioId = useUsuarioId()
  // Fuera de «En evaluación» el servicio devuelve la foto de la propuesta y no usa `pesos`.
  const consulta = useEvaluacion(evento.id, null)
  const vigente = consulta.data?.vigente
  // El id de la propuesta que el aprobador está revisando: la primera que llega completa.
  const [revisada, setRevisada] = useState<string | null>(null)
  if (
    vigente?.estado === "pendiente" &&
    revisada === null &&
    !consulta.isFetching
  )
    setRevisada(vigente.id)
  const encabezado = useRef<HTMLHeadingElement>(null)
  const revisar = useRef<HTMLButtonElement>(null)
  const conAcciones = useRef(false)
  // Con una decisión en camino (esta u otra) no se empieza otra.
  const ocupado = useIsMutating({ mutationKey: DECISION }) > 0

  const decide =
    vigente?.estado === "pendiente" &&
    esAprobador &&
    vigente.propuesta_por_id !== usuarioId &&
    revisada !== null
  const hayCambio = decide && vigente.id !== revisada
  const hayAcciones = decide && !hayCambio

  useEffect(() => {
    const habia = conAcciones.current
    conAcciones.current = hayAcciones
    // Si las acciones desaparecen estando el foco en ellas, pasa al aviso del cambio o al contenido
    // y no a <body>.
    if (habia && !hayAcciones && document.activeElement === document.body)
      (revisar.current ?? document.getElementById("contenido"))?.focus()
  }, [hayAcciones])

  const aprobar = useMutation({
    // Sin red, que falle de inmediato y el botón quede libre: por omisión la solicitud se
    // quedaría en espera.
    networkMode: "always",
    mutationKey: DECISION,
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
      // actualiza lo que se ve.
      if (error instanceof ErrorApi && error.estado === 409) {
        alConflicto(error.message)
        // Si la propuesta es otra, las acciones se reemplazan por el aviso del cambio y ahí
        // recibe el foco. Si la negociación cambió de estado, la sección desaparece: al contenido.
        if (error.codigo !== "propuesta_distinta")
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
  // Una propuesta en caché no se muestra mientras llega la viva: la primera que se adopta es siempre
  // la vigente, y no la que el servicio ya reemplazó.
  if (consulta.isPending || (revisada === null && consulta.isFetching)) {
    cuerpo = <EstadoCarga />
  } else if (consulta.isLoadingError) {
    cuerpo = (
      <EstadoError
        error={consulta.error}
        alReintentar={() => void consulta.refetch()}
      />
    )
  } else if (!vigente) {
    // Con la evaluación anterior en caché (sin propuesta), la nueva está en camino. Tras una decisión,
    // la evaluación puede llegar antes que la negociación: mientras esta se actualiza, no hay aviso.
    cuerpo =
      consulta.isFetching || ocupado ? (
        <EstadoCarga />
      ) : (
        <EstadoVacio
          titulo="No hay una propuesta pendiente."
          descripcion="La negociación cambió de estado; actualice la página para ver el estado más reciente."
        />
      )
  } else {
    cuerpo = (
      <div className="space-y-6">
        {hayCambio && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warning p-3 text-sm">
            <p id={idCambio} className="flex items-start gap-2">
              <TriangleAlert
                aria-hidden
                className="mt-0.5 size-4 shrink-0 text-warning"
              />
              <span>
                La propuesta cambió mientras usted la revisaba. Lo que ve abajo
                es la propuesta de {vigente.propuesta_por_nombre}; revísela
                antes de decidir.
              </span>
            </p>
            <Button
              ref={revisar}
              type="button"
              variant="outline"
              aria-describedby={idCambio}
              onClick={() => {
                alEmpezar()
                setRevisada(vigente.id)
                // El botón desaparece: el foco pasa al título, desde donde se lee lo nuevo.
                encabezado.current?.focus()
              }}
            >
              Revisar la propuesta nueva
            </Button>
          </div>
        )}
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
                  <li key={motivo}>{MOTIVOS[motivo]}</li>
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
        {vigente.estado === "pendiente" &&
          vigente.propuesta_por_id === usuarioId && (
            <p className="text-sm text-muted-foreground">
              Usted propuso esta adjudicación; la aprueba otra persona.
            </p>
          )}
        {vigente.estado === "pendiente" &&
          vigente.propuesta_por_id !== usuarioId &&
          !esAprobador && (
            <p className="text-sm text-muted-foreground">
              Esperando aprobación de un aprobador.
            </p>
          )}
        {hayAcciones && (
          <div className="flex flex-wrap justify-end gap-2">
            <DialogoRechazar
              evento={evento}
              adjudicacionId={vigente.id}
              ocupado={ocupado}
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
              aria-disabled={ocupado}
              onClick={() => {
                if (ocupado) return
                alEmpezar()
                aprobar.mutate(vigente.id)
              }}
            >
              Aprobar
            </Button>
          </div>
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
      refTitulo={encabezado}
      descripcion="Un aprobador revisa la propuesta del comprador y la aprueba o la rechaza."
    >
      {cuerpo}
    </Seccion>
  )
}
