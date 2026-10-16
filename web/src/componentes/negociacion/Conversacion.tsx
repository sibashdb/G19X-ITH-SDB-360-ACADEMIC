import { EstadoVacio } from "@/componentes/Estados"
import { ValoresOferta } from "@/componentes/negociacion/ValoresOferta"
import { formatoFechaHora } from "@/fechas"
import { cn } from "@/lib/utils"
import {
  NOMBRES_AUTOR,
  explicarDecision,
  type SesionDetalle,
} from "@/negociacion"

/** La conversación por ronda; cada respuesta del agente explica por qué respondió así. */
export function Conversacion({ datos }: { datos: SesionDetalle }) {
  const ofertas = new Map(datos.ofertas.map((o) => [o.id, o]))
  if (datos.mensajes.length === 0) {
    return (
      <EstadoVacio
        titulo="Aún no hay mensajes"
        descripcion="El proveedor todavía no envía su primera oferta."
      />
    )
  }
  return (
    <ol className="space-y-3">
      {datos.mensajes.map((m) => {
        const oferta = m.oferta_id ? ofertas.get(m.oferta_id) : undefined
        return (
          <li
            key={m.id}
            className={cn(
              "space-y-2 rounded-lg border p-3",
              m.autor === "proveedor" && "bg-muted/40"
            )}
          >
            <p className="flex flex-wrap gap-x-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">
                {NOMBRES_AUTOR[m.autor]}
              </span>
              {/* Ronda 0: lo que pasa antes de la primera oferta (por ejemplo, escalar). */}
              {m.ronda > 0 && <span>{`Ronda ${m.ronda}`}</span>}
              <span>{formatoFechaHora(m.fecha)}</span>
            </p>
            {m.texto && (
              <p className="text-sm break-words whitespace-pre-wrap">
                {m.texto}
              </p>
            )}
            {oferta && (
              <ValoresOferta
                valores={oferta.valores}
                lineas={datos.lineas}
                palancas={datos.palancas}
                moneda={datos.moneda}
              />
            )}
            {m.decision && (
              <details className="text-sm">
                <summary className="cursor-pointer rounded-sm text-accent outline-hidden focus-visible:ring-2 focus-visible:ring-ring">
                  ¿Por qué respondió esto?
                </summary>
                <p className="mt-1 text-muted-foreground">
                  {explicarDecision(m.decision)}
                </p>
              </details>
            )}
          </li>
        )
      })}
    </ol>
  )
}
