import { onlineManager } from "@tanstack/react-query"
import { act, cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { Evaluacion } from "@/adjudicacion"
import { Negociacion } from "@/paginas/Negociacion"
import {
  CON_RECOMENDACION,
  EVALUACION,
  EVENTO,
  ID,
  RECOMENDACION,
  RUTA,
  propuesta,
  sesion,
} from "@/pruebas/evaluacion"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  llamadaA,
  renderizarPagina,
  respuestaDiferida,
  respuestaJson,
  simularRutas,
} from "@/pruebas/utilidades"
import { formatoMoneda } from "@/tipos"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const ADJUDICACION = `${RUTA}/adjudicacion`
const DESIERTA = `${RUTA}/desierta`
const JUSTIFICACION = "El costo es mayor, pero ofrece soporte local."
const MENSAJE_OBLIGATORIA =
  "Para elegir un proveedor distinto del recomendado, escriba la justificación (de 10 a 1,000 caracteres)."
const MENSAJE_LONGITUD = "La justificación debe tener de 10 a 1,000 caracteres."

function abrir() {
  return renderizarPagina(
    <>
      <Negociacion />
      <div id="contenido" tabIndex={-1} />
    </>,
    { ruta: `/negociaciones/${ID}`, patron: "/negociaciones/:id" }
  )
}

/** Abre la página con la evaluación y, opcionalmente, otra recomendación o sesiones. */
function abrirConEvaluacion(
  evaluacion: Evaluacion = CON_RECOMENDACION,
  evento: typeof EVENTO = EVENTO,
  rutas: Record<string, () => Response | Promise<Response>> = {}
) {
  const api = simularRutas({
    [`GET ${RUTA}`]: () => respuestaJson(evento),
    [`GET ${EVALUACION}`]: () => respuestaJson(evaluacion),
    ...rutas,
  })
  return { api, ...abrir() }
}

const nombreBoton = (proveedor: string) => `Adjudicar a ${proveedor}`

/** Abre la confirmación de un proveedor desde su fila de la tabla de candidatos. */
async function abrirDialogo(proveedor: string) {
  const tabla = await screen.findByRole("table", {
    name: "Candidatos de la evaluación",
  })
  await userEvent.click(
    within(tabla).getByRole("button", { name: nombreBoton(proveedor) })
  )
  return screen.findByRole("dialog", { name: nombreBoton(proveedor) })
}

