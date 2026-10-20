import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { FormularioAdjudicacion } from "@/componentes/FormularioAdjudicacion"
import {
  esperarSinViolaciones,
  llamadaA,
  renderizarPagina,
  respuestaJson,
  simularRutas,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const URL_CONFIGURACION = "/api/inteligencia/configuracion"
// La puntuación guardada no es la de omisión (30/20/20/15/15, riesgo 40, inflación 4.50): un PUT
// que la reescribiera con esos valores en vez de mandar los guardados no pasaría la prueba.
const CONFIGURACION = {
  peso_sla: 25,
  peso_resolucion: 25,
  peso_incidentes: 20,
  peso_entregas: 15,
  peso_satisfaccion: 15,
  umbral_riesgo: 45,
  inflacion_anual: "6.25",
  adjudicacion_costo: 40,
  adjudicacion_desempeno: 30,
  adjudicacion_riesgo: 15,
  adjudicacion_sla: 15,
  umbral_aprobacion: "500000.00",
  actualizado_en: null,
  actualizado_por: null,
}
const GUARDADO = "Se guardó la configuración de la adjudicación."

function problema422(campo: string, mensaje: string) {
  return respuestaJson(
    {
      title: "Solicitud inválida",
      detail: "Revise los campos indicados.",
      codigo: "pesos_invalidos",
      errores: [{ campo: `body.${campo}`, mensaje }],
    },
    422
  )
}

/** La configuración guardada; `guardar` responde el PUT. */
function api(guardar: () => Response = () => respuestaJson(CONFIGURACION)) {
  return simularRutas({
    [`GET ${URL_CONFIGURACION}`]: () => respuestaJson(CONFIGURACION),
    [`PUT ${URL_CONFIGURACION}`]: guardar,
  })
}

const hayPut = (simulado: ReturnType<typeof api>) =>
  simulado.mock.calls.some(
    ([, init]) => (init as RequestInit | undefined)?.method === "PUT"
  )

async function escribir(campo: HTMLElement, texto: string) {
  await userEvent.clear(campo)
  await userEvent.type(campo, texto)
}

/** El grupo de los pesos: el total y el aviso de los pesos viven juntos ahí. */
const grupoDePesos = () =>
  screen.getByRole("group", { name: /^Pesos de la recomendación/ })

const guardar = () =>
  userEvent.click(screen.getByRole("button", { name: "Guardar adjudicación" }))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("FormularioAdjudicacion", () => {
  it("muestra los pesos y el umbral guardados", async () => {
    api()
    renderizarPagina(<FormularioAdjudicacion />)

    expect(
      screen.getByRole("heading", { name: "Adjudicación" })
    ).toBeInTheDocument()
    expect(await screen.findByLabelText("Costo total")).toHaveValue(40)
    expect(screen.getByLabelText("Desempeño")).toHaveValue(30)
    expect(screen.getByLabelText("Riesgo")).toHaveValue(15)
    expect(screen.getByLabelText("SLA")).toHaveValue(15)
    expect(screen.getByText("Total: 100 de 100")).toBeInTheDocument()
    const umbral = screen.getByLabelText("Umbral de aprobación (MXN)")
    expect(umbral).toHaveValue(500000)
    expect(umbral).toHaveAttribute("inputmode", "decimal")
    expect(umbral).toHaveAttribute("min", "0")
    expect(umbral).toHaveAttribute("step", "0.01")
    expect(umbral).toHaveAccessibleDescription(
      "Una adjudicación con un costo total mayor necesita un aprobador."
    )
  })

  it("el total se actualiza al escribir", async () => {
    api()
    renderizarPagina(<FormularioAdjudicacion />)

    await escribir(await screen.findByLabelText("Costo total"), "45")

    expect(screen.getByText("Total: 105 de 100")).toBeInTheDocument()
    expect(screen.getByLabelText("SLA")).toHaveAccessibleDescription(
      "Total: 105 de 100"
    )
  })

  it("guardar manda la puntuación sin cambios y la adjudicación nueva", async () => {
    const simulado = api()
    renderizarPagina(<FormularioAdjudicacion />)

    await escribir(await screen.findByLabelText("Costo total"), "35")
    await escribir(screen.getByLabelText("Desempeño"), "35")
    await escribir(
      screen.getByLabelText("Umbral de aprobación (MXN)"),
      "750000.5"
    )
    await guardar()

    expect(await screen.findByText(GUARDADO)).toBeInTheDocument()
    expect(llamadaA(simulado, URL_CONFIGURACION, "PUT").cuerpo).toEqual({
      peso_sla: 25,
      peso_resolucion: 25,
      peso_incidentes: 20,
      peso_entregas: 15,
      peso_satisfaccion: 15,
      umbral_riesgo: 45,
      inflacion_anual: "6.25",
      adjudicacion_costo: 35,
      adjudicacion_desempeno: 35,
      adjudicacion_riesgo: 15,
      adjudicacion_sla: 15,
      umbral_aprobacion: "750000.5",
    })
  })

  it("al guardar invalida lo que depende de la configuración", async () => {
    api()
    const { cliente } = renderizarPagina(<FormularioAdjudicacion />)
    const invalidar = vi.spyOn(cliente, "invalidateQueries")
    await screen.findByLabelText("Costo total")

    await guardar()

    await screen.findByText(GUARDADO)
    expect(invalidar).toHaveBeenCalledWith({ queryKey: ["inteligencia"] })
  })

  it("pesos que no suman 100 no se envían", async () => {
    const simulado = api()
    renderizarPagina(<FormularioAdjudicacion />)

    await escribir(await screen.findByLabelText("Costo total"), "45")
    await guardar()

    expect(within(grupoDePesos()).getByRole("alert")).toHaveTextContent(
      "Los pesos deben sumar 100; ahora suman 105."
    )
    expect(hayPut(simulado)).toBe(false)
    expect(screen.queryByText(GUARDADO)).not.toBeInTheDocument()
  })

  it("un peso que no es un entero no se envía", async () => {
    const simulado = api()
    renderizarPagina(<FormularioAdjudicacion />)

    await escribir(await screen.findByLabelText("Costo total"), "39.5")
    await guardar()

    expect(within(grupoDePesos()).getByRole("alert")).toHaveTextContent(
      "Cada peso debe ser un número entero de 0 a 100."
    )
    expect(hayPut(simulado)).toBe(false)
  })

  it("sin umbral no se envía y lo pide junto al campo", async () => {
    const simulado = api()
    renderizarPagina(<FormularioAdjudicacion />)

    await userEvent.clear(
      await screen.findByLabelText("Umbral de aprobación (MXN)")
    )
    await guardar()

    const umbral = screen.getByLabelText("Umbral de aprobación (MXN)")
    expect(umbral).toHaveAttribute("aria-invalid", "true")
    expect(umbral).toHaveAccessibleDescription(
      /Escriba el umbral de aprobación\./
    )
    expect(hayPut(simulado)).toBe(false)
  })

  it("un 422 de pesos de adjudicación se muestra junto al total", async () => {
    api(() =>
      problema422("pesos_adjudicacion", "Los pesos deben sumar 100; suman 99.")
    )
    renderizarPagina(<FormularioAdjudicacion />)
    await screen.findByLabelText("Costo total")

    await guardar()

    // El aviso está siempre montado (vacío): se espera a que llegue el rechazo del servicio.
    const aviso = within(grupoDePesos()).getByRole("alert")
    await waitFor(() =>
      expect(aviso).toHaveTextContent("Los pesos deben sumar 100; suman 99.")
    )
    expect(
      within(grupoDePesos()).getByText("Total: 100 de 100")
    ).toBeInTheDocument()
    expect(screen.queryByText(GUARDADO)).not.toBeInTheDocument()

    // Corregir un peso retira el rechazo del servicio.
    await escribir(screen.getByLabelText("Costo total"), "41")
    await waitFor(() => expect(aviso).toBeEmptyDOMElement())
  })

  it("un 422 del umbral se muestra junto al campo", async () => {
    api(() => problema422("umbral_aprobacion", "Use a lo más dos decimales."))
    renderizarPagina(<FormularioAdjudicacion />)
    await screen.findByLabelText("Costo total")

    await guardar()

    const umbral = screen.getByLabelText("Umbral de aprobación (MXN)")
    await waitFor(() => expect(umbral).toHaveAttribute("aria-invalid", "true"))
    expect(umbral).toHaveAccessibleDescription(/Use a lo más dos decimales\./)
  })

  it("un fallo sin campo se muestra como aviso", async () => {
    api(() => new Response("", { status: 500 }))
    renderizarPagina(<FormularioAdjudicacion />)
    await screen.findByLabelText("Costo total")

    await guardar()

    expect(
      await screen.findByText(
        "El servicio no está disponible; intente más tarde."
      )
    ).toBeInTheDocument()
  })

  it("no tiene violaciones de axe", async () => {
    api()
    const { container } = renderizarPagina(<FormularioAdjudicacion />)
    await screen.findByLabelText("Costo total")
    await esperarSinViolaciones(container)
  })
})
