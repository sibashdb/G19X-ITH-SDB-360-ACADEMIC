import { Campo } from "@/componentes/negociacion/Campo"
import { Input } from "@/components/ui/input"
import { formatoDecimal, porUnidad } from "@/inteligencia"
import { PASOS, type ClavePalanca, type Valores } from "@/negociacion"

type Linea = { id: string; nombre: string; unidad: string; cantidad: string }
type Palanca = { clave: ClavePalanca; nombre: string; unidad: string }

/** Un valor vacío por línea y por palanca; el precio no es palanca aquí: va por línea. */
export function valoresVacios(lineas: Linea[], palancas: Palanca[]): Valores {
  return {
    precios: Object.fromEntries(lineas.map((l) => [l.id, ""])),
    palancas: Object.fromEntries(
      palancas.filter((p) => p.clave !== "precio").map((p) => [p.clave, ""])
    ),
  }
}

/** Solo lo capturado: un valor vacío no se manda y la API dice junto a su campo que falta. */
export function valoresCapturados(valores: Valores): Valores {
  const llenos = (registro: Record<string, string>) =>
    Object.fromEntries(
      Object.entries(registro)
        .map(([clave, valor]) => [clave, valor.trim()])
        .filter(([, valor]) => valor !== "")
    )
  return {
    precios: llenos(valores.precios),
    palancas: llenos(valores.palancas),
  }
}

/** Un campo por línea (precio unitario) y por palanca, con su unidad y la precisión de la spec §6.4. */
export function CamposValores({
  id,
  lineas,
  palancas,
  moneda,
  valores,
  alCambiar,
  errores,
  prefijo,
}: {
  id: string
  lineas: Linea[]
  palancas: Palanca[]
  moneda: string
  valores: Valores
  alCambiar: (valores: Valores) => void
  errores: Record<string, string>
  prefijo: string
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {lineas.map((l) => (
        <Campo
          key={l.id}
          id={`${id}-precio-${l.id}`}
          etiqueta={`Precio de ${l.nombre}`}
          ayuda={`${moneda} ${porUnidad(l.unidad)} · cantidad: ${formatoDecimal(Number(l.cantidad), 4)}`}
          error={errores[`${prefijo}.precios.${l.id}`]}
        >
          {(control) => (
            <Input
              {...control}
              type="number"
              inputMode="decimal"
              min="0.01"
              step={PASOS.precio}
              value={valores.precios[l.id] ?? ""}
              onChange={(e) =>
                alCambiar({
                  ...valores,
                  precios: { ...valores.precios, [l.id]: e.target.value },
                })
              }
            />
          )}
        </Campo>
      ))}
      {palancas
        .filter((p) => p.clave !== "precio")
        .map((p) => (
          <Campo
            key={p.clave}
            id={`${id}-${p.clave}`}
            etiqueta={`${p.nombre} (${p.unidad})`}
            error={errores[`${prefijo}.palancas.${p.clave}`]}
          >
            {(control) => (
              <Input
                {...control}
                type="number"
                inputMode="decimal"
                min="0"
                step={PASOS[p.clave]}
                value={valores.palancas[p.clave] ?? ""}
                onChange={(e) =>
                  alCambiar({
                    ...valores,
                    palancas: {
                      ...valores.palancas,
                      [p.clave]: e.target.value,
                    },
                  })
                }
              />
            )}
          </Campo>
        ))}
    </div>
  )
}
