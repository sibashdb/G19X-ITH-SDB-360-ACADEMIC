import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Configuracion } from "@/paginas/Configuracion"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaDiferida,
  respuestaJson,
  simularApi,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const CONFIGURACION = {
  peso_sla: 30,
  peso_resolucion: 20,
  peso_incidentes: 20,
  peso_entregas: 15,
  peso_satisfaccion: 15,
  umbral_riesgo: 40,
  inflacion_anual: "4.50",
  actualizado_en: null,
  actualizado_por: null,
}
const V2 = {
  version: 2,
  entrenado_en: "2026-10-10T18:00:00Z",
  origen: "manual",
  actor_nombre: "admin1",
  observaciones: 1520,
  datos_hasta: "2026-09-30",
  mape: "0.083000",
  mape_linea_base: "0.093000",
  cobertura: "0.520000",
  pinball: "0.010000",
  promovido: true,
}
const V3 = {
  ...V2,
  version: 3,
  origen: "automatico",
  actor_nombre: "Sistema (automático)",
  mape: "0.090000",
  mape_linea_base: "0.100000",
}
const MODELOS = {
  entrenando: false,
  activo: 2,
  en_uso: 2,
  ultimo_error: null,
  elementos: [V2],
}

type Respuesta = () => Response
type RespuestaDiferible = () => Response | Promise<Response>

/**
 * La configuración y los modelos. `guardar` responde el PUT (la URL es la misma que la del GET:
 * el primer pedido es la lectura). `entrenar` responde el POST y deja `despues` como estado de
 * los modelos.
 */
function api({
  guardar = () => respuestaJson(CONFIGURACION),
  modelos = MODELOS,
  entrenar = () => respuestaJson({ entrenando: true }, 202),
  despues = MODELOS,
}: {
  guardar?: Respuesta
  modelos?: object
  entrenar?: RespuestaDiferible
  despues?: object
} = {}) {
  let lecturas = 0
  let estado = modelos
  return simularApi((url) => {
    if (url === "/api/inteligencia/configuracion")
      return ++lecturas === 1 ? respuestaJson(CONFIGURACION) : guardar()
    if (url === "/api/inteligencia/modelos") return respuestaJson(estado)
    if (url === "/api/inteligencia/modelos/entrenar") {
      estado = despues
      return entrenar()
    }
    return new Response("", { status: 404 })
  })
}

/** El cuerpo del PUT de la configuración, si se envió. */
function cuerpoGuardado(simulado: ReturnType<typeof simularApi>) {
  const llamada = (simulado.mock.calls as unknown[][]).find(
    ([, init]) => (init as RequestInit | undefined)?.method === "PUT"
  )
  return llamada
    ? JSON.parse(String((llamada[1] as RequestInit).body))
    : undefined
}

const renderizar = () => renderizarPagina(<Configuracion />)

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  sesionDePrueba.roles = ["admin"]
})

