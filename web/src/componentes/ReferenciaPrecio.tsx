import { Tags } from "lucide-react"
import { useEffect, useId, useRef, type FormEvent } from "react"
import { ErrorApi } from "@/api"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Termino } from "@/componentes/Termino"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  formatoDecimal,
  porUnidad,
  useInteligencia,
  type Referencia,
  type ServicioPrecios,
} from "@/inteligencia"
import { cn } from "@/lib/utils"
import { enteroPositivo, useParametros } from "@/parametros"
import { formatoMoneda } from "@/tipos"

const CANTIDAD_MAXIMA = 10_000_000 // las que acepta la API
const PLAZO_MAXIMO = 120

/** La cantidad de la URL si es un número mayor que 0 y no excede el máximo; si no, null. */
function cantidadValida(valor: string | null): string | null {
  const numero = Number(valor)
  return valor &&
    Number.isFinite(numero) &&
    numero > 0 &&
    numero <= CANTIDAD_MAXIMA
    ? valor
    : null
}

/** P25, P50 y P75 para la cantidad y el plazo de la URL, con el formulario para cambiarlos. */
export function ReferenciaPrecio({
  servicio,
  cantidadSugerida,
}: {
  servicio: ServicioPrecios
  cantidadSugerida: string
}) {
  const [parametros, actualizar] = useParametros()
  const cantidad =
    cantidadValida(parametros.get("cantidad")) ?? cantidadSugerida
  const plazo = enteroPositivo(parametros.get("plazo"), 12, PLAZO_MAXIMO)
  const idCantidad = useId()
  const idPlazo = useId()
  const formulario = useRef<HTMLFormElement>(null)
  // Atrás/Adelante cambian la URL pero React no toca un campo que la persona ya editó: reset()
  // devuelve cada campo a su `defaultValue`, que sí sigue a la URL, sin remontar el formulario.
  useEffect(() => {
    formulario.current?.reset()
  }, [cantidad, plazo])
  const referencia = useInteligencia<Referencia>(
    `/precios/servicios/${encodeURIComponent(servicio.codigo)}/referencia?${new URLSearchParams(
      { cantidad, plazo: String(plazo) }
    )}`
  )

  function calcular(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const datos = new FormData(evento.currentTarget)
    // El navegador ya bloquea los valores fuera de rango; esto cubre al que no lo haga.
    const nuevaCantidad = cantidadValida(String(datos.get("cantidad")))
    if (!nuevaCantidad) return
    actualizar({
      cantidad: nuevaCantidad,
      plazo: String(
        enteroPositivo(String(datos.get("plazo")), 12, PLAZO_MAXIMO)
      ),
    })
  }

  function resultado() {
    if (referencia.isPending) return <EstadoCarga filas={2} />
    if (referencia.isError) {
      if (
        referencia.error instanceof ErrorApi &&
        referencia.error.codigo === "sin_observaciones"
      ) {
        return (
          <EstadoVacio
            icono={Tags}
            titulo="Sin contratos recientes"
            descripcion="No hay contratos de este servicio en los últimos 24 meses: no se puede calcular su precio de referencia."
          />
        )
      }
      return (
        <EstadoError
          error={referencia.error}
          alReintentar={() => void referencia.refetch()}
        />
      )
    }
    const r = referencia.data
    const valores: [string, string, string][] = [
      ["P25", "Bajo", r.p25],
      ["P50", "Típico", r.p50],
      ["P75", "Alto", r.p75],
    ]
    return (
      <div className="space-y-3">
        <dl className="grid gap-3 sm:grid-cols-3">
          {valores.map(([clave, nombre, valor]) => (
            <div
              key={clave}
              className={cn(
                "rounded-lg border p-3",
                clave === "P50" && "border-accent"
              )}
            >
              <dt className="text-sm text-muted-foreground">
                {nombre} ({clave})
              </dt>
              <dd className="text-xl font-semibold tabular-nums">
                {formatoMoneda(valor, r.moneda)}
              </dd>
            </div>
          ))}
        </dl>
        <p className="text-sm text-muted-foreground">
          {/* Lo que dice la respuesta, no el formulario: así el precio nunca se lee con otra cantidad. */}
          {`Precio ${porUnidad(r.unidad)} para una cantidad de ${formatoDecimal(Number(r.cantidad), 4)} y un plazo de ${r.plazo} ${r.plazo === 1 ? "mes" : "meses"}. `}
          {r.metodo === "modelo" ? (
            `Calculado con el modelo de precios versión ${r.version}`
          ) : (
            <>
              Calculado con la <Termino clave="lineaBase">línea base</Termino>
            </>
          )}{" "}
          · {r.observaciones.toLocaleString("es-MX")} contratos comparables de
          los últimos 24 meses
          {r.confianza === "baja" && (
            <>
              {" "}
              ·{" "}
              <span className="text-warning">
                <Termino clave="bajaConfianza">baja confianza</Termino>
              </span>
            </>
          )}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Sin `key`: remontar el formulario al calcular sacaría el foco del botón. */}
      <form
        ref={formulario}
        onSubmit={calcular}
        className="flex flex-wrap items-end gap-3"
      >
        <div className="space-y-1">
          <Label htmlFor={idCantidad}>Cantidad</Label>
          <Input
            id={idCantidad}
            name="cantidad"
            type="number"
            inputMode="decimal"
            min="0.0001"
            max={CANTIDAD_MAXIMA}
            step="any"
            required
            defaultValue={cantidad}
            className="w-36"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor={idPlazo}>Plazo (meses)</Label>
          <Input
            id={idPlazo}
            name="plazo"
            type="number"
            inputMode="numeric"
            min={1}
            max={PLAZO_MAXIMO}
            step={1}
            required
            defaultValue={plazo}
            className="w-28"
          />
        </div>
        <Button type="submit">Calcular</Button>
      </form>
      {resultado()}
    </div>
  )
}
