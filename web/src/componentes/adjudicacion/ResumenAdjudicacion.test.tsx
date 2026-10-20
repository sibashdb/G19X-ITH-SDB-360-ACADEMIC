import { act, cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { Evaluacion } from "@/adjudicacion"
import { ResumenAdjudicacion } from "@/componentes/adjudicacion/ResumenAdjudicacion"
import { formatoFechaHora } from "@/fechas"
import { GLOSARIO } from "@/glosario"
import type { Evento } from "@/negociacion"
import { Negociacion } from "@/paginas/Negociacion"
import {
  DATOS_DEL_SUR,
  EVALUACION,
  EVENTO,
  ID,
  NUBE_NORTE,
  RECOMENDACION,
  RUTA,
  SIN_ACUERDOS,
  propuesta,
  sesion,
} from "@/pruebas/evaluacion"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaDiferida,
  respuestaJson,
  simularRutas,
  sinEspaciosDuros,
} from "@/pruebas/utilidades"
import { formatoMoneda } from "@/tipos"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const APROBAR = `${RUTA}/adjudicacion/aprobar`

const fecha = (iso: string) => sinEspaciosDuros(formatoFechaHora(iso))
const dinero = (valor: string, moneda: string) =>
  sinEspaciosDuros(formatoMoneda(valor, moneda))

const ADJUDICADO = { ...EVENTO, estado: "adjudicado" }
const DESIERTO = {
  ...EVENTO,
  estado: "desierto",
  sesiones: [
    sesion("s1", "Nube Norte", "sin_acuerdo"),
    sesion("s2", "Datos del Sur", "sin_acuerdo"),
  ],
}

const APROBADA = propuesta("s1", "aprobada", {
  decidida_por_nombre: "Luis Pérez",
  decidida_en: "2026-10-23T09:30:00Z",
  contrato_folio: "CTR-2026-0042",
})
const DIRECTA = propuesta("s1", "directa", {
  decidida_por_nombre: "Ana López",
  decidida_en: "2026-10-22T16:00:00Z",
  contrato_folio: "CTR-2026-0043",
})

/** Las rechazadas, de la más reciente a la más antigua; la primera guarda otro nombre del proveedor. */
const RECHAZADA = propuesta("s2", "rechazada", {
  id: "a2",
  propuesta_por_id: "marta-3",
  propuesta_por_nombre: "Marta Ruiz",
  propuesta_en: "2026-10-21T10:00:00Z",
  decidida_por_nombre: "Luis Pérez",
  decidida_en: "2026-10-21T15:00:00Z",
  motivo_rechazo: "El proveedor no cumple los límites del contrato.",
  recomendacion: {
    ...RECOMENDACION,
    candidatos: [
      NUBE_NORTE,
      { ...DATOS_DEL_SUR, nombre: "Datos del Sur, S.A." },
    ],
  },
}).vigente!
const RECHAZADA_ANTERIOR = propuesta("s1", "rechazada", {
  id: "a1",
  propuesta_por_nombre: "Ana López",
  propuesta_en: "2026-10-20T10:00:00Z",
  decidida_por_nombre: "Sofía Díaz",
  decidida_en: "2026-10-20T18:00:00Z",
  motivo_rechazo: "Falta la cotización firmada.",
}).vigente!
const CON_RECHAZADAS: Evaluacion = {
  ...APROBADA,
  historial: [RECHAZADA, RECHAZADA_ANTERIOR],
}

function abrirResumen(evento: object, evaluacion: Evaluacion) {
  simularRutas({ [`GET ${EVALUACION}`]: () => respuestaJson(evaluacion) })
  return renderizarPagina(
    <ResumenAdjudicacion evento={evento as unknown as Evento} />
  )
}

/** Un párrafo por su texto completo, aunque lleve dentro un término del glosario. */
const parrafo = (texto: string) => (_: string, elemento: Element | null) =>
  elemento?.tagName === "P" && elemento.textContent === texto
const DECLARADA = "La negociación se declaró desierta."

/** La definición de un dato del resumen («Proveedor», «Folio del contrato»…). */
const dato = async (nombre: string) =>
  (await screen.findByText(nombre, { selector: "dt" })).nextElementSibling