beforeEach(() => {
  sesionDePrueba.roles = ["comprador"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  onlineManager.setOnline(true)
})

describe("Adjudicar", () => {
  it("anticipa la adjudicación directa con el costo y el umbral", async () => {
    abrirConEvaluacion()
    const dialogo = await abrirDialogo("Nube Norte")
    expect(dialogo).toHaveTextContent(
      `Se adjudicará directamente: el costo total (${formatoMoneda("480000.00", "MXN")}) no supera el umbral de aprobación (${formatoMoneda("500000.00", "MXN")}) y el acuerdo está dentro de sus límites.`
    )
    expect(
      within(dialogo).getByRole("button", { name: "Confirmar" })
    ).toBeInTheDocument()
  })

  it("un costo igual al umbral se adjudica directamente", async () => {
    abrirConEvaluacion({
      ...CON_RECOMENDACION,
      recomendacion: { ...RECOMENDACION, umbral_aprobacion: "480000.00" },
    })
    const dialogo = await abrirDialogo("Nube Norte")
    const monto = formatoMoneda("480000.00", "MXN")
    // Solo lo que lo supera pide aprobación (comparación estricta, como el servicio).
    expect(dialogo).toHaveTextContent(
      `Se adjudicará directamente: el costo total (${monto}) no supera el umbral de aprobación (${monto})`
    )
  })

  it("anticipa el aprobador por el umbral, por los límites o por los dos", async () => {
    const costo = formatoMoneda("510000.00", "MXN")
    const umbral = formatoMoneda("500000.00", "MXN")
    const casos: [string, Evaluacion, typeof EVENTO, string][] = [
      [
        "umbral",
        CON_RECOMENDACION,
        {
          ...EVENTO,
          sesiones: [
            sesion("s1", "Nube Norte", "acuerdo_tentativo"),
            sesion("s2", "Datos del Sur", "acuerdo_tentativo"),
          ],
        },
        `Irá a un aprobador porque el costo total (${costo}) supera el umbral de aprobación (${umbral}).`,
      ],
      [
        "límites",
        {
          ...CON_RECOMENDACION,
          recomendacion: { ...RECOMENDACION, umbral_aprobacion: "600000.00" },
        },
        EVENTO,
        "Irá a un aprobador porque el acuerdo está fuera de sus límites.",
      ],
      [
        "los dos",
        CON_RECOMENDACION,
        EVENTO,
        `Irá a un aprobador porque el costo total (${costo}) supera el umbral de aprobación (${umbral}) y el acuerdo está fuera de sus límites.`,
      ],
    ]
    for (const [, evaluacion, evento, texto] of casos) {
      abrirConEvaluacion(evaluacion, evento)
      const dialogo = await abrirDialogo("Datos del Sur")
      expect(dialogo).toHaveTextContent(texto)
      expect(dialogo).not.toHaveTextContent("Se adjudicará directamente")
      cleanup()
    }
  })

  it("pide la justificación solo si no es el recomendado", async () => {
    abrirConEvaluacion()
    const recomendado = await abrirDialogo("Nube Norte")
    expect(
      within(recomendado).queryByLabelText("Justificación")
    ).not.toBeInTheDocument()
    await userEvent.keyboard("{Escape}")
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    )

    const otro = await abrirDialogo("Datos del Sur")
    const campo = within(otro).getByLabelText("Justificación")
    expect(campo).toBeRequired()
    expect(campo).toHaveAccessibleDescription(
      "Explique por qué se aparta de la recomendación (de 10 a 1,000 caracteres)."
    )
  })

  it("valida la justificación antes de enviar y lo dice junto al campo", async () => {
    const { api } = abrirConEvaluacion()
    const dialogo = await abrirDialogo("Datos del Sur")
    const confirmar = within(dialogo).getByRole("button", { name: "Confirmar" })
    const campo = within(dialogo).getByLabelText("Justificación")

    await userEvent.click(confirmar)
    expect(within(dialogo).getByText(MENSAJE_OBLIGATORIA)).toBeInTheDocument()
    expect(campo).toBeInvalid()
    expect(campo).toHaveAccessibleDescription(
      expect.stringContaining(MENSAJE_OBLIGATORIA)
    )
    // El error del campo no es una región viva: el foco pasa al campo para que se lea.
    expect(campo).toHaveFocus()

    // Los espacios no cuentan: «corta» y espacios sobrantes siguen sin llegar a 10 caracteres.
    await userEvent.type(campo, "   corta   ")
    expect(within(dialogo).getByText(MENSAJE_LONGITUD)).toBeInTheDocument()
    await userEvent.click(confirmar)

    await userEvent.type(campo, " pero ya suficiente")
    expect(
      within(dialogo).queryByText(MENSAJE_LONGITUD)
    ).not.toBeInTheDocument()
    expect(
      api.mock.calls.filter(([, init]) => init?.method === "POST")
    ).toHaveLength(0)
  })

  it("manda la sesión, los pesos como texto y la justificación", async () => {
    const { api } = abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`POST ${ADJUDICACION}`]: () =>
        respuestaJson(propuesta("s2", "pendiente")),
    })
    const dialogo = await abrirDialogo("Datos del Sur")
    await userEvent.type(
      within(dialogo).getByLabelText("Justificación"),
      `  ${JUSTIFICACION}  `
    )
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Confirmar" })
    )
    await screen.findByText("Se envió la propuesta a un aprobador.")
    expect(llamadaA(api, ADJUDICACION, "POST").cuerpo).toEqual({
      sesion_id: "s2",
      pesos: "40,30,15,15",
      justificacion: JUSTIFICACION,
    })
  })

  it("al elegir al recomendado no manda justificación", async () => {
    const { api } = abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`POST ${ADJUDICACION}`]: () => respuestaJson(propuesta("s1", "directa")),
    })
    const dialogo = await abrirDialogo("Nube Norte")
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Confirmar" })
    )
    await screen.findByText("Se adjudicó la negociación a Nube Norte.")
    expect(llamadaA(api, ADJUDICACION, "POST").cuerpo).toEqual({
      sesion_id: "s1",
      pesos: "40,30,15,15",
    })
  })

  it("manda los pesos de la evaluación que se ve, no los que el servicio rechazó", async () => {
    const rechazados = `${EVALUACION}?pesos=30,30,30,10`
    // La negociación no cambia de estado: así se ve si la sección queda atorada en los pesos rechazados.
    const { api } = abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`GET ${rechazados}`]: () =>
        respuestaJson(
          {
            title: "Solicitud inválida",
            detail: "Revise los datos marcados.",
            codigo: "pesos_invalidos",
            errores: [{ campo: "pesos", mensaje: "Pesos inválidos." }],
          },
          422
        ),
      [`POST ${ADJUDICACION}`]: () => respuestaJson(propuesta("s1", "directa")),
    })
    for (const [i, nombre] of [
      "Costo total",
      "Desempeño",
      "Riesgo",
      "SLA",
    ].entries()) {
      const campo = await screen.findByLabelText(`Peso (${nombre})`)
      await userEvent.clear(campo)
      await userEvent.type(campo, ["30", "30", "30", "10"][i])
    }
    await userEvent.click(screen.getByRole("button", { name: "Recalcular" }))
    await screen.findByText(
      "Se muestran los resultados de los últimos pesos que se calcularon."
    )

    const dialogo = await abrirDialogo("Nube Norte")
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Confirmar" })
    )
    await screen.findByText("Se adjudicó la negociación a Nube Norte.")
    expect(llamadaA(api, ADJUDICACION, "POST").cuerpo).toEqual({
      sesion_id: "s1",
      pesos: "40,30,15,15",
    })
    // Tras la acción, la sección vuelve a los pesos configurados y ya no avisa del rechazo.
    await waitFor(() =>
      expect(
        screen.queryByText(
          "Se muestran los resultados de los últimos pesos que se calcularon."
        )
      ).not.toBeInTheDocument()
    )
  })

  it("un 422 de justificación queda junto al campo", async () => {
    const servicio =
      "Para elegir un proveedor distinto del recomendado, escriba la justificación (de 10 a 1,000 caracteres)."
    abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`POST ${ADJUDICACION}`]: () =>
        respuestaJson(
          {
            title: "Solicitud inválida",
            detail: "Revise los datos marcados.",
            codigo: "justificacion_requerida",
            errores: [{ campo: "justificacion", mensaje: servicio }],
          },
          422
        ),
    })
    const dialogo = await abrirDialogo("Datos del Sur")
    const campo = within(dialogo).getByLabelText("Justificación")
    await userEvent.type(campo, JUSTIFICACION)
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Confirmar" })
    )
    const mensaje = await within(dialogo).findByText(servicio)
    expect(campo).toBeInvalid()
    expect(campo.getAttribute("aria-describedby")).toContain(mensaje.id)
    expect(campo).toHaveFocus()
    // Es del campo: la región de avisos del diálogo no lo repite y el diálogo sigue abierto.
    expect(within(dialogo).getByRole("alert")).toBeEmptyDOMElement()
    expect(screen.getByRole("dialog")).toBe(dialogo)
  })

  it("los demás errores del servicio se muestran en el diálogo, que sigue abierto", async () => {
    const errores = [
      respuestaJson(
        {
          title: "Conflicto",
          detail: "La negociación ya no está en evaluación.",
          codigo: "estado_invalido",
        },
        409
      ),
      respuestaJson(
        {
          title: "Servicio no disponible",
          detail: "No se pudo consultar la recomendación; intente de nuevo.",
          codigo: "dependencia_no_disponible",
        },
        503
      ),
      respuestaJson(
        {
          title: "Solicitud inválida",
          detail: "Revise los datos marcados.",
          codigo: "sesion_no_candidata",
          errores: [
            {
              campo: "sesion_id",
              mensaje:
                "La sesión elegida no es un acuerdo tentativo de esta negociación.",
            },
          ],
        },
        422
      ),
    ]
    const { api } = abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`POST ${ADJUDICACION}`]: () => errores.shift()!,
    })
    const dialogo = await abrirDialogo("Nube Norte")
    const confirmar = within(dialogo).getByRole("button", { name: "Confirmar" })
    const alerta = within(dialogo).getByRole("alert")
    expect(alerta).toBeEmptyDOMElement()
    const lecturas = () => api.mock.calls.filter(([url]) => url === RUTA).length
    const antes = lecturas()

    await userEvent.click(confirmar)
    await waitFor(() =>
      expect(alerta).toHaveTextContent(
        "La negociación ya no está en evaluación."
      )
    )
    // El 409 dice que la negociación cambió: la página de atrás se actualiza.
    await waitFor(() => expect(lecturas()).toBe(antes + 1))
    await userEvent.click(confirmar)
    await waitFor(() =>
      expect(alerta).toHaveTextContent(
        "No se pudo consultar la recomendación; intente de nuevo."
      )
    )
    await userEvent.click(confirmar)
    await waitFor(() =>
      expect(alerta).toHaveTextContent(
        "La sesión elegida no es un acuerdo tentativo de esta negociación."
      )
    )
    expect(screen.getByRole("dialog")).toBe(dialogo)
    // El 503 y el 422 no cambian nada en el servicio: no hay nada que actualizar.
    expect(lecturas()).toBe(antes + 1)
    // Al cerrar y volver a abrir, el error anterior ya no está.
    await userEvent.keyboard("{Escape}")
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    )
    // Sin adjudicar, el botón sigue ahí y recupera el foco (no se manda al contenido).
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Adjudicar a Nube Norte" })
      ).toHaveFocus()
    )
    const otra = await abrirDialogo("Nube Norte")
    expect(within(otra).getByRole("alert")).toBeEmptyDOMElement()
  })

  it("un 409 que saca a la negociación de «En evaluación» deja el texto del servicio en la página y el foco en el contenido", async () => {
    const conflicto =
      "La negociación ya tiene una propuesta pendiente de aprobación."
    let otroComprador = false
    abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`GET ${RUTA}`]: () =>
        respuestaJson({
          ...EVENTO,
          estado: otroComprador ? "pendiente_aprobacion" : "en_evaluacion",
        }),
      [`POST ${ADJUDICACION}`]: () => {
        otroComprador = true
        return respuestaJson(
          { title: "Conflicto", detail: conflicto, codigo: "estado_invalido" },
          409
        )
      },
    })
    const dialogo = await abrirDialogo("Nube Norte")
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Confirmar" })
    )
    // La sección desaparece con su diálogo: el texto se queda en la región de avisos de la página.
    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: "Evaluación" })
      ).not.toBeInTheDocument()
    )
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(screen.getByText(conflicto)).toHaveAttribute("role", "status")
    await waitFor(() =>
      expect(document.getElementById("contenido")).toHaveFocus()
    )
  })

  it("un doble clic en Confirmar manda una sola propuesta", async () => {
    const lenta = respuestaDiferida()
    const { api } = abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`POST ${ADJUDICACION}`]: () => lenta.promesa,
    })
    const dialogo = await abrirDialogo("Nube Norte")
    const confirmar = within(dialogo).getByRole("button", { name: "Confirmar" })
    await userEvent.click(confirmar)
    await userEvent.click(confirmar)
    // aria-disabled y no disabled: el botón conserva el foco mientras se envía.
    expect(confirmar).toHaveAttribute("aria-disabled", "true")
    expect(confirmar).not.toBeDisabled()
    // Cerrar con la propuesta en camino reiniciaría el envío y dejaría mandar otra: no se cierra.
    await userEvent.keyboard("{Escape}")
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Volver" })
    )
    expect(screen.getByRole("dialog")).toBe(dialogo)
    expect(confirmar).toHaveAttribute("aria-disabled", "true")
    await act(async () =>
      lenta.resolver(respuestaJson(propuesta("s1", "directa")))
    )
    await screen.findByText("Se adjudicó la negociación a Nube Norte.")
    expect(
      api.mock.calls.filter(
        ([url, init]) => url === ADJUDICACION && init?.method === "POST"
      )
    ).toHaveLength(1)
  })

  it("al adjudicar avisa y el foco pasa al contenido", async () => {
    let adjudicada = false
    abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`GET ${RUTA}`]: () =>
        respuestaJson({
          ...EVENTO,
          estado: adjudicada ? "adjudicado" : "en_evaluacion",
        }),
      [`POST ${ADJUDICACION}`]: () => {
        adjudicada = true
        return respuestaJson(propuesta("s1", "directa"))
      },
    })
    const dialogo = await abrirDialogo("Nube Norte")
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Confirmar" })
    )
    const aviso = await screen.findByText(
      "Se adjudicó la negociación a Nube Norte."
    )
    expect(aviso).toHaveAttribute("role", "status")
    // La negociación salió de «En evaluación»: la sección y el botón que abrió el diálogo desaparecen.
    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: "Evaluación" })
      ).not.toBeInTheDocument()
    )
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    await waitFor(() =>
      expect(document.getElementById("contenido")).toHaveFocus()
    )
  })

  it("declarar desierta manda el motivo y avisa", async () => {
    let desierta = false
    const { api } = abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`GET ${RUTA}`]: () =>
        respuestaJson({
          ...EVENTO,
          estado: desierta ? "desierto" : "en_evaluacion",
        }),
      [`POST ${DESIERTA}`]: () => {
        desierta = true
        return respuestaJson({
          recomendacion: null,
          vigente: null,
          historial: [],
        })
      },
    })
    await userEvent.click(
      await screen.findByRole("button", { name: "Declarar desierta" })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Declarar desierta la negociación",
    })
    const motivo = within(dialogo).getByLabelText("Motivo")
    expect(motivo).toHaveAttribute("maxlength", "500")
    await userEvent.type(motivo, "Ninguna propuesta conviene")
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Declarar desierta" })
    )
    expect(
      await screen.findByText("Se declaró desierta la negociación.")
    ).toHaveAttribute("role", "status")
    expect(llamadaA(api, DESIERTA, "POST").cuerpo).toEqual({
      motivo: "Ninguna propuesta conviene",
    })
    await waitFor(() =>
      expect(document.getElementById("contenido")).toHaveFocus()
    )
  })

  it("el motivo de la desierta que el servicio rechaza queda junto al campo", async () => {
    abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`POST ${DESIERTA}`]: () =>
        respuestaJson(
          {
            title: "Solicitud inválida",
            detail: "Revise los datos marcados.",
            errores: [{ campo: "motivo", mensaje: "El motivo no es válido." }],
          },
          422
        ),
    })
    await userEvent.click(
      await screen.findByRole("button", { name: "Declarar desierta" })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Declarar desierta la negociación",
    })
    const motivo = within(dialogo).getByLabelText("Motivo")
    // Un motivo en blanco ya no llega al servicio (lo detiene la página): este sí.
    await userEvent.type(motivo, "Sin ofertas")
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Declarar desierta" })
    )
    const mensaje = await within(dialogo).findByText("El motivo no es válido.")
    expect(mensaje).toBeVisible()
    expect(motivo).toBeInvalid()
    expect(motivo.getAttribute("aria-describedby")).toContain(mensaje.id)
    // El error del campo no es una región viva: el foco pasa al campo para que se lea.
    expect(motivo).toHaveFocus()
    expect(within(dialogo).getByRole("alert")).toBeEmptyDOMElement()
  })

  it("un motivo en blanco al declarar desierta no se envía y se dice junto al campo", async () => {
    const { api } = abrirConEvaluacion()
    await userEvent.click(
      await screen.findByRole("button", { name: "Declarar desierta" })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Declarar desierta la negociación",
    })
    const motivo = within(dialogo).getByLabelText("Motivo")
    const confirmar = within(dialogo).getByRole("button", {
      name: "Declarar desierta",
    })
    // Sin motivo, y con solo espacios, se avisa en español y no se manda nada.
    await userEvent.click(confirmar)
    const mensaje = within(dialogo).getByText("Escriba el motivo.")
    expect(motivo).toBeInvalid()
    expect(motivo.getAttribute("aria-describedby")).toContain(mensaje.id)
    expect(motivo).toHaveFocus()
    await userEvent.type(motivo, "   ")
    await userEvent.click(confirmar)
    expect(within(dialogo).getByText("Escriba el motivo.")).toBeVisible()
    expect(
      api.mock.calls.filter(([, init]) => init?.method === "POST")
    ).toHaveLength(0)
    // Al escribir un motivo, el aviso se va.
    await userEvent.type(motivo, "Sin ofertas")
    expect(
      within(dialogo).queryByText("Escriba el motivo.")
    ).not.toBeInTheDocument()
  })

  it("cerrar «Declarar desierta» sin declarar devuelve el foco al botón", async () => {
    abrirConEvaluacion()
    await userEvent.click(
      await screen.findByRole("button", { name: "Declarar desierta" })
    )
    await screen.findByRole("dialog", {
      name: "Declarar desierta la negociación",
    })
    await userEvent.keyboard("{Escape}")
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    )
    // El botón sigue ahí (la negociación no cambió): recupera el foco y no se manda al contenido.
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Declarar desierta" })
      ).toHaveFocus()
    )
  })

  it("sin conexión, adjudicar termina con un aviso en el diálogo y se puede cerrar", async () => {
    abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`POST ${ADJUDICACION}`]: () =>
        Promise.reject(new TypeError("Failed to fetch")),
    })
    const dialogo = await abrirDialogo("Nube Norte")
    // Con la red caída la solicitud no se queda esperando: falla de inmediato y lo dice.
    onlineManager.setOnline(false)
    const confirmar = within(dialogo).getByRole("button", { name: "Confirmar" })
    await userEvent.click(confirmar)
    await waitFor(() =>
      expect(within(dialogo).getByRole("alert")).toHaveTextContent(
        "No se pudo conectar con el servidor; revise su conexión e intente de nuevo."
      )
    )
    expect(confirmar).toHaveAttribute("aria-disabled", "false")
    await userEvent.keyboard("{Escape}")
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    )
  })

  it("sin conexión, declarar desierta termina con un aviso en el diálogo y se puede cerrar", async () => {
    abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`POST ${DESIERTA}`]: () =>
        Promise.reject(new TypeError("Failed to fetch")),
    })
    await userEvent.click(
      await screen.findByRole("button", { name: "Declarar desierta" })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Declarar desierta la negociación",
    })
    await userEvent.type(
      within(dialogo).getByLabelText("Motivo"),
      "Sin ofertas"
    )
    onlineManager.setOnline(false)
    const confirmar = within(dialogo).getByRole("button", {
      name: "Declarar desierta",
    })
    await userEvent.click(confirmar)
    await waitFor(() =>
      expect(within(dialogo).getByRole("alert")).toHaveTextContent(
        "No se pudo conectar con el servidor; revise su conexión e intente de nuevo."
      )
    )
    expect(confirmar).toHaveAttribute("aria-disabled", "false")
    await userEvent.keyboard("{Escape}")
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    )
  })

  it("el aviso de un conflicto lleva el tono de conflicto y se borra al abrir otra confirmación", async () => {
    const conflicto = "La negociación ya no está en evaluación."
    abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`POST ${ADJUDICACION}`]: () =>
        respuestaJson(
          { title: "Conflicto", detail: conflicto, codigo: "estado_invalido" },
          409
        ),
    })
    const dialogo = await abrirDialogo("Nube Norte")
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Confirmar" })
    )
    // El texto está en el diálogo y en el aviso de la página (detrás del diálogo).
    await waitFor(() =>
      expect(
        screen.getAllByText(conflicto).map((e) => e.getAttribute("role"))
      ).toEqual(["status", "alert"])
    )
    const aviso = screen.getAllByText(conflicto)[0]
    expect(aviso).toHaveClass("text-warning")
    expect(aviso.querySelector("svg")).toHaveAttribute("aria-hidden", "true")
    await userEvent.keyboard("{Escape}")
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    )
    expect(screen.getByText(conflicto)).toHaveClass("text-warning")

    // Abrir cualquier confirmación borra el conflicto de antes.
    await abrirDialogo("Datos del Sur")
    expect(screen.queryByText(conflicto)).not.toBeInTheDocument()
  })

  it("un doble clic en Declarar desierta manda una sola solicitud y no deja cerrar mientras tanto", async () => {
    const lenta = respuestaDiferida()
    const { api } = abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`POST ${DESIERTA}`]: () => lenta.promesa,
    })
    await userEvent.click(
      await screen.findByRole("button", { name: "Declarar desierta" })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Declarar desierta la negociación",
    })
    await userEvent.type(
      within(dialogo).getByLabelText("Motivo"),
      "Sin ofertas"
    )
    const confirmar = within(dialogo).getByRole("button", {
      name: "Declarar desierta",
    })
    await userEvent.click(confirmar)
    await userEvent.click(confirmar)
    expect(confirmar).toHaveAttribute("aria-disabled", "true")
    expect(confirmar).not.toBeDisabled()
    await userEvent.keyboard("{Escape}")
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Volver" })
    )
    expect(screen.getByRole("dialog")).toBe(dialogo)
    await act(async () =>
      lenta.resolver(
        respuestaJson({ recomendacion: null, vigente: null, historial: [] })
      )
    )
    await screen.findByText("Se declaró desierta la negociación.")
    expect(
      api.mock.calls.filter(
        ([url, init]) => url === DESIERTA && init?.method === "POST"
      )
    ).toHaveLength(1)
  })

  it("un 409 al declarar desierta actualiza la página y deja el mensaje en el diálogo", async () => {
    const { api } = abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`POST ${DESIERTA}`]: () =>
        respuestaJson(
          {
            title: "Conflicto",
            detail: "La negociación ya no está en evaluación.",
            codigo: "estado_invalido",
          },
          409
        ),
    })
    const lecturas = () => api.mock.calls.filter(([url]) => url === RUTA).length
    await userEvent.click(
      await screen.findByRole("button", { name: "Declarar desierta" })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Declarar desierta la negociación",
    })
    const antes = lecturas()
    await userEvent.type(
      within(dialogo).getByLabelText("Motivo"),
      "Sin ofertas"
    )
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Declarar desierta" })
    )
    await waitFor(() =>
      expect(within(dialogo).getByRole("alert")).toHaveTextContent(
        "La negociación ya no está en evaluación."
      )
    )
    await waitFor(() => expect(lecturas()).toBe(antes + 1))
    expect(screen.getByRole("dialog")).toBe(dialogo)
  })

  it("un 409 al declarar desierta que saca a la negociación de «En evaluación» deja el texto en la página y el foco en el contenido", async () => {
    const conflicto = "La negociación ya no está en evaluación."
    let otroComprador = false
    abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`GET ${RUTA}`]: () =>
        respuestaJson({
          ...EVENTO,
          estado: otroComprador ? "adjudicado" : "en_evaluacion",
        }),
      [`POST ${DESIERTA}`]: () => {
        otroComprador = true
        return respuestaJson(
          { title: "Conflicto", detail: conflicto, codigo: "estado_invalido" },
          409
        )
      },
    })
    await userEvent.click(
      await screen.findByRole("button", { name: "Declarar desierta" })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Declarar desierta la negociación",
    })
    await userEvent.type(
      within(dialogo).getByLabelText("Motivo"),
      "Sin ofertas"
    )
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Declarar desierta" })
    )
    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: "Evaluación" })
      ).not.toBeInTheDocument()
    )
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(screen.getByText(conflicto)).toHaveAttribute("role", "status")
    await waitFor(() =>
      expect(document.getElementById("contenido")).toHaveFocus()
    )
  })

  it("quien no es comprador no ve Adjudicar ni Declarar desierta", async () => {
    sesionDePrueba.roles = ["aprobador"]
    abrirConEvaluacion()
    await screen.findByRole("table", { name: "Candidatos de la evaluación" })
    expect(
      screen.queryByRole("button", { name: /Adjudicar/ })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Declarar desierta" })
    ).not.toBeInTheDocument()
  })

  it("el comprador puede declarar desierta aunque no haya acuerdos que evaluar", async () => {
    abrirConEvaluacion({ recomendacion: null, vigente: null, historial: [] })
    await screen.findByText("No hay acuerdos tentativos para evaluar.")
    expect(
      screen.getByRole("button", { name: "Declarar desierta" })
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: /Adjudicar/ })
    ).not.toBeInTheDocument()
  })

  it("no tiene violaciones de axe con el diálogo abierto", async () => {
    abrirConEvaluacion()
    await abrirDialogo("Datos del Sur")
    await esperarSinViolaciones(document.body)
    await userEvent.keyboard("{Escape}")
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    )
    await userEvent.click(
      screen.getByRole("button", { name: "Declarar desierta" })
    )
    await screen.findByRole("dialog", {
      name: "Declarar desierta la negociación",
    })
    await esperarSinViolaciones(document.body)
  })
})
