import type { Recomendacion } from "@/adjudicacion"

/** Por qué ganó el recomendado y qué pesos cambiarían el resultado, en las frases del servicio. */
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
          <p key={i}>{frase}</p>
        ))}
      </div>
    </div>
  )
}
