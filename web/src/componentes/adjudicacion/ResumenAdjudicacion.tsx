import { useId, type ReactNode } from "react"
import { useEvaluacion, type Adjudicacion } from "@/adjudicacion"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Termino } from "@/componentes/Termino"
import { formatoFechaHora } from "@/fechas"
import type { Evento } from "@/negociacion"
import { formatoMoneda } from "@/tipos"

/** El proveedor de una propuesta, como lo mostraba su foto; si falta, el de la sesión. */
function proveedorDe(propuesta: Adjudicacion, evento: Evento): string {
  return (
    propuesta.recomendacion.candidatos.find((c) => c.id === propuesta.sesion_id)
      ?.nombre ??
    evento.sesiones.find((s) => s.id === propuesta.sesion_id)
      ?.proveedor_nombre ??
    "—"
  )
}

/** Quién actuó y cuándo: «Ana López, 22 oct 2026, 10:00 a.m.». */
const quienYCuando = (nombre: string | null, iso: string | null) =>
  [nombre, iso && formatoFechaHora(iso)].filter(Boolean).join(", ") || "—"

/** Lo que se adjudicó: proveedor, costo, quién propuso y aprobó, y el folio del contrato. */
function DatosAdjudicacion({
  vigente,
  evento,
}: {
  vigente: Adjudicacion
  evento: Evento
}) {
  const datos: [string, ReactNode][] = [
    ["Proveedor", proveedorDe(vigente, evento)],
    [
      "Costo total",
      <>
        {formatoMoneda(vigente.costo_total, evento.moneda)}
        {evento.moneda === "USD" && (
          <span className="block text-xs text-muted-foreground">
            ≈ {formatoMoneda(vigente.costo_total_mxn, "MXN")}
          </span>
        )}
      </>,
    ],
    [
      "Propuso",
      quienYCuando(vigente.propuesta_por_nombre, vigente.propuesta_en),
    ],
    [
      "Aprobó",
      vigente.estado === "directa"
        ? "Adjudicación directa del comprador"
        : quienYCuando(vigente.decidida_por_nombre, vigente.decidida_en),
    ],
    [
      "Folio del contrato",
      vigente.contrato_folio ? (
        <span className="font-mono">{vigente.contrato_folio}</span>
      ) : (
        "—"
      ),
    ],
  ]
  return (
    <dl className="grid gap-3 text-sm sm:grid-cols-2">
      {datos.map(([titulo, valor]) => (
        <div key={titulo}>
          <dt className="text-muted-foreground">{titulo}</dt>
          <dd className="font-medium break-words">{valor}</dd>
        </div>
      ))}
    </dl>
  )
}

/**
 * Cómo terminó una negociación «Adjudicada» o «Desierta», de solo lectura: quién propuso y quién
 * aprobó, el proveedor, el costo y el folio del contrato (o por qué quedó desierta) y las
 * propuestas que se rechazaron antes. Lee la foto que guardó la propuesta vigente.
 */
export function ResumenAdjudicacion({ evento }: { evento: Evento }) {
  const idRechazadas = useId()
  // «always»: la evaluación en caché puede ser anterior a la decisión (la propuesta aún pendiente).
  const consulta = useEvaluacion(evento.id, null, { refetchOnMount: "always" })
  const evaluacion = consulta.data
  const vigente = evaluacion?.vigente
  const desierto = evento.estado === "desierto"
  const lista =
    evaluacion !== undefined &&
    (desierto ||
      vigente?.estado === "aprobada" ||
      vigente?.estado === "directa")

  let cuerpo: ReactNode
  if (consulta.isPending || (!lista && consulta.isFetching)) {
    cuerpo = <EstadoCarga />
  } else if (!lista && consulta.isError) {
    cuerpo = (
      <EstadoError
        error={consulta.error}
        alReintentar={() => void consulta.refetch()}
      />
    )
  } else if (!lista) {
    cuerpo = (
      <EstadoVacio
        titulo="No se encontró el detalle de la adjudicación."
        descripcion="Actualice la página para ver el estado más reciente."
      />
    )
  } else {
    cuerpo = (
      <div className="space-y-6">
        {desierto ? (
          <div className="space-y-1 text-sm">
            <p className="font-medium">
              La negociación se declaró{" "}
              <Termino clave="desierta">desierta</Termino>.
            </p>
            <p className="break-words">
              {evento.motivo_desierta
                ? `Motivo: ${evento.motivo_desierta}`
                : "Ningún proveedor llegó a un acuerdo tentativo."}
            </p>
          </div>
        ) : (
          vigente && <DatosAdjudicacion vigente={vigente} evento={evento} />
        )}
        {evaluacion.historial.length > 0 && (
          <div className="space-y-2">
            <h3 id={idRechazadas} className="text-sm font-semibold">
              Propuestas rechazadas
            </h3>
            <ul aria-labelledby={idRechazadas} className="space-y-3 text-sm">
              {evaluacion.historial.map((p) => (
                <li
                  key={p.id}
                  className="space-y-0.5 rounded-lg border p-3 break-words"
                >
                  <p className="font-medium">{proveedorDe(p, evento)}</p>
                  <p>
                    Propuso{" "}
                    {quienYCuando(p.propuesta_por_nombre, p.propuesta_en)}
                  </p>
                  <p>
                    Rechazó {quienYCuando(p.decidida_por_nombre, p.decidida_en)}
                  </p>
                  {p.motivo_rechazo && (
                    <p>Motivo del rechazo: {p.motivo_rechazo}</p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    )
  }

  return (
    <Seccion
      titulo="Resultado"
      descripcion={
        desierto
          ? undefined
          : "La propuesta que se adjudicó y quién la decidió."
      }
    >
      {cuerpo}
    </Seccion>
  )
}
