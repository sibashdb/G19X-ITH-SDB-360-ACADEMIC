import type { Adjudicacion } from "@/adjudicacion"
import { formatoFechaHora } from "@/fechas"
import type { Evento } from "@/negociacion"

/** El proveedor de una propuesta, como lo mostraba su foto; si falta, el de la sesión. */
export function proveedorDe(propuesta: Adjudicacion, evento: Evento): string {
  return (
    propuesta.recomendacion.candidatos.find((c) => c.id === propuesta.sesion_id)
      ?.nombre ??
    evento.sesiones.find((s) => s.id === propuesta.sesion_id)
      ?.proveedor_nombre ??
    "—"
  )
}

/** Quién actuó y cuándo: «Ana López, 22 oct 2026, 10:00 a.m.». */
export const quienYCuando = (nombre: string | null, iso: string | null) =>
  [nombre, iso && formatoFechaHora(iso)].filter(Boolean).join(", ") || "—"

/**
 * Una propuesta rechazada, en párrafos: el proveedor, quién la propuso, quién la rechazó (ambos con
 * fecha) y el motivo. Quien la contiene pone el marco y el `break-words` del motivo.
 */
export function PropuestaRechazada({
  propuesta,
  evento,
}: {
  propuesta: Adjudicacion
  evento: Evento
}) {
  return (
    <>
      <p className="font-medium">{proveedorDe(propuesta, evento)}</p>
      <p>
        Propuso{" "}
        {quienYCuando(propuesta.propuesta_por_nombre, propuesta.propuesta_en)}
      </p>
      <p>
        Rechazó{" "}
        {quienYCuando(propuesta.decidida_por_nombre, propuesta.decidida_en)}
      </p>
      {propuesta.motivo_rechazo && (
        <p>Motivo del rechazo: {propuesta.motivo_rechazo}</p>
      )}
    </>
  )
}
