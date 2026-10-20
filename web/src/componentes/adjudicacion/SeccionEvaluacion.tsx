import { keepPreviousData } from "@tanstack/react-query"
import { useState } from "react"
import { PESOS_POR_OMISION, useEvaluacion, type Pesos } from "@/adjudicacion"
import { erroresPorCampo } from "@/api"
import { AjustarPesos } from "@/componentes/adjudicacion/AjustarPesos"
import { Explicacion } from "@/componentes/adjudicacion/Explicacion"
import { TablaCandidatos } from "@/componentes/adjudicacion/TablaCandidatos"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Termino } from "@/componentes/Termino"
import type { Evento } from "@/negociacion"

/** Los acuerdos tentativos ordenados y explicados, con los pesos que el comprador quiera probar. */
export function SeccionEvaluacion({ evento }: { evento: Evento }) {
  // Los pesos que se pidieron al recalcular; null, los configurados.
  const [pesos, setPesos] = useState<Pesos | null>(null)
  const consulta = useEvaluacion(evento.id, pesos, {
    // Al recalcular, la tabla anterior se queda a la vista hasta que llegue la nueva.
    placeholderData: keepPreviousData,
  })
  const recomendacion = consulta.data?.recomendacion
  // El servicio rechazó los pesos: se dice junto a los campos y no sustituye a la evaluación.
  const errorPesos = consulta.isLoadingError
    ? erroresPorCampo(consulta.error).pesos
    : undefined
  const aviso = consulta.isPlaceholderData
    ? "Recalculando…"
    : consulta.isRefetchError
      ? "No se pudo actualizar; se muestran los últimos datos recibidos."
      : ""

  let cuerpo
  if (consulta.isPending) {
    cuerpo = <EstadoCarga />
  } else if (consulta.isLoadingError && !errorPesos) {
    cuerpo = (
      <EstadoError
        error={consulta.error}
        alReintentar={() => void consulta.refetch()}
      />
    )
  } else if (consulta.data && !recomendacion) {
    cuerpo = (
      <EstadoVacio
        titulo="No hay acuerdos tentativos para evaluar."
        descripcion="Ninguna sesión terminó en un acuerdo tentativo, así que no hay propuestas que comparar."
      />
    )
  } else {
    cuerpo = (
      <div className="space-y-6">
        {recomendacion && (
          <TablaCandidatos recomendacion={recomendacion} evento={evento} />
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
      descripcion={
        <>
          Los acuerdos tentativos, del mejor al peor. Cada uno se califica con
          su costo total, el <Termino clave="desempeno">desempeño</Termino> del
          proveedor, su riesgo y el <Termino clave="sla">SLA</Termino>. La
          recomendación es una guía: la decisión es suya.
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
