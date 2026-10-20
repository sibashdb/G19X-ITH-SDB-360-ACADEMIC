import type { Recomendacion } from "@/adjudicacion"
import { conPuntoFinal } from "@/tipos"

/**
 * Por qué ganó el recomendado y qué pesos cambiarían el resultado, en las frases del servicio. Las
 * plantillas del servicio ponen su punto tras el nombre del proveedor, que puede terminar en uno.
 */
export function Explicacion({
  recomendacion,
}: {
  recomendacion: Recomendacion
}) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">Por qué se recomienda</h3>
      <div className="space-y-1 text-sm">
        {recomendacion.explicacion.map((frase, i) => (
          <p key={i}>{conPuntoFinal(frase)}</p>
        ))}
      </div>
    </div>
  )
}
