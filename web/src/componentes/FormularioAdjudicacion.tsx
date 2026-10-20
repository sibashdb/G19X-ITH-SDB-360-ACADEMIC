import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Check, CircleAlert } from "lucide-react"
import { useId, useState, type FormEvent } from "react"
import {
  CRITERIOS,
  mensajePesos,
  NOMBRES_CRITERIO,
  pesosValidos,
  totalPesos,
  type Criterio,
} from "@/adjudicacion"
import { enviarJson, erroresPorCampo, pedir } from "@/api"
import { useToken } from "@/auth"
import { CampoNumero } from "@/componentes/CampoNumero"
import { ContenidoConsulta } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  GUARDAR_CONFIGURACION,
  useConfiguracionOcupada,
  useInteligencia,
  type ConfiguracionInteligencia,
} from "@/inteligencia"
import { cn } from "@/lib/utils"

function Formulario({ inicial }: { inicial: ConfiguracionInteligencia }) {
  const token = useToken()
  const cliente = useQueryClient()
  const idTotal = useId()
  const [pesos, setPesos] = useState(
    () =>
      Object.fromEntries(
        CRITERIOS.map((criterio) => [
          criterio,
          String(inicial[`adjudicacion_${criterio}` as const]),
        ])
      ) as Record<Criterio, string>
  )
  const [umbral, setUmbral] = useState(inicial.umbral_aprobacion)
  const [intentado, setIntentado] = useState(false)
  const total = totalPesos(pesos)
  const validos = pesosValidos(pesos)
  const monto = umbral.trim()
  const ocupada = useConfiguracionOcupada()
  const guardar = useMutation({
    mutationKey: GUARDAR_CONFIGURACION,
    mutationFn: (datos: Record<string, number | string>) =>
      pedir<ConfiguracionInteligencia>(
        "/inteligencia/configuracion",
        token,
        enviarJson("PUT", datos)
      ),
    // Los pesos y el umbral los lee también la evaluación de cada negociación.
    onSuccess: () => cliente.invalidateQueries({ queryKey: ["inteligencia"] }),
  })
  const errores = erroresPorCampo(guardar.error)
  const errorTotal =
    errores.pesos_adjudicacion ?? (intentado ? mensajePesos(pesos) : undefined)
  const errorUmbral =
    errores.umbral_aprobacion ??
    (intentado && monto === "" ? "Escriba el umbral de aprobación." : undefined)

  /** Cualquier edición retira el rechazo y el aviso anteriores. */
  function editado() {
    setIntentado(false)
    guardar.reset()
  }

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (ocupada) return
    setIntentado(true)
    if (!validos || monto === "") return
    // El servicio exige también la puntuación: se manda la guardada, no lo que se edite arriba.
    guardar.mutate({
      peso_sla: inicial.peso_sla,
      peso_resolucion: inicial.peso_resolucion,
      peso_incidentes: inicial.peso_incidentes,
      peso_entregas: inicial.peso_entregas,
      peso_satisfaccion: inicial.peso_satisfaccion,
      umbral_riesgo: inicial.umbral_riesgo,
      inflacion_anual: inicial.inflacion_anual,
      adjudicacion_costo: validos.costo,
      adjudicacion_desempeno: validos.desempeno,
      adjudicacion_riesgo: validos.riesgo,
      adjudicacion_sla: validos.sla,
      umbral_aprobacion: monto,
    })
  }

  return (
    // noValidate: el aviso lo da la página, en español y junto a los campos, no el navegador.
    <form noValidate onSubmit={enviar} className="space-y-5">
      <fieldset className="space-y-3">
        <legend className="text-sm font-medium">
          Pesos de la recomendación (deben sumar 100)
        </legend>
        <div className="grid gap-3 sm:grid-cols-2">
          {CRITERIOS.map((criterio) => (
            <CampoNumero
              key={criterio}
              nombre={`adjudicacion_${criterio}`}
              etiqueta={NOMBRES_CRITERIO[criterio]}
              error={errores[`adjudicacion_${criterio}`]}
              min={0}
              max={100}
              step={1}
              inputMode="numeric"
              value={pesos[criterio]}
              aria-describedby={idTotal}
              onChange={(evento) => {
                setPesos({ ...pesos, [criterio]: evento.target.value })
                editado()
              }}
            />
          ))}
        </div>
        <p
          id={idTotal}
          aria-live="polite"
          aria-atomic="true"
          className={cn(
            "flex items-center gap-1 text-sm font-medium",
            validos ? "text-success" : "text-destructive"
          )}
        >
          {validos ? (
            <Check aria-hidden className="size-4" />
          ) : (
            <CircleAlert aria-hidden className="size-4" />
          )}
          {`Total: ${total} de 100`}
        </p>
        <p
          role="alert"
          className={errorTotal ? "text-sm text-destructive" : "sr-only"}
        >
          {errorTotal}
        </p>
      </fieldset>
      <CampoNumero
        nombre="umbral_aprobacion"
        etiqueta="Umbral de aprobación (MXN)"
        ayuda="Una adjudicación con un costo total mayor necesita un aprobador."
        error={errorUmbral}
        min={0}
        step={0.01}
        inputMode="decimal"
        className="w-48"
        value={umbral}
        onChange={(evento) => {
          setUmbral(evento.target.value)
          editado()
        }}
      />
      {guardar.isError && Object.keys(errores).length === 0 && (
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertDescription>{guardar.error.message}</AlertDescription>
        </Alert>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" aria-disabled={ocupada}>
          {guardar.isPending ? "Guardando…" : "Guardar adjudicación"}
        </Button>
        <p
          role="status"
          className="flex items-center gap-1 text-sm text-success"
        >
          {guardar.isSuccess && (
            <>
              <Check aria-hidden className="size-4" />
              Se guardó la configuración de la adjudicación.
            </>
          )}
        </p>
      </div>
    </form>
  )
}

/** Pesos de la recomendación y umbral de aprobación en MXN. */
export function FormularioAdjudicacion() {
  const configuracion =
    useInteligencia<ConfiguracionInteligencia>("/configuracion")
  return (
    <Seccion
      titulo="Adjudicación"
      descripcion="Cuánto pesa cada criterio al recomendar a quién adjudicar, y desde qué costo total (el umbral de aprobación) una adjudicación necesita un aprobador."
    >
      <ContenidoConsulta consulta={configuracion}>
        {(datos) => <Formulario inicial={datos} />}
      </ContenidoConsulta>
    </Seccion>
  )
}