beforeEach(() => {
  sesionDePrueba.roles = ["comprador"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Resumen de la adjudicada o la desierta", () => {
  it("la adjudicada aprobada dice quién propuso, quién aprobó y el folio", async () => {
    abrirResumen(ADJUDICADO, APROBADA)
    expect(await dato("Proveedor")).toHaveTextContent("Nube Norte")
    expect(await dato("Costo total")).toHaveTextContent(
      dinero("480000.00", "MXN")
    )
    expect(await dato("Propuso")).toHaveTextContent(
      `Ana López, ${fecha("2026-10-22T16:00:00Z")}`
    )
    expect(await dato("Aprobó")).toHaveTextContent(
      `Luis Pérez, ${fecha("2026-10-23T09:30:00Z")}`
    )
    expect(screen.getByText("CTR-2026-0042")).toHaveClass("font-mono")
    // Ni la desierta ni las rechazadas: no hubo.
    expect(screen.queryByText(parrafo(DECLARADA))).not.toBeInTheDocument()
    expect(
      screen.queryByRole("heading", { name: "Propuestas rechazadas" })
    ).not.toBeInTheDocument()
  })

  it("en dólares agrega el equivalente en pesos", async () => {
    abrirResumen(
      { ...ADJUDICADO, moneda: "USD" },
      propuesta("s1", "aprobada", {
        costo_total: "27000.00",
        costo_total_mxn: "486000.00",
        decidida_por_nombre: "Luis Pérez",
        decidida_en: "2026-10-23T09:30:00Z",
        contrato_folio: "CTR-2026-0042",
      })
    )
    const costo = await dato("Costo total")
    expect(costo).toHaveTextContent(dinero("27000.00", "USD"))
    expect(costo).toHaveTextContent(`≈ ${dinero("486000.00", "MXN")}`)
  })

  it("la directa dice que la adjudicó el comprador", async () => {
    abrirResumen(ADJUDICADO, DIRECTA)
    expect(await dato("Aprobó")).toHaveTextContent(
      "Adjudicación directa del comprador"
    )
    expect(await dato("Propuso")).toHaveTextContent(
      `Ana López, ${fecha("2026-10-22T16:00:00Z")}`
    )
    expect(screen.getByText("CTR-2026-0043")).toHaveClass("font-mono")
  })

  it("si el candidato falta en la foto, el proveedor sale de la sesión", async () => {
    abrirResumen(
      ADJUDICADO,
      propuesta("s1", "aprobada", {
        recomendacion: { ...RECOMENDACION, candidatos: [] },
      })
    )
    expect(await dato("Proveedor")).toHaveTextContent("Nube Norte")
  })

  it("la desierta automática explica que no hubo acuerdos", async () => {
    abrirResumen(DESIERTO, SIN_ACUERDOS)
    expect(await screen.findByText(parrafo(DECLARADA))).toBeInTheDocument()
    expect(
      screen.getByText("Ningún proveedor llegó a un acuerdo tentativo.")
    ).toBeInTheDocument()
    expect(screen.queryByText(/Motivo:/)).not.toBeInTheDocument()
    expect(screen.queryByRole("term")).not.toBeInTheDocument()
  })

  it("define qué es una negociación desierta", async () => {
    abrirResumen(DESIERTO, SIN_ACUERDOS)
    await userEvent.click(
      await screen.findByRole("button", { name: "desierta" })
    )
    expect(
      await screen.findByRole("dialog", { name: "Desierta" })
    ).toHaveTextContent(GLOSARIO.desierta.definicion)
  })

  it("el motivo de la desierta y cada propuesta rechazada parten las palabras largas para no ensanchar la tarjeta a 375 px", async () => {
    // jsdom no calcula el diseño: se fija la clase. El motivo del rechazo va dentro de la propuesta
    // y hereda `overflow-wrap`.
    abrirResumen(
      { ...DESIERTO, motivo_desierta: "x".repeat(300) },
      { ...SIN_ACUERDOS, historial: [RECHAZADA, RECHAZADA_ANTERIOR] }
    )
    expect(await screen.findByText(/^Motivo: x+$/)).toHaveClass("break-words")
    const rechazadas = within(
      screen.getByRole("list", { name: "Propuestas rechazadas" })
    ).getAllByRole("listitem")
    expect(rechazadas).toHaveLength(2)
    for (const rechazada of rechazadas)
      expect(rechazada).toHaveClass("break-words")
  })

  it("la desierta manual muestra el motivo", async () => {
    abrirResumen(
      { ...DESIERTO, motivo_desierta: "El presupuesto se congeló." },
      SIN_ACUERDOS
    )
    expect(
      await screen.findByText("Motivo: El presupuesto se congeló.")
    ).toBeInTheDocument()
    expect(
      screen.queryByText("Ningún proveedor llegó a un acuerdo tentativo.")
    ).not.toBeInTheDocument()
  })

  it("lista las propuestas rechazadas con su motivo", async () => {
    abrirResumen(ADJUDICADO, CON_RECHAZADAS)
    const lista = await screen.findByRole("list", {
      name: "Propuestas rechazadas",
    })
    const [reciente, anterior] = within(lista).getAllByRole("listitem")
    // Cada una con el proveedor de su propia foto, quién la propuso y quién la rechazó.
    expect(reciente).toHaveTextContent("Datos del Sur, S.A.")
    expect(reciente).toHaveTextContent(
      `Propuso Marta Ruiz, ${fecha("2026-10-21T10:00:00Z")}`
    )
    expect(reciente).toHaveTextContent(
      `Rechazó Luis Pérez, ${fecha("2026-10-21T15:00:00Z")}`
    )
    expect(reciente).toHaveTextContent(
      "Motivo del rechazo: El proveedor no cumple los límites del contrato."
    )
    expect(anterior).toHaveTextContent("Nube Norte")
    expect(anterior).toHaveTextContent(
      `Propuso Ana López, ${fecha("2026-10-20T10:00:00Z")}`
    )
    expect(anterior).toHaveTextContent(
      `Rechazó Sofía Díaz, ${fecha("2026-10-20T18:00:00Z")}`
    )
    expect(anterior).toHaveTextContent(
      "Motivo del rechazo: Falta la cotización firmada."
    )
  })

  it("la desierta también lista las rechazadas", async () => {
    abrirResumen(DESIERTO, { ...SIN_ACUERDOS, historial: [RECHAZADA] })
    const lista = await screen.findByRole("list", {
      name: "Propuestas rechazadas",
    })
    expect(within(lista).getAllByRole("listitem")).toHaveLength(1)
    expect(lista).toHaveTextContent("Datos del Sur, S.A.")
  })

  it("no tiene violaciones de axe", async () => {
    const { container, unmount } = abrirResumen(ADJUDICADO, CON_RECHAZADAS)
    await dato("Proveedor")
    await esperarSinViolaciones(container)
    unmount()
    const desierta = abrirResumen(
      { ...DESIERTO, motivo_desierta: "El presupuesto se congeló." },
      { ...SIN_ACUERDOS, historial: [RECHAZADA] }
    )
    await screen.findByText(parrafo(DECLARADA))
    await esperarSinViolaciones(desierta.container)
  })

  it("si la evaluación falla, lo dice con «Reintentar» y se recupera", async () => {
    let caida = true
    simularRutas({
      [`GET ${EVALUACION}`]: () =>
        caida
          ? respuestaJson(
              {
                title: "Servicio no disponible",
                detail:
                  "No se pudo consultar la adjudicación; intente de nuevo.",
              },
              503
            )
          : respuestaJson(APROBADA),
    })
    renderizarPagina(
      <ResumenAdjudicacion evento={ADJUDICADO as unknown as Evento} />
    )
    expect(
      await screen.findByText(
        "No se pudo consultar la adjudicación; intente de nuevo."
      )
    ).toBeInTheDocument()
    caida = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(await dato("Proveedor")).toHaveTextContent("Nube Norte")
    expect(
      screen.queryByRole("button", { name: "Reintentar" })
    ).not.toBeInTheDocument()
  })
})

describe("Resumen en la página de la negociación", () => {
  const abrirPagina = () =>
    renderizarPagina(<Negociacion />, {
      ruta: `/negociaciones/${ID}`,
      patron: "/negociaciones/:id",
    })

  it.each([
    ["adjudicada", ADJUDICADO, APROBADA],
    ["desierta", DESIERTO, SIN_ACUERDOS],
  ])(
    "la %s lo muestra antes de las sesiones",
    async (_, evento, evaluacion) => {
      simularRutas({
        [`GET ${RUTA}`]: () => respuestaJson(evento),
        [`GET ${EVALUACION}`]: () => respuestaJson(evaluacion),
      })
      abrirPagina()
      const resumen = await screen.findByRole("heading", { name: "Resultado" })
      const sesiones = screen.getByRole("heading", { name: "Sesiones" })
      expect(
        resumen.compareDocumentPosition(sesiones) &
          Node.DOCUMENT_POSITION_FOLLOWING
      ).toBeTruthy()
    }
  )

  it("las demás etapas no lo muestran", async () => {
    simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
      [`GET ${EVALUACION}`]: () => respuestaJson(SIN_ACUERDOS),
    })
    abrirPagina()
    await screen.findByRole("heading", { name: "Evaluación" })
    expect(
      screen.queryByRole("heading", { name: "Resultado" })
    ).not.toBeInTheDocument()
  })

  it("tras aprobar no presenta la propuesta pendiente como adjudicada mientras llega la viva", async () => {
    sesionDePrueba.roles = ["aprobador"]
    const pendiente = propuesta("s1", "pendiente", {
      propuesta_por_id: "luis-2",
      propuesta_por_nombre: "Luis Pérez",
    })
    const viva = respuestaDiferida()
    let aprobada = false
    let pedidasTrasAprobar = 0
    simularRutas({
      [`GET ${RUTA}`]: () =>
        respuestaJson({
          ...EVENTO,
          estado: aprobada ? "adjudicado" : "pendiente_aprobacion",
        }),
      [`GET ${EVALUACION}`]: () => {
        if (!aprobada) return respuestaJson(pendiente)
        // La primera lectura tras aprobar tarda; las siguientes ya traen la aprobada.
        return pedidasTrasAprobar++ === 0
          ? viva.promesa
          : respuestaJson(APROBADA)
      },
      [`POST ${APROBAR}`]: () => {
        aprobada = true
        return respuestaJson(APROBADA)
      },
    })
    abrirPagina()
    await userEvent.click(
      await screen.findByRole("button", { name: "Aprobar" })
    )
    // La negociación ya es «Adjudicada», pero la evaluación en caché sigue siendo la pendiente.
    const resumen = await screen.findByRole("heading", { name: "Resultado" })
    expect(resumen).toBeInTheDocument()
    // Ni quién propuso ni quién aprobó: lo que hay en caché es la pendiente.
    expect(screen.queryByText("Propuso", { selector: "dt" })).toBeNull()
    await act(async () => viva.resolver(respuestaJson(APROBADA)))
    expect(await dato("Aprobó")).toHaveTextContent("Luis Pérez")
  })
})
