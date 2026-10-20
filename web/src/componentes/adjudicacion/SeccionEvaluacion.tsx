import { keepPreviousData } from "@tanstack/react-query"
import { useState } from "react"
import {
  PESOS_POR_OMISION,
  useEvaluacion,
  type Evaluacion,
  type Pesos,
} from "@/adjudicacion"
import { erroresPorCampo } from "@/api"
import { useRoles } from "@/auth"
import { AjustarPesos } from "@/componentes/adjudicacion/AjustarPesos"
import { DialogoAdjudicar } from "@/componentes/adjudicacion/DialogoAdjudicar"
import { DialogoDesierta } from "@/componentes/adjudicacion/DialogoDesierta"
import { Explicacion } from "@/componentes/adjudicacion/Explicacion"
import { AvisoRechazo } from "@/componentes/adjudicacion/PropuestaRechazada"
import { TablaCandidatos } from "@/componentes/adjudicacion/TablaCandidatos"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Termino } from "@/componentes/Termino"
import type { Evento } from "@/negociacion"
import { conPuntoFinal } from "@/tipos"

/**
 * Los acuerdos tentativos ordenados y explicados, con los pesos que el comprador quiera probar. El
 * comprador también adjudica a un candidato o declara desierta la negociación; `alAvisar` recibe el
 * resultado para el aviso de la página, `alConflicto` el texto de un 409 y `alEmpezar` avisa de que
 * se abrió un diálogo (el aviso de un conflicto anterior ya no viene al caso).
 */
export function SeccionEvaluacion({
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
  const esComprador = useRoles().includes("comprador")
  // Los pesos que se pidieron al recalcular; null, los configurados.
  const [pesos, setPesos] = useState<Pesos | null>(null)
  // Tras adjudicar o declarar desierta, lo que hay en caché es anterior a la decisión hasta que la
  // negociación se actualiza y esta sección desaparece: no se ofrece decidir otra vez.
  const [decidida, setDecidida] = useState(false)
  const consulta = useEvaluacion(evento.id, pesos, {
    // Al recalcular, la tabla anterior se queda a la vista hasta que llegue la nueva.
    placeholderData: keepPreviousData,
    // Una evaluación en caché con propuesta vigente es la foto de una propuesta pendiente (la
    // misma clave la guarda): siempre se vuelve a pedir la viva.
    refetchOnMount: (q) => (q.state.data?.vigente ? "always" : true),
  })
  // La última evaluación que llegó. Si el servicio rechaza otros pesos, la consulta nueva no tiene
  // datos (el marcador de posición solo sirve mientras carga): esta copia mantiene la tabla a la vista.
  const [ultima, setUltima] = useState<Evaluacion | undefined>()
  if (consulta.data && consulta.data !== ultima) setUltima(consulta.data)
  const evaluacion = consulta.data ?? ultima
  const recomendacion = evaluacion?.recomendacion
  // Las rechazadas vienen de la más reciente a la más antigua.
  const rechazada = evaluacion?.historial[0]
  // La evaluación viva nunca trae propuesta vigente. Si la que se tiene la trae, es la foto de una
  // propuesta ya decidida (p. ej. la que se acaba de rechazar): mientras llega la viva no se
  // muestra y, si la consulta no la trae, se ve sin acciones.
  const obsoleta = Boolean(evaluacion?.vigente)
  const conAcciones = esComprador && !obsoleta && !decidida
  // El servicio rechazó los pesos: se dice junto a los campos y la tabla anterior se queda.
  const errorPesos = consulta.isLoadingError
    ? erroresPorCampo(consulta.error).pesos
    : undefined
  const aviso = consulta.isPlaceholderData
    ? "Recalculando…"
    : errorPesos
      ? "Se muestran los resultados de los últimos pesos que se calcularon."
      : consulta.isRefetchError
        ? "No se pudo actualizar; se muestran los últimos datos recibidos."
        : ""

  let cuerpo
  if (consulta.isPending || (obsoleta && consulta.isFetching)) {
    cuerpo = <EstadoCarga />
  } else if (
    (consulta.isLoadingError && !errorPesos) ||
    (obsoleta && consulta.isError)
  ) {
    cuerpo = (
      <EstadoError
        error={consulta.error}
        alReintentar={() => void consulta.refetch()}
      />
    )
  } else if (evaluacion && !recomendacion) {
    // Tras declarar desierta, la evaluación sin acuerdos puede llegar antes que la negociación.
    cuerpo = decidida ? (
      <EstadoCarga />
    ) : (
      <EstadoVacio
        titulo="No hay acuerdos tentativos para evaluar."
        descripcion="Ninguna sesión terminó en un acuerdo tentativo, así que no hay propuestas que comparar."
      />
    )
  } else {
    cuerpo = (
      <div className="space-y-6">
        {rechazada && (
          <AvisoRechazo
            titulo="Se rechazó la última propuesta"
            propuesta={rechazada}
            evento={evento}
          />
        )}
        {recomendacion && (
          <TablaCandidatos
            recomendacion={recomendacion}
            evento={evento}
            accion={
              conAcciones
                ? (candidato) => (
                    <DialogoAdjudicar
                      evento={evento}
                      candidato={candidato}
                      recomendacion={recomendacion}
                      alConflicto={alConflicto}
                      alEmpezar={alEmpezar}
                      alAdjudicar={(resultado) => {
                        // Los pesos rechazados no deben quedar pedidos al invalidar las consultas.
                        setPesos(null)
                        setDecidida(true)
                        alAvisar(
                          resultado.vigente?.estado === "directa"
                            ? conPuntoFinal(
                                `Se adjudicó la negociación a ${candidato.nombre}`
                              )
                            : "Se envió la propuesta a un aprobador."
                        )
                      }}
                    />
                  )
                : undefined
            }
          />
        )}
        {recomendacion && <Explicacion recomendacion={recomendacion} />}
        <AjustarPesos
          pesos={pesos ?? recomendacion?.pesos ?? PESOS_POR_OMISION}
          error={errorPesos}
          alRecalcular={setPesos}
        />
      </div>
    )
  }

  return (
    <Seccion
      titulo="Evaluación"
      acciones={
        conAcciones && (
          <DialogoDesierta
            evento={evento}
            alConflicto={alConflicto}
            alEmpezar={alEmpezar}
            alDeclarar={() => {
              setDecidida(true)
              alAvisar("Se declaró desierta la negociación.")
            }}
          />
        )
      }
      descripcion={
        <>
          Los acuerdos tentativos, del mejor al peor. Cada uno se califica con
          su costo total, el <Termino clave="desempeno">desempeño</Termino> del
          proveedor, su riesgo y el <Termino clave="sla">SLA</Termino>. La
          recomendación es una guía: la{" "}
          <Termino clave="adjudicacion">adjudicación</Termino> es decisión suya.
        </>
      }
    >
      <p
        role="status"
        className={aviso ? "mb-2 text-sm text-muted-foreground" : "sr-only"}
      >
        {aviso}
      </p>
      {cuerpo}
    </Seccion>
  )
}
