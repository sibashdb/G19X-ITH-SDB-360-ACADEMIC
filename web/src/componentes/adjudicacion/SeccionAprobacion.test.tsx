import { onlineManager, useQueryClient } from "@tanstack/react-query"
import { act, cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useState, type ReactNode } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { Evaluacion } from "@/adjudicacion"
import { SeccionAprobacion } from "@/componentes/adjudicacion/SeccionAprobacion"
import { formatoFechaHora } from "@/fechas"
import type { Evento } from "@/negociacion"
import { Negociacion } from "@/paginas/Negociacion"
import {
  CON_RECOMENDACION,
  EVALUACION,
  EVENTO,
  ID,
  RECOMENDACION,
  RUTA,
  propuesta,
} from "@/pruebas/evaluacion"
import { USUARIO_DE_PRUEBA, sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  llamadaA,
  renderizarPagina,
  respuestaDiferida,
  respuestaJson,
  simularRutas,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const APROBAR = `${RUTA}/adjudicacion/aprobar`
const RECHAZAR = `${RUTA}/adjudicacion/rechazar`

const PROPUESTA_EN = "2026-10-22T16:00:00Z"
const JUSTIFICACION = "El costo es mayor, pero ofrece soporte local."
const DISTINTA =
  "La propuesta cambió desde que usted la abrió. Revise la propuesta vigente antes de decidir."
const ESTADO_INVALIDO = "La negociación ya no está pendiente de aprobación."
const SIN_RED =
  "No se pudo conectar con el servidor; revise su conexión e intente de nuevo."

/** La propuesta pendiente de otra persona (Luis Pérez): quien ve la pantalla es Ana López, `ana-1`. */
const DE_LUIS = propuesta("s2", "pendiente", {
  propuesta_por_id: "luis-2",
  propuesta_por_nombre: "Luis Pérez",
  justificacion: JUSTIFICACION,
  costo_total: "510000.00",
  costo_total_mxn: "510000.00",
  motivo_aprobacion: ["umbral", "fuera_de_limites"],
})
/** La propuesta de quien ve la pantalla. */
const DE_ANA = propuesta("s2", "pendiente", {
  propuesta_por_id: USUARIO_DE_PRUEBA,
  motivo_aprobacion: ["fuera_de_limites"],
})
/** Otra propuesta que sustituye a la anterior (se rechazó y se propuso de nuevo). */
const DE_MARTA = propuesta("s1", "pendiente", {
  id: "a2",
  propuesta_por_id: "marta-3",
  propuesta_por_nombre: "Marta Ruiz",
  propuesta_en: "2026-10-23T09:30:00Z",
  motivo_aprobacion: ["umbral"],
})

const PENDIENTE = { ...EVENTO, estado: "pendiente_aprobacion" }

const problema = (estado: number, codigo: string, detalle: string) =>
  respuestaJson(
    {
      title: estado === 403 ? "Sin permiso" : "Conflicto",
      detail: detalle,
      codigo,
    },
    estado
  )

function abrir() {
  return renderizarPagina(
    <>
      <Negociacion />
      <div id="contenido" tabIndex={-1} />
    </>,
    { ruta: `/negociaciones/${ID}`, patron: "/negociaciones/:id" }
  )
}

/** Abre la página con la negociación pendiente de aprobación y la evaluación indicada. */
function abrirPendiente(
  evaluacion: Evaluacion = DE_LUIS,
  rutas: Record<string, () => Response | Promise<Response>> = {}
) {
  const api = simularRutas({
    [`GET ${RUTA}`]: () => respuestaJson(PENDIENTE),
    [`GET ${EVALUACION}`]: () => respuestaJson(evaluacion),
    ...rutas,
  })
  return { api, ...abrir() }
}

const TITULO = "Propuesta pendiente de aprobación"
/** Espera a que la sección muestre la propuesta (no solo su título). */
const seccion = async () => {
  await screen.findByRole("heading", { name: TITULO })
  return screen.findByRole("table", { name: "Candidatos de la evaluación" })
}
const aprobar = () => screen.getByRole("button", { name: "Aprobar" })
const rechazar = () => screen.getByRole("button", { name: "Rechazar" })
const revisarNueva = () =>
  screen.getByRole("button", { name: "Revisar la propuesta nueva" })

/** Las llamadas POST que llegaron a una ruta. */
const envios = (api: ReturnType<typeof simularRutas>, url: string) =>
  api.mock.calls.filter(([u, init]) => u === url && init?.method === "POST")
const lecturas = (api: ReturnType<typeof simularRutas>, url: string) =>
  api.mock.calls.filter(([u, init]) => u === url && !init?.method).length

/** Abre «Rechazar» y devuelve el diálogo. */
async function abrirRechazo() {
  await userEvent.click(rechazar())
  return screen.findByRole("dialog", { name: "Rechazar la propuesta" })
}
const confirmarRechazo = (dialogo: HTMLElement) =>
  within(dialogo).getByRole("button", { name: "Rechazar propuesta" })

/** Monta a sus hijos con la evaluación de `evaluacion` ya en caché (y vencida): lo que queda de una visita anterior. */
function ConCache({
  evaluacion,
  children,
}: {
  evaluacion: Evaluacion
  children: ReactNode
}) {
  const cliente = useQueryClient()
  useState(() =>
    cliente.setQueryData(
      ["negociacion", `/eventos/${ID}/evaluacion`],
      evaluacion
    )
  )
  return children
}

beforeEach(() => {
  sesionDePrueba.roles = ["aprobador"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  onlineManager.setOnline(true)
})

describe("Pendiente de aprobación", () => {
  it("la propuesta pendiente se muestra con la foto guardada", async () => {
    const { api } = abrirPendiente()
    const tabla = await seccion()
    // La foto guardada: la evaluación se pide sin «?pesos».
    expect(lecturas(api, EVALUACION)).toBe(1)
    expect(
      api.mock.calls.filter(([url]) => String(url).includes("pesos"))
    ).toHaveLength(0)

    // Solo la fila de la propuesta lleva «Propuesta», con el recomendado y las marcas de cada fila.
    expect(within(tabla).getAllByText("Propuesta")).toHaveLength(1)
    const propuesta = within(
      within(tabla).getByText("Datos del Sur").closest("tr")!
    )
    expect(propuesta.getByText("Propuesta")).toBeInTheDocument()
    expect(propuesta.getByText("Fuera de límites")).toBeInTheDocument()
    expect(
      within(within(tabla).getByText("Nube Norte").closest("tr")!).getByText(
        "Recomendado"
      )
    ).toBeInTheDocument()

    // Quién propuso, cuándo, por qué y por qué pide aprobación.
    expect(
      screen.getByText(
        `Propuesta de Luis Pérez, ${formatoFechaHora(PROPUESTA_EN)}`
      )
    ).toBeInTheDocument()
    expect(screen.getByText(JUSTIFICACION)).toBeInTheDocument()
    const motivos = within(
      screen.getByRole("list", { name: "Por qué requiere aprobación" })
    )
      .getAllByRole("listitem")
      .map((m) => m.textContent)
    expect(motivos).toEqual([
      "Supera el umbral de aprobación",
      "Fuera de límites",
    ])
    for (const frase of RECOMENDACION.explicacion)
      expect(screen.getByText(frase)).toBeInTheDocument()

    // Las sesiones siguen debajo; esta pantalla no adjudica ni recalcula.
    expect(
      screen.getByRole("heading", { name: "Sesiones" })
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("heading", { name: "Evaluación" })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: /Adjudicar/ })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Recalcular" })
    ).not.toBeInTheDocument()
  })

  it("sin justificación no la muestra", async () => {
    abrirPendiente(propuesta("s1", "pendiente", { propuesta_por_id: "luis-2" }))
    await seccion()
    expect(screen.queryByText(/Justificación/)).not.toBeInTheDocument()
  })

  it("cada rol ve solo sus acciones", async () => {
    const PROPUSO = "Usted propuso esta adjudicación; la aprueba otra persona."
    const ESPERA = "Esperando aprobación de un aprobador."
    const casos: [
      string[],
      Evaluacion,
      "botones" | typeof PROPUSO | typeof ESPERA,
    ][] = [
      // Otra persona con el rol de aprobador decide.
      [["aprobador"], DE_LUIS, "botones"],
      [["comprador", "aprobador"], DE_LUIS, "botones"],
      // Quien propuso no decide, aunque tenga el rol de aprobador.
      [["comprador", "aprobador"], DE_ANA, PROPUSO],
      [["aprobador"], DE_ANA, PROPUSO],
      [["comprador"], DE_ANA, PROPUSO],
      // Los demás esperan.
      [["comprador"], DE_LUIS, ESPERA],
      [["admin"], DE_LUIS, ESPERA],
    ]
    for (const [roles, evaluacion, esperado] of casos) {
      sesionDePrueba.roles = roles
      abrirPendiente(evaluacion)
      await seccion()
      const caso = `${roles.join("+")} / ${evaluacion.vigente!.propuesta_por_nombre}`
      expect(
        screen.queryByRole("button", { name: "Aprobar" }) !== null,
        caso
      ).toBe(esperado === "botones")
      expect(
        screen.queryByRole("button", { name: "Rechazar" }) !== null,
        caso
      ).toBe(esperado === "botones")
      for (const texto of [PROPUSO, ESPERA]) {
        expect(screen.queryByText(texto) !== null, `${caso}: ${texto}`).toBe(
          texto === esperado
        )
      }
      cleanup()
    }
  })

  it("aprobar manda el id de la propuesta vista y avisa con el tono de éxito", async () => {
    let aprobada = false
    const { api } = abrirPendiente(DE_LUIS, {
      [`GET ${RUTA}`]: () =>
        respuestaJson({
          ...EVENTO,
          estado: aprobada ? "adjudicado" : "pendiente_aprobacion",
        }),
      [`POST ${APROBAR}`]: () => {
        aprobada = true
        return respuestaJson(propuesta("s2", "aprobada"))
      },
    })
    await seccion()
    await userEvent.click(aprobar())
    const aviso = await screen.findByText("Se aprobó la adjudicación.")
    expect(aviso).toHaveAttribute("role", "status")
    expect(aviso).toHaveClass("text-success")
    expect(aviso.querySelector("svg")).toBeNull()
    expect(llamadaA(api, APROBAR, "POST").cuerpo).toEqual({
      adjudicacion_id: "a1",
    })
  })

  it("al aprobar avisa y el foco pasa al contenido", async () => {
    let aprobada = false
    abrirPendiente(DE_LUIS, {
      [`GET ${RUTA}`]: () =>
        respuestaJson({
          ...EVENTO,
          estado: aprobada ? "adjudicado" : "pendiente_aprobacion",
        }),
      [`POST ${APROBAR}`]: () => {
        aprobada = true
        return respuestaJson(propuesta("s2", "aprobada"))
      },
    })
    await seccion()
    await userEvent.click(aprobar())
    await screen.findByText("Se aprobó la adjudicación.")
    // La negociación salió de «Pendiente de aprobación»: la sección y sus botones desaparecen.
    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: TITULO })
      ).not.toBeInTheDocument()
    )
    expect(
      screen.queryByRole("button", { name: "Aprobar" })
    ).not.toBeInTheDocument()
    expect(document.getElementById("contenido")).toHaveFocus()
  })

  it("un doble clic en Aprobar manda una sola aprobación", async () => {
    const lenta = respuestaDiferida()
    const { api } = abrirPendiente(DE_LUIS, {
      [`POST ${APROBAR}`]: () => lenta.promesa,
    })
    await seccion()
    const boton = aprobar()
    await userEvent.click(boton)
    await userEvent.click(boton)
    // aria-disabled y no disabled: el botón conserva el foco mientras se envía.
    expect(boton).toHaveAttribute("aria-disabled", "true")
    expect(boton).not.toBeDisabled()
    await act(async () =>
      lenta.resolver(respuestaJson(propuesta("s2", "aprobada")))
    )
    await screen.findByText("Se aprobó la adjudicación.")
    expect(envios(api, APROBAR)).toHaveLength(1)
  })

  it("rechazar exige el motivo y manda el id de la propuesta vista", async () => {
    let rechazada = false
    const { api } = abrirPendiente(DE_LUIS, {
      [`GET ${RUTA}`]: () =>
        respuestaJson({
          ...EVENTO,
          estado: rechazada ? "en_evaluacion" : "pendiente_aprobacion",
        }),
      [`GET ${EVALUACION}`]: () =>
        respuestaJson(rechazada ? CON_RECOMENDACION : DE_LUIS),
      [`POST ${RECHAZAR}`]: () => {
        rechazada = true
        return respuestaJson({
          recomendacion: null,
          vigente: null,
          historial: [],
        })
      },
    })
    await seccion()
    const dialogo = await abrirRechazo()
    const motivo = within(dialogo).getByLabelText("Motivo del rechazo")
    expect(motivo).toBeRequired()
    expect(motivo).toHaveAttribute("maxlength", "500")

    // Sin motivo (o solo con espacios) no se envía, y se dice junto al campo.
    await userEvent.type(motivo, "   ")
    await userEvent.click(confirmarRechazo(dialogo))
    const mensaje = within(dialogo).getByText("Escriba el motivo.")
    expect(motivo).toBeInvalid()
    expect(motivo.getAttribute("aria-describedby")).toContain(mensaje.id)
    expect(motivo).toHaveFocus()
    expect(envios(api, RECHAZAR)).toHaveLength(0)

    await userEvent.type(motivo, "  El costo es alto  ")
    expect(
      within(dialogo).queryByText("Escriba el motivo.")
    ).not.toBeInTheDocument()
    await userEvent.click(confirmarRechazo(dialogo))
    const aviso = await screen.findByText(
      "Se rechazó la propuesta; la negociación vuelve a evaluación."
    )
    expect(aviso).toHaveAttribute("role", "status")
    expect(llamadaA(api, RECHAZAR, "POST").cuerpo).toEqual({
      adjudicacion_id: "a1",
      motivo: "El costo es alto",
    })
    // Vuelve a evaluación: aparece «Evaluación», sin la propuesta, y el foco pasa al contenido.
    expect(
      await screen.findByRole("heading", { name: "Evaluación" })
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("heading", { name: TITULO })
    ).not.toBeInTheDocument()
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    await waitFor(() =>
      expect(document.getElementById("contenido")).toHaveFocus()
    )
  })

  it("si la propuesta cambia detrás del diálogo, el diálogo desaparece con las acciones y no se decide nada", async () => {
    let cambio = false
    const { api, cliente } = abrirPendiente(DE_LUIS, {
      [`GET ${EVALUACION}`]: () => respuestaJson(cambio ? DE_MARTA : DE_LUIS),
    })
    await seccion()
    const dialogo = await abrirRechazo()
    await userEvent.type(
      within(dialogo).getByLabelText("Motivo del rechazo"),
      "El costo es alto"
    )
    // La evaluación se actualiza con el diálogo abierto y trae la propuesta de Marta, que nadie revisó.
    cambio = true
    await act(async () => {
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
    })
    await screen.findByText(/Propuesta de Marta Ruiz/)
    // Las acciones se reemplazan por el aviso del cambio y el diálogo se va con ellas.
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    )
    expect(
      screen.queryByRole("button", { name: "Rechazar" })
    ).not.toBeInTheDocument()
    expect(revisarNueva()).toBeInTheDocument()
    expect(envios(api, RECHAZAR)).toHaveLength(0)
  })

  it("un 409 de propuesta distinta explica, recarga la evaluación y no decide", async () => {
    let cambio = false
    const { api } = abrirPendiente(DE_LUIS, {
      [`GET ${EVALUACION}`]: () => respuestaJson(cambio ? DE_MARTA : DE_LUIS),
      [`POST ${APROBAR}`]: () => {
        cambio = true
        return problema(409, "propuesta_distinta", DISTINTA)
      },
    })
    await seccion()
    await userEvent.click(aprobar())
    // El texto del servicio queda en la página, con el tono de conflicto (icono y texto, no solo color).
    const aviso = await screen.findByText(DISTINTA)
    expect(aviso).toHaveAttribute("role", "status")
    expect(aviso).toHaveClass("text-warning")
    expect(aviso.querySelector("svg")).toHaveAttribute("aria-hidden", "true")
    // La evaluación se recarga: aparece la propuesta nueva y no se decidió nada.
    expect(
      await screen.findByText(
        `Propuesta de Marta Ruiz, ${formatoFechaHora("2026-10-23T09:30:00Z")}`
      )
    ).toBeInTheDocument()
    expect(lecturas(api, EVALUACION)).toBe(2)
    expect(envios(api, APROBAR)).toHaveLength(1)
    expect(envios(api, RECHAZAR)).toHaveLength(0)
    // Las acciones se reemplazan por el aviso del cambio, y ahí recibe el foco el aprobador.
    expect(
      screen.queryByRole("button", { name: "Aprobar" })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Rechazar" })
    ).not.toBeInTheDocument()
    await waitFor(() => expect(revisarNueva()).toHaveFocus())
    expect(revisarNueva()).toHaveAccessibleDescription(
      /La propuesta cambió mientras usted la revisaba/
    )
  })

  it("un segundo clic apresurado tras el 409 no aprueba la propuesta nueva", async () => {
    let cambio = false
    const { api } = abrirPendiente(DE_LUIS, {
      [`GET ${EVALUACION}`]: () => respuestaJson(cambio ? DE_MARTA : DE_LUIS),
      [`POST ${APROBAR}`]: () => {
        cambio = true
        return problema(409, "propuesta_distinta", DISTINTA)
      },
    })
    await seccion()
    const boton = aprobar()
    // Dos clics seguidos: la segunda aprobación no sale mientras la primera está en camino.
    await userEvent.dblClick(boton)
    await screen.findByText(/Propuesta de Marta Ruiz/)
    // Con la propuesta nueva a la vista, nada ofrece decidir en el lugar de «Aprobar»: un clic más
    // (del dedo que seguía ahí) no llega a ninguna acción.
    await userEvent.click(boton)
    expect(
      screen.queryByRole("button", { name: "Aprobar" })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Rechazar" })
    ).not.toBeInTheDocument()
    expect(
      envios(api, APROBAR).map(([, init]) => JSON.parse(String(init?.body)))
    ).toEqual([{ adjudicacion_id: "a1" }])
  })

  it("tras un conflicto, «Revisar la propuesta nueva» devuelve las acciones y aprobar manda la propuesta nueva", async () => {
    let cambio = false
    let intentos = 0
    const { api } = abrirPendiente(DE_LUIS, {
      [`GET ${EVALUACION}`]: () => respuestaJson(cambio ? DE_MARTA : DE_LUIS),
      [`POST ${APROBAR}`]: () => {
        intentos += 1
        if (intentos === 1) {
          cambio = true
          return problema(409, "propuesta_distinta", DISTINTA)
        }
        return respuestaJson(propuesta("s1", "aprobada"))
      },
    })
    await seccion()
    await userEvent.click(aprobar())
    await screen.findByText(DISTINTA)
    await userEvent.click(
      await screen.findByRole("button", { name: "Revisar la propuesta nueva" })
    )

    // El aviso del cambio se va, las acciones vuelven y el foco pasa al título (no a <body>).
    expect(
      screen.queryByRole("button", { name: "Revisar la propuesta nueva" })
    ).not.toBeInTheDocument()
    expect(screen.getByRole("heading", { name: TITULO })).toHaveFocus()
    // El conflicto anterior ya no viene al caso.
    expect(screen.queryByText(DISTINTA)).not.toBeInTheDocument()
    await userEvent.click(aprobar())
    await screen.findByText("Se aprobó la adjudicación.")
    expect(llamadaA(api, APROBAR, "POST").cuerpo).toEqual({
      adjudicacion_id: "a2",
    })
    expect(envios(api, APROBAR)).toHaveLength(2)
  })

  it("un 409 de propuesta distinta al rechazar cierra el diálogo, explica y recarga", async () => {
    let cambio = false
    const { api } = abrirPendiente(DE_LUIS, {
      [`GET ${EVALUACION}`]: () => respuestaJson(cambio ? DE_MARTA : DE_LUIS),
      [`POST ${RECHAZAR}`]: () => {
        cambio = true
        return problema(409, "propuesta_distinta", DISTINTA)
      },
    })
    await seccion()
    const dialogo = await abrirRechazo()
    await userEvent.type(
      within(dialogo).getByLabelText("Motivo del rechazo"),
      "El costo es alto"
    )
    await userEvent.click(confirmarRechazo(dialogo))
    const aviso = await screen.findByText(DISTINTA)
    expect(aviso).toHaveAttribute("role", "status")
    expect(aviso).toHaveClass("text-warning")
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    )
    expect(
      await screen.findByText(/Propuesta de Marta Ruiz/)
    ).toBeInTheDocument()
    expect(lecturas(api, EVALUACION)).toBe(2)
    expect(envios(api, RECHAZAR)).toHaveLength(1)
    expect(envios(api, APROBAR)).toHaveLength(0)
    // Las acciones se reemplazan por el aviso del cambio, que recibe el foco.
    expect(
      screen.queryByRole("button", { name: "Rechazar" })
    ).not.toBeInTheDocument()
    await waitFor(() => expect(revisarNueva()).toHaveFocus())
    // Tras revisarla, «Rechazar» vuelve y el diálogo abre limpio.
    await userEvent.click(revisarNueva())
    const otro = await abrirRechazo()
    expect(within(otro).getByLabelText("Motivo del rechazo")).toHaveValue("")
    expect(within(otro).getByRole("alert")).toBeEmptyDOMElement()
  })

  it("un 409 de estado inválido deja el texto del servicio en la página y el foco en el contenido", async () => {
    let otra = false
    abrirPendiente(DE_LUIS, {
      [`GET ${RUTA}`]: () =>
        respuestaJson({
          ...EVENTO,
          estado: otra ? "en_evaluacion" : "pendiente_aprobacion",
        }),
      [`GET ${EVALUACION}`]: () =>
        respuestaJson(otra ? CON_RECOMENDACION : DE_LUIS),
      [`POST ${APROBAR}`]: () => {
        otra = true
        return problema(409, "estado_invalido", ESTADO_INVALIDO)
      },
    })
    await seccion()
    await userEvent.click(aprobar())
    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: TITULO })
      ).not.toBeInTheDocument()
    )
    const aviso = screen.getByText(ESTADO_INVALIDO)
    expect(aviso).toHaveAttribute("role", "status")
    expect(aviso).toHaveClass("text-warning")
    expect(document.getElementById("contenido")).toHaveFocus()
  })

  it("abrir «Rechazar» borra el aviso de un conflicto anterior", async () => {
    abrirPendiente(DE_LUIS, {
      [`POST ${APROBAR}`]: () => problema(409, "propuesta_distinta", DISTINTA),
    })
    await seccion()
    await userEvent.click(aprobar())
    await screen.findByText(DISTINTA)
    await userEvent.click(rechazar())
    await screen.findByRole("dialog", { name: "Rechazar la propuesta" })
    expect(screen.queryByText(DISTINTA)).not.toBeInTheDocument()
  })

  it("los demás errores al aprobar se dicen en la sección, que sigue disponible", async () => {
    const errores = [
      problema(
        403,
        "misma_persona",
        "Usted propuso esta adjudicación; la decide otra persona."
      ),
      respuestaJson(
        {
          title: "Servicio no disponible",
          detail: "No se pudo crear el contrato; intente de nuevo.",
        },
        503
      ),
    ]
    const { api } = abrirPendiente(DE_LUIS, {
      [`POST ${APROBAR}`]: () => errores.shift()!,
    })
    await seccion()
    const alerta = screen.getByRole("alert")
    expect(alerta).toBeEmptyDOMElement()
    await userEvent.click(aprobar())
    await waitFor(() =>
      expect(alerta).toHaveTextContent(
        "Usted propuso esta adjudicación; la decide otra persona."
      )
    )
    await userEvent.click(aprobar())
    await waitFor(() =>
      expect(alerta).toHaveTextContent(
        "No se pudo crear el contrato; intente de nuevo."
      )
    )
    // No son conflictos: no se recarga nada.
    expect(lecturas(api, EVALUACION)).toBe(1)
    expect(aprobar()).toHaveAttribute("aria-disabled", "false")
  })

  it("sin conexión, aprobar termina con un aviso y se puede intentar de nuevo", async () => {
    const { api } = abrirPendiente(DE_LUIS, {
      [`POST ${APROBAR}`]: () =>
        Promise.reject(new TypeError("Failed to fetch")),
    })
    await seccion()
    // Con la red caída la solicitud no se queda esperando: falla de inmediato y lo dice.
    onlineManager.setOnline(false)
    await userEvent.click(aprobar())
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(SIN_RED)
    )
    expect(aprobar()).toHaveAttribute("aria-disabled", "false")
    await userEvent.click(aprobar())
    await waitFor(() => expect(envios(api, APROBAR)).toHaveLength(2))
  })

  it("sin conexión, rechazar termina con un aviso en el diálogo y se puede cerrar", async () => {
    abrirPendiente(DE_LUIS, {
      [`POST ${RECHAZAR}`]: () =>
        Promise.reject(new TypeError("Failed to fetch")),
    })
    await seccion()
    const dialogo = await abrirRechazo()
    await userEvent.type(
      within(dialogo).getByLabelText("Motivo del rechazo"),
      "El costo es alto"
    )
    onlineManager.setOnline(false)
    await userEvent.click(confirmarRechazo(dialogo))
    await waitFor(() =>
      expect(within(dialogo).getByRole("alert")).toHaveTextContent(SIN_RED)
    )
    expect(confirmarRechazo(dialogo)).toHaveAttribute("aria-disabled", "false")
    await userEvent.keyboard("{Escape}")
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    )
  })

  it("cerrar «Rechazar» sin decidir devuelve el foco al botón", async () => {
    const { api } = abrirPendiente()
    await seccion()
    await abrirRechazo()
    await userEvent.keyboard("{Escape}")
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    )
    await waitFor(() => expect(rechazar()).toHaveFocus())
    expect(envios(api, RECHAZAR)).toHaveLength(0)
  })

  it("mientras se aprueba, «Rechazar» no abre", async () => {
    const lenta = respuestaDiferida()
    abrirPendiente(DE_LUIS, { [`POST ${APROBAR}`]: () => lenta.promesa })
    await seccion()
    await userEvent.click(aprobar())
    // aria-disabled y no disabled: el botón conserva su lugar en el orden del teclado.
    expect(rechazar()).toHaveAttribute("aria-disabled", "true")
    expect(rechazar()).not.toBeDisabled()
    await userEvent.click(rechazar())
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    await act(async () =>
      lenta.resolver(respuestaJson(propuesta("s2", "aprobada")))
    )
    await screen.findByText("Se aprobó la adjudicación.")
    await waitFor(() =>
      expect(rechazar()).toHaveAttribute("aria-disabled", "false")
    )
  })

  it("mientras una decisión sigue en camino, «Aprobar» no manda otra", async () => {
    const lenta = respuestaDiferida()
    let rechazada = false
    const { api } = abrirPendiente(DE_LUIS, {
      [`GET ${RUTA}`]: () =>
        rechazada ? lenta.promesa : respuestaJson(PENDIENTE),
      [`POST ${RECHAZAR}`]: () => {
        rechazada = true
        return respuestaJson({
          recomendacion: null,
          vigente: null,
          historial: [],
        })
      },
    })
    await seccion()
    const dialogo = await abrirRechazo()
    await userEvent.type(
      within(dialogo).getByLabelText("Motivo del rechazo"),
      "El costo es alto"
    )
    await userEvent.click(confirmarRechazo(dialogo))
    await screen.findByText(
      "Se rechazó la propuesta; la negociación vuelve a evaluación."
    )
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    )
    // El diálogo ya se cerró, pero la decisión sigue hasta que la negociación se actualiza.
    expect(aprobar()).toHaveAttribute("aria-disabled", "true")
    await userEvent.click(aprobar())
    expect(envios(api, APROBAR)).toHaveLength(0)
    await act(async () =>
      lenta.resolver(respuestaJson({ ...EVENTO, estado: "en_evaluacion" }))
    )
    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: TITULO })
      ).not.toBeInTheDocument()
    )
  })

  it("una propuesta que ya no está pendiente no ofrece acciones ni dice que hay que actualizar", async () => {
    for (const roles of [["aprobador"], ["comprador"]]) {
      for (const estado of ["aprobada", "directa", "rechazada"] as const) {
        sesionDePrueba.roles = roles
        abrirPendiente(
          propuesta("s2", estado, {
            propuesta_por_id: "luis-2",
            propuesta_por_nombre: "Luis Pérez",
          })
        )
        await seccion()
        const caso = `${roles} / ${estado}`
        expect(
          screen.queryByRole("button", { name: /Aprobar|Rechazar|Revisar/ }),
          caso
        ).not.toBeInTheDocument()
        for (const texto of [
          "Esperando aprobación de un aprobador.",
          "Usted propuso esta adjudicación; la aprueba otra persona.",
          "No hay una propuesta pendiente.",
        ])
          expect(screen.queryByText(texto), caso).not.toBeInTheDocument()
        expect(screen.getByText(/Propuesta de Luis Pérez/)).toBeInTheDocument()
        cleanup()
      }
    }
  })

  it("al aprobar, mientras la negociación se actualiza, la propuesta aprobada no ofrece decidir otra vez", async () => {
    const lenta = respuestaDiferida()
    let aprobada = false
    abrirPendiente(DE_LUIS, {
      [`GET ${RUTA}`]: () =>
        aprobada ? lenta.promesa : respuestaJson(PENDIENTE),
      [`GET ${EVALUACION}`]: () =>
        respuestaJson(
          aprobada
            ? propuesta("s2", "aprobada", {
                propuesta_por_id: "luis-2",
                propuesta_por_nombre: "Luis Pérez",
              })
            : DE_LUIS
        ),
      [`POST ${APROBAR}`]: () => {
        aprobada = true
        return respuestaJson(propuesta("s2", "aprobada"))
      },
    })
    await seccion()
    await userEvent.click(aprobar())
    await screen.findByText("Se aprobó la adjudicación.")
    // La evaluación ya dice «aprobada», pero la negociación aún no se actualizó: la sección sigue
    // a la vista, sin botones y sin pedir que se actualice la página.
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Aprobar" })
      ).not.toBeInTheDocument()
    )
    expect(
      screen.queryByRole("button", { name: "Rechazar" })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText("No hay una propuesta pendiente.")
    ).not.toBeInTheDocument()
    expect(screen.getByRole("heading", { name: TITULO })).toBeInTheDocument()
    await act(async () =>
      lenta.resolver(respuestaJson({ ...EVENTO, estado: "adjudicado" }))
    )
    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: TITULO })
      ).not.toBeInTheDocument()
    )
  })

  it("tras rechazar, la foto de la propuesta no se ofrece como evaluación mientras llega la viva", async () => {
    // Quien compra y aprueba: sus botones «Adjudicar» saldrían en la foto de la propuesta rechazada.
    sesionDePrueba.roles = ["comprador", "aprobador"]
    const viva = respuestaDiferida()
    let rechazada = false
    let pedidas = 0
    abrirPendiente(DE_LUIS, {
      [`GET ${RUTA}`]: () =>
        respuestaJson({
          ...EVENTO,
          estado: rechazada ? "en_evaluacion" : "pendiente_aprobacion",
        }),
      [`GET ${EVALUACION}`]: () => {
        if (!rechazada) return respuestaJson(DE_LUIS)
        pedidas += 1
        return pedidas === 1 ? viva.promesa : respuestaJson(CON_RECOMENDACION)
      },
      [`POST ${RECHAZAR}`]: () => {
        rechazada = true
        return respuestaJson({
          recomendacion: null,
          vigente: null,
          historial: [],
        })
      },
    })
    await seccion()
    const dialogo = await abrirRechazo()
    await userEvent.type(
      within(dialogo).getByLabelText("Motivo del rechazo"),
      "El costo es alto"
    )
    await userEvent.click(confirmarRechazo(dialogo))
    await screen.findByRole("heading", { name: "Evaluación" })
    // La evaluación viva todavía no llega: lo que hay en caché es la foto de la propuesta rechazada.
    expect(
      screen.queryByRole("table", { name: "Candidatos de la evaluación" })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: /Adjudicar/ })
    ).not.toBeInTheDocument()
    expect(screen.getByText("Cargando…")).toBeInTheDocument()

    await act(async () => viva.resolver(respuestaJson(CON_RECOMENDACION)))
    const tabla = await screen.findByRole("table", {
      name: "Candidatos de la evaluación",
    })
    expect(
      within(tabla).getAllByRole("button", { name: /Adjudicar/ })
    ).toHaveLength(2)
    expect(within(tabla).queryByText("Propuesta")).not.toBeInTheDocument()
  })

  it("con una propuesta vieja en caché, no se muestra ni se adopta hasta que llega la vigente", async () => {
    // El aprobador vuelve a la negociación con la propuesta de Luis en caché; mientras tanto el
    // servicio la reemplazó por la de Marta.
    const viva = respuestaDiferida()
    simularRutas({ [`GET ${EVALUACION}`]: () => viva.promesa })
    renderizarPagina(
      <ConCache evaluacion={DE_LUIS}>
        <SeccionAprobacion
          evento={PENDIENTE as unknown as Evento}
          alAvisar={vi.fn()}
          alConflicto={vi.fn()}
          alEmpezar={vi.fn()}
        />
      </ConCache>
    )
    // Mientras llega la vigente, ni la tabla ni la propuesta vieja ni sus acciones.
    expect(screen.getByText("Cargando…")).toBeInTheDocument()
    expect(
      screen.queryByText(/Propuesta de Luis Pérez/)
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("table", { name: "Candidatos de la evaluación" })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: /Aprobar|Rechazar/ })
    ).not.toBeInTheDocument()

    await act(async () => viva.resolver(respuestaJson(DE_MARTA)))
    // La primera que se adopta es la vigente: sus acciones salen sin aviso de cambio, porque el
    // aprobador nunca vio la anterior como algo que decidir.
    await screen.findByText(/Propuesta de Marta Ruiz/)
    expect(aprobar()).toBeInTheDocument()
    expect(rechazar()).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Revisar la propuesta nueva" })
    ).not.toBeInTheDocument()
  })

  it("tras rechazar, si la evaluación llega antes que la negociación no avisa de actualizar la página", async () => {
    const lenta = respuestaDiferida()
    let rechazada = false
    const { api, cliente } = abrirPendiente(DE_LUIS, {
      [`GET ${RUTA}`]: () =>
        rechazada ? lenta.promesa : respuestaJson(PENDIENTE),
      [`GET ${EVALUACION}`]: () =>
        respuestaJson(rechazada ? CON_RECOMENDACION : DE_LUIS),
      [`POST ${RECHAZAR}`]: () => {
        rechazada = true
        return respuestaJson({
          recomendacion: null,
          vigente: null,
          historial: [],
        })
      },
    })
    await seccion()
    const dialogo = await abrirRechazo()
    await userEvent.type(
      within(dialogo).getByLabelText("Motivo del rechazo"),
      "El costo es alto"
    )
    await userEvent.click(confirmarRechazo(dialogo))
    await screen.findByText(
      "Se rechazó la propuesta; la negociación vuelve a evaluación."
    )
    // La evaluación viva (sin propuesta) ya llegó; la negociación todavía no se actualiza.
    await waitFor(() => expect(lecturas(api, EVALUACION)).toBe(2))
    await waitFor(() =>
      expect(
        cliente.getQueryState(["negociacion", `/eventos/${ID}/evaluacion`])
          ?.fetchStatus
      ).toBe("idle")
    )
    await act(async () => {})
    expect(
      screen.queryByText("No hay una propuesta pendiente.")
    ).not.toBeInTheDocument()
    expect(screen.getByText("Cargando…")).toBeInTheDocument()

    await act(async () =>
      lenta.resolver(respuestaJson({ ...EVENTO, estado: "en_evaluacion" }))
    )
    await screen.findByRole("heading", { name: "Evaluación" })
    expect(
      screen.queryByRole("heading", { name: TITULO })
    ).not.toBeInTheDocument()
  })

  it("no tiene violaciones de axe en claro ni en oscuro", async () => {
    const { container } = abrirPendiente()
    await seccion()
    await esperarSinViolaciones(container)
    // Con el diálogo abierto.
    await abrirRechazo()
    await esperarSinViolaciones(document.body)
    await userEvent.keyboard("{Escape}")
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    )
  })

  it("quien propuso o espera tampoco tiene violaciones de axe", async () => {
    const PROPUSO = "Usted propuso esta adjudicación; la aprueba otra persona."
    const ESPERA = "Esperando aprobación de un aprobador."
    for (const [evaluacion, texto] of [
      [DE_ANA, PROPUSO],
      [DE_LUIS, ESPERA],
    ] as const) {
      sesionDePrueba.roles = ["comprador"]
      const { container } = abrirPendiente(evaluacion)
      await seccion()
      expect(screen.getByText(texto)).toBeInTheDocument()
      await esperarSinViolaciones(container)
      cleanup()
    }
  })

  it("el aviso de que la propuesta cambió tampoco tiene violaciones de axe", async () => {
    let cambio = false
    const { container } = abrirPendiente(DE_LUIS, {
      [`GET ${EVALUACION}`]: () => respuestaJson(cambio ? DE_MARTA : DE_LUIS),
      [`POST ${APROBAR}`]: () => {
        cambio = true
        return problema(409, "propuesta_distinta", DISTINTA)
      },
    })
    await seccion()
    await userEvent.click(aprobar())
    await screen.findByRole("button", { name: "Revisar la propuesta nueva" })
    await esperarSinViolaciones(container)
  })
})
