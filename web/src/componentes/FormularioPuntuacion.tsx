import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Check, CircleAlert } from "lucide-react"
import { useId, useState, type FormEvent } from "react"
import { enviarJson, erroresPorCampo, pedir } from "@/api"
import { useToken } from "@/auth"
import { CampoNumero } from "@/componentes/CampoNumero"
import { ContenidoConsulta } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Termino } from "@/componentes/Termino"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { formatoFechaHora } from "@/fechas"
import { useInteligencia, type ConfiguracionInteligencia } from "@/inteligencia"
import { cn } from "@/lib/utils"

const PESOS = [
  ["peso_sla", "Cumplimiento de SLA"],
  ["peso_resolucion", "Tiempo de resolución"],
  ["peso_incidentes", "Incidentes críticos"],
  ["peso_entregas", "Entregas a tiempo"],
  ["peso_satisfaccion", "Satisfacción"],
] as const
type ClavePeso = (typeof PESOS)[number][0]

function Formulario({ inicial }: { inicial: ConfiguracionInteligencia }) {
  const token = useToken()
  const cliente = useQueryClient()
  const idTotal = useId()
  const [pesos, setPesos] = useState(
    () =>
      Object.fromEntries(
        PESOS.map(([clave]) => [clave, String(inicial[clave])])
      ) as Record<ClavePeso, string>
  )
  const [intentado, setIntentado] = useState(false)
  // Los pesos son enteros: sumarlos aquí no es operar montos.
  const total = PESOS.reduce(
    (suma, [clave]) => suma + (Number(pesos[clave]) || 0),
    0
  )
  const guardar = useMutation({
    mutationFn: (datos: Record<string, number | string>) =>
      pedir<ConfiguracionInteligencia>(
        "/inteligencia/configuracion",
        token,
        enviarJson("PUT", datos)
      ),
    // La puntuación, el ranking, las alertas y el Tablero dependen de esta configuración.
    onSuccess: () => cliente.invalidateQueries({ queryKey: ["inteligencia"] }),
  })
  const errores = erroresPorCampo(guardar.error)
  const errorTotal =
    errores.pesos ??
    (intentado && total !== 100
      ? `Los pesos deben sumar 100; ahora suman ${total}.`
      : undefined)

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (guardar.isPending) return
    setIntentado(true)
    if (total !== 100) return
    const datos = new FormData(evento.currentTarget)
    guardar.mutate({
      ...Object.fromEntries(
        PESOS.map(([clave]) => [clave, Number(pesos[clave])])
      ),
      umbral_riesgo: Number(datos.get("umbral_riesgo")),
      inflacion_anual: String(datos.get("inflacion_anual")),
    })
  }

  return (
    <form onSubmit={enviar} className="space-y-5">
      <fieldset className="space-y-3">
        <legend className="text-sm font-medium">Pesos (deben sumar 100)</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          {PESOS.map(([clave, etiqueta]) => (
            <CampoNumero
              key={clave}
              nombre={clave}
              etiqueta={etiqueta}
              error={errores[clave]}
              min={0}
              max={100}
              step={1}
              inputMode="numeric"
              value={pesos[clave]}
              aria-describedby={idTotal}
              onChange={(evento) => {
                setPesos({ ...pesos, [clave]: evento.target.value })
                guardar.reset()
              }}
            />
          ))}
        </div>
        <p
          id={idTotal}
          aria-live="polite"
          className={cn(
            "flex items-center gap-1 text-sm font-medium",
            total === 100 ? "text-success" : "text-destructive"
          )}
        >
          {total === 100 ? (
            <Check aria-hidden className="size-4" />
          ) : (
            <CircleAlert aria-hidden className="size-4" />
          )}
          Total: {total} de 100
        </p>
        {errorTotal && (
          <p role="alert" className="text-sm text-destructive">
            {errorTotal}
          </p>
        )}
      </fieldset>
      <div className="grid gap-3 sm:grid-cols-2">
        <CampoNumero
          nombre="umbral_riesgo"
          etiqueta="Umbral de riesgo"
          ayuda="Un proveedor con menos puntos queda en riesgo."
          error={errores.umbral_riesgo}
          min={0}
          max={100}
          step={1}
          inputMode="numeric"
          defaultValue={inicial.umbral_riesgo}
          onChange={() => guardar.reset()}
        />
        <CampoNumero
          nombre="inflacion_anual"
          etiqueta="Inflación anual (%)"
          ayuda="Lleva los precios de la línea base a pesos de hoy."
          error={errores.inflacion_anual}
          min={0}
          max={50}
          step={0.01}
          inputMode="decimal"
          defaultValue={inicial.inflacion_anual}
          onChange={() => guardar.reset()}
        />
      </div>
      {guardar.isError && Object.keys(errores).length === 0 && (
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertDescription>{guardar.error.message}</AlertDescription>
        </Alert>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" aria-disabled={guardar.isPending}>
          {guardar.isPending ? "Guardando…" : "Guardar cambios"}
        </Button>
        <p
          role="status"
          className="flex items-center gap-1 text-sm text-success"
        >
          {guardar.isSuccess && (
            <>
              <Check aria-hidden className="size-4" />
              Configuración guardada. Las puntuaciones y las alertas ya usan los
              valores nuevos.
            </>
          )}
        </p>
      </div>
      <p className="text-xs text-muted-foreground">
        {inicial.actualizado_en
          ? `Última modificación: ${formatoFechaHora(inicial.actualizado_en)}, por ${inicial.actualizado_por}.`
          : "Son los valores iniciales: nadie los ha cambiado todavía."}
      </p>
    </form>
  )
}

/** Pesos de la puntuación, umbral de riesgo e inflación de la línea base. */
export function FormularioPuntuacion() {
  const configuracion =
    useInteligencia<ConfiguracionInteligencia>("/configuracion")
  return (
    <Seccion
      titulo="Pesos de la puntuación"
      descripcion={
        <>
          Cuánto pesa cada aspecto del{" "}
          <Termino clave="desempeno">desempeño</Termino>, desde qué{" "}
          <Termino clave="puntuacion">puntuación</Termino> un proveedor queda en
          riesgo y la inflación que usa la línea base.
        </>
      }
    >
      <ContenidoConsulta consulta={configuracion}>
        {(datos) => <Formulario inicial={datos} />}
      </ContenidoConsulta>
    </Seccion>
  )
}