describe("Configuracion", () => {
  it("muestra un esqueleto en cada sección mientras carga", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    renderizar()
    expect(await screen.findAllByRole("status")).toHaveLength(2)
  })

  it("muestra al administrador la puntuación y el modelo con sus términos", async () => {
    api()
    renderizar()
    expect(
      screen.getByRole("heading", { name: "Pesos de la puntuación" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("heading", { name: "Modelo de precios" })
    ).toBeInTheDocument()
    for (const termino of ["precio de referencia", "puntuación", "desempeño"]) {
      expect(screen.getByRole("button", { name: termino })).toBeInTheDocument()
    }
    expect(await screen.findByLabelText("Cumplimiento de SLA")).toHaveValue(30)
    expect(screen.getByText("Total: 100 de 100")).toBeInTheDocument()
    expect(
      screen.getByText(
        "Son los valores iniciales: nadie los ha cambiado todavía."
      )
    ).toBeInTheDocument()
  })

  it("bloquea a quien no es administrador", () => {
    sesionDePrueba.roles = ["comprador"]
    renderizar()
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
    expect(
      screen.queryByRole("heading", { name: "Pesos de la puntuación" })
    ).not.toBeInTheDocument()
  })

  it("no guarda si los pesos no suman 100 y dice cuánto suman", async () => {
    const simulado = api()
    renderizar()
    const sla = await screen.findByLabelText("Cumplimiento de SLA")

    await userEvent.clear(sla)
    await userEvent.type(sla, "35")
    expect(screen.getByText("Total: 105 de 100")).toBeInTheDocument()
    await userEvent.click(
      screen.getByRole("button", { name: "Guardar cambios" })
    )

    expect(
      screen.getByText("Los pesos deben sumar 100; ahora suman 105.")
    ).toBeInTheDocument()
    expect(cuerpoGuardado(simulado)).toBeUndefined()
  })

  it("guarda la configuración y lo confirma", async () => {
    const simulado = api()
    renderizar()
    const sla = await screen.findByLabelText("Cumplimiento de SLA")
    const satisfaccion = screen.getByLabelText("Satisfacción")

    await userEvent.clear(sla)
    await userEvent.type(sla, "35")
    await userEvent.clear(satisfaccion)
    await userEvent.type(satisfaccion, "10")
    await userEvent.click(
      screen.getByRole("button", { name: "Guardar cambios" })
    )

    expect(
      await screen.findByText(
        "Configuración guardada. Las puntuaciones y las alertas ya usan los valores nuevos."
      )
    ).toBeInTheDocument()
    expect(cuerpoGuardado(simulado)).toEqual({
      peso_sla: 35,
      peso_resolucion: 20,
      peso_incidentes: 20,
      peso_entregas: 15,
      peso_satisfaccion: 10,
      umbral_riesgo: 40,
      inflacion_anual: "4.50",
    })
  })

  it("muestra junto al campo el error del servicio", async () => {
    api({
      guardar: () =>
        respuestaJson(
          {
            title: "Solicitud inválida",
            detail: "Revise los campos indicados.",
            errores: [
              {
                campo: "body.inflacion_anual",
                mensaje: "Use a lo más dos decimales.",
              },
            ],
          },
          422
        ),
    })
    renderizar()
    await screen.findByLabelText("Cumplimiento de SLA")

    await userEvent.click(
      screen.getByRole("button", { name: "Guardar cambios" })
    )

    const inflacion = screen.getByLabelText("Inflación anual (%)")
    await waitFor(() =>
      expect(inflacion).toHaveAttribute("aria-invalid", "true")
    )
    expect(inflacion).toHaveAccessibleDescription(
      /Use a lo más dos decimales\./
    )
  })

  it("muestra el modelo en uso y su registro", async () => {
    api()
    renderizar()
    const modelo = screen
      .getByRole("heading", { name: "Modelo de precios" })
      .closest<HTMLElement>("[data-slot=card]")!

    expect(await within(modelo).findByText("Versión 2")).toBeInTheDocument()
    expect(within(modelo).getByText("Manual · admin1")).toBeInTheDocument()
    expect(within(modelo).getAllByText("8.3 %")).not.toHaveLength(0)
    expect(within(modelo).getByText("En uso")).toBeInTheDocument()
  })

  it("avisa si el modelo promovido no está en uso", async () => {
    api({ modelos: { ...MODELOS, en_uso: null } })
    renderizar()
    expect(
      await screen.findByText("El modelo promovido no está en uso")
    ).toBeInTheDocument()
  })

  it("reentrena y muestra el resultado", async () => {
    api({
      despues: { ...MODELOS, activo: 3, en_uso: 3, elementos: [V3, V2] },
    })
    renderizar()
    await screen.findByText("Versión 2")

    await userEvent.click(
      screen.getByRole("button", { name: "Reentrenar modelo de precios" })
    )

    expect(
      await screen.findByText(
        "Versión 3: MAPE 9.0 % (línea base 10.0 %). Se promovió: ahora calcula el precio de referencia."
      )
    ).toBeInTheDocument()
  })

  it("un entrenamiento que falla muestra el motivo", async () => {
    api({
      despues: {
        ...MODELOS,
        ultimo_error:
          "No hay datos suficientes para entrenar. Solo hay 12 líneas de contrato.",
      },
    })
    renderizar()
    await screen.findByText("Versión 2")

    await userEvent.click(
      screen.getByRole("button", { name: "Reentrenar modelo de precios" })
    )

    expect(
      await screen.findByText(
        "No se pudo entrenar: No hay datos suficientes para entrenar. Solo hay 12 líneas de contrato."
      )
    ).toBeInTheDocument()
  })

  it("mientras se pide el entrenamiento no muestra el fallo del anterior", async () => {
    const ERROR_ANTERIOR =
      "No hay datos suficientes para entrenar. Solo hay 12 líneas de contrato."
    const post = respuestaDiferida()
    api({
      modelos: { ...MODELOS, ultimo_error: ERROR_ANTERIOR },
      entrenar: () => post.promesa,
      despues: { ...MODELOS, activo: 3, en_uso: 3, elementos: [V3, V2] },
    })
    renderizar()
    await screen.findByText("Versión 2")

    await userEvent.click(
      screen.getByRole("button", { name: "Reentrenar modelo de precios" })
    )

    expect(
      await screen.findByText(
        "Entrenando el modelo de precios; puede tardar un minuto."
      )
    ).toBeInTheDocument()
    expect(screen.queryByText(/No se pudo entrenar/)).not.toBeInTheDocument()

    post.resolver(respuestaJson({ entrenando: true }, 202))

    expect(
      await screen.findByText(
        "Versión 3: MAPE 9.0 % (línea base 10.0 %). Se promovió: ahora calcula el precio de referencia."
      )
    ).toBeInTheDocument()
    expect(screen.queryByText(/No se pudo entrenar/)).not.toBeInTheDocument()
    expect(
      screen.queryByText(
        "Entrenando el modelo de precios; puede tardar un minuto."
      )
    ).not.toBeInTheDocument()
  })

  it("si ya hay un entrenamiento en curso lo explica", async () => {
    api({
      entrenar: () =>
        respuestaJson(
          {
            title: "Conflicto",
            detail:
              "Ya hay un entrenamiento del modelo de precios en curso; espere a que termine.",
            codigo: "entrenamiento_en_curso",
          },
          409
        ),
    })
    renderizar()
    await screen.findByText("Versión 2")

    await userEvent.click(
      screen.getByRole("button", { name: "Reentrenar modelo de precios" })
    )

    expect(
      await screen.findByText(
        "Ya hay un entrenamiento del modelo de precios en curso; espere a que termine."
      )
    ).toBeInTheDocument()
  })

  it("mientras entrena lo dice y el botón queda marcado como no disponible", async () => {
    api({ modelos: { ...MODELOS, entrenando: true } })
    renderizar()
    expect(
      await screen.findByText(
        "Entrenando el modelo de precios; puede tardar un minuto."
      )
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Reentrenar modelo de precios" })
    ).toHaveAttribute("aria-disabled", "true")
  })

  it("no tiene violaciones de accesibilidad", async () => {
    api()
    const { container } = renderizar()
    await screen.findByText("Versión 2")
    await screen.findByLabelText("Cumplimiento de SLA")
    await esperarSinViolaciones(container)
  })
})
