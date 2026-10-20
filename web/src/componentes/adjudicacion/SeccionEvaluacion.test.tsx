import { focusManager } from "@tanstack/react-query"
import { act, cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { Evaluacion } from "@/adjudicacion"
import { TablaCandidatos } from "@/componentes/adjudicacion/TablaCandidatos"
import { formatoFechaHora } from "@/fechas"
import { GLOSARIO } from "@/glosario"
import type { Evento } from "@/negociacion"
import { Negociacion } from "@/paginas/Negociacion"
import {
  CON_RECOMENDACION,
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

const PESOS_25 = `${EVALUACION}?pesos=25,25,25,25`

/** Lo que devuelve el servicio con otros pesos: el orden de los candidatos cambia. */
const CON_PESOS_25: Evaluacion = {
  ...CON_RECOMENDACION,
  recomendacion: {
    ...RECOMENDACION,
    pesos: { costo: 25, desempeno: 25, riesgo: 25, sla: 25 },
    candidatos: [
      { ...DATOS_DEL_SUR, lugar: 1, puntaje: 71.5 },
      { ...NUBE_NORTE, lugar: 2, puntaje: 70.2 },
    ],
    recomendado: "s2",
    explicacion: ["Con pesos parejos, Datos del Sur queda primero."],
  },
}

/** Las rechazadas, de la más reciente a la más antigua; la primera guarda otro nombre del proveedor. */
const RECHAZADA = propuesta("s2", "rechazada", {
  id: "a2",
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
/** Lo que devuelve el servicio en evaluación tras dos rechazos. */
const TRAS_RECHAZOS: Evaluacion = {
  ...CON_RECOMENDACION,
  historial: [RECHAZADA, RECHAZADA_ANTERIOR],
}
const fecha = (iso: string) => sinEspaciosDuros(formatoFechaHora(iso))

const PESOS_INVALIDOS =
  "Indique los pesos como cuatro enteros de 0 a 100 que sumen 100, en el orden costo, desempeño, riesgo y SLA; por ejemplo, 40,30,15,15."

function abrir() {
  return renderizarPagina(<Negociacion />, {
    ruta: `/negociaciones/${ID}`,
    patron: "/negociaciones/:id",
  })
}

/** La tabla de candidatos de la evaluación (la de sesiones es otra). */
const tablaCandidatos = () =>
  screen.getByRole("table", { name: "Candidatos de la evaluación" })

/** Los datos de la fila de un proveedor en la tabla de candidatos. */
function fila(proveedor: string) {
  const celda = within(tablaCandidatos()).getByText(proveedor)
  return within(celda.closest("tr")!)
}

/** Escribe los cuatro pesos, en el orden costo, desempeño, riesgo y SLA. */
async function escribirPesos(...valores: string[]) {
  const nombres = ["Costo total", "Desempeño", "Riesgo", "SLA"]
  for (const [i, nombre] of nombres.entries()) {
    const campo = screen.getByLabelText(`Peso (${nombre})`)
    await userEvent.clear(campo)
    await userEvent.type(campo, valores[i])
  }
}

beforeEach(() => {
  sesionDePrueba.roles = ["comprador"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Sección «Evaluación»", () => {
  it("define la adjudicación y «fuera de límites» con sus términos", async () => {
    simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
      [`GET ${EVALUACION}`]: () => respuestaJson(CON_RECOMENDACION),
    })
    abrir()
    await userEvent.click(
      await screen.findByRole("button", { name: "adjudicación" })
    )
    expect(
      await screen.findByRole("dialog", { name: "Adjudicación" })
    ).toHaveTextContent(GLOSARIO.adjudicacion.definicion)
    await userEvent.keyboard("{Escape}")

    await userEvent.click(
      fila("Datos del Sur").getByRole("button", { name: "Fuera de límites" })
    )
    expect(
      await screen.findByRole("dialog", { name: "Fuera de límites" })
    ).toHaveTextContent(GLOSARIO.fueraDeLimites.definicion)
  })

  it("muestra los candidatos en orden, con el recomendado marcado con texto", async () => {
    simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
      [`GET ${EVALUACION}`]: () => respuestaJson(CON_RECOMENDACION),
    })
    abrir()
    expect(
      await screen.findByRole("heading", { name: "Evaluación" })
    ).toBeInTheDocument()
    const filas = within(
      await screen.findByRole("table", {
        name: "Candidatos de la evaluación",
      })
    ).getAllByRole("row")
    // El encabezado y un candidato por fila, en el orden de los lugares.
    expect(filas).toHaveLength(3)
    expect(
      within(filas[0])
        .getAllByRole("columnheader")
        .map((c) => c.textContent)
    ).toEqual(
      expect.arrayContaining([
        "Proveedor",
        "Costo total",
        "Desempeño",
        "Riesgo",
        "SLA",
        "Puntaje",
        "Lugar",
      ])
    )
    expect(filas[1]).toHaveTextContent("Nube Norte")
    expect(filas[2]).toHaveTextContent("Datos del Sur")

    const primera = fila("Nube Norte")
    expect(primera.getByText("Recomendado")).toBeInTheDocument()
    expect(primera.getByText(formatoMoneda("480000.00", "MXN"))).toBeVisible()
    expect(primera.getByText("82.4")).toBeInTheDocument()
    expect(primera.getByText("99.9 %")).toBeInTheDocument()
    expect(primera.getByText("78.3")).toBeInTheDocument()
    expect(primera.getByText("1")).toBeInTheDocument()
    expect(primera.queryByText("Fuera de límites")).not.toBeInTheDocument()
    // En pesos mexicanos, el costo no repite una equivalencia.
    expect(within(tablaCandidatos()).queryByText(/≈/)).not.toBeInTheDocument()

    const segunda = fila("Datos del Sur")
    expect(segunda.queryByText("Recomendado")).not.toBeInTheDocument()
    expect(segunda.getByText("Fuera de límites")).toBeInTheDocument()
    // Sin SLA en el acuerdo ni en el contrato vigente.
    expect(segunda.getByText("—")).toBeInTheDocument()
    // Las sesiones siguen debajo, con su propia tabla.
    expect(
      screen.getByRole("heading", { name: "Sesiones" })
    ).toBeInTheDocument()
  })

  it("en USD el costo lleva su equivalente en MXN", async () => {
    const enDolares: Evaluacion = {
      ...CON_RECOMENDACION,
      recomendacion: {
        ...RECOMENDACION,
        tipo_cambio: { periodo: "2026-10", usd_mxn: "18.4615" },
        candidatos: [
          { ...NUBE_NORTE, costo_total: "26000.00" },
          { ...DATOS_DEL_SUR, costo_total: "27600.00" },
        ],
      },
    }
    simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson({ ...EVENTO, moneda: "USD" }),
      [`GET ${EVALUACION}`]: () => respuestaJson(enDolares),
    })
    abrir()
    await screen.findByRole("table", { name: "Candidatos de la evaluación" })
    const primera = fila("Nube Norte")
    expect(
      primera.getByText(sinEspaciosDuros(formatoMoneda("26000.00", "USD")))
    ).toBeInTheDocument()
    expect(
      primera.getByText(`≈ ${formatoMoneda("480000.00", "MXN")}`)
    ).toBeInTheDocument()
    expect(
      fila("Datos del Sur").getByText(`≈ ${formatoMoneda("510000.00", "MXN")}`)
    ).toBeInTheDocument()
  })

  it("el riesgo muestra su nivel y sus componentes", async () => {
    simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
      [`GET ${EVALUACION}`]: () => respuestaJson(CON_RECOMENDACION),
    })
    abrir()
    await screen.findByRole("table", { name: "Candidatos de la evaluación" })
    const primera = fila("Nube Norte")
    expect(primera.getByText("Bajo")).toBeInTheDocument()
    // El nombre accesible del control dice de qué es el nivel.
    expect(primera.getByText("Bajo").closest("summary")).toHaveTextContent(
      "Riesgo Bajo"
    )
    expect(primera.getByText("Concentración: 35 %")).toBeInTheDocument()
    expect(
      primera.getByText("Tendencia de incidentes: 10 %")
    ).toBeInTheDocument()
    expect(primera.getByText("Sin historial: no")).toBeInTheDocument()
    const segunda = fila("Datos del Sur")
    expect(segunda.getByText("Medio")).toBeInTheDocument()
    expect(segunda.getByText("Concentración: 60 %")).toBeInTheDocument()
    expect(
      segunda.getByText("Tendencia de incidentes: 25 %")
    ).toBeInTheDocument()
    expect(segunda.getByText("Sin historial: sí")).toBeInTheDocument()
  })

  it("la explicación se lee como texto", async () => {
    simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
      [`GET ${EVALUACION}`]: () => respuestaJson(CON_RECOMENDACION),
    })
    abrir()
    for (const frase of RECOMENDACION.explicacion) {
      const parrafo = await screen.findByText(frase)
      expect(parrafo.tagName).toBe("P")
    }
  })

  it("recalcular pide la evaluación con los pesos como texto y deja la tabla mientras carga", async () => {
    const recalculo = respuestaDiferida()
    const api = simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
      [`GET ${EVALUACION}`]: () => respuestaJson(CON_RECOMENDACION),
      [`GET ${PESOS_25}`]: () => recalculo.promesa,
    })
    abrir()
    // Los campos parten de los pesos configurados, en el orden costo, desempeño, riesgo y SLA.
    expect(await screen.findByLabelText("Peso (Costo total)")).toHaveValue(40)
    expect(screen.getByLabelText("Peso (Desempeño)")).toHaveValue(30)
    expect(screen.getByLabelText("Peso (Riesgo)")).toHaveValue(15)
    expect(screen.getByLabelText("Peso (SLA)")).toHaveValue(15)
    expect(screen.getByText("Total: 100 de 100")).toBeInTheDocument()

    await escribirPesos("25", "25", "25", "25")
    await userEvent.click(screen.getByRole("button", { name: "Recalcular" }))

    // Mientras llega la respuesta, la tabla anterior sigue a la vista y se avisa del cálculo.
    expect(await screen.findByText("Recalculando…")).toBeInTheDocument()
    expect(tablaCandidatos()).toBeInTheDocument()
    expect(api).toHaveBeenCalledWith(PESOS_25, expect.anything())

    recalculo.resolver(respuestaJson(CON_PESOS_25))
    expect(
      await screen.findByText("Con pesos parejos, Datos del Sur queda primero.")
    ).toBeInTheDocument()
    expect(screen.queryByText("Recalculando…")).not.toBeInTheDocument()
    expect(within(tablaCandidatos()).getAllByRole("row")[1]).toHaveTextContent(
      "Datos del Sur"
    )
    expect(fila("Datos del Sur").getByText("Recomendado")).toBeInTheDocument()
    // Los campos conservan lo que se escribió.
    expect(screen.getByLabelText("Peso (Costo total)")).toHaveValue(25)
  })

  it("pesos que no suman 100 no recalculan y lo explican", async () => {
    const api = simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
      [`GET ${EVALUACION}`]: () => respuestaJson(CON_RECOMENDACION),
    })
    abrir()
    await screen.findByLabelText("Peso (Costo total)")
    const antes = api.mock.calls.length
    await escribirPesos("25", "25", "20", "20")
    expect(
      screen.getByText("Total: 90 de 100 · Los pesos deben sumar 100.")
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Recalcular" }))
    expect(
      await screen.findByText("Los pesos deben sumar 100; ahora suman 90.")
    ).toBeInTheDocument()
    expect(api.mock.calls).toHaveLength(antes)
  })

  it("un campo fuera de rango no recalcula, aunque el total parezca 100", async () => {
    const api = simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
      [`GET ${EVALUACION}`]: () => respuestaJson(CON_RECOMENDACION),
    })
    abrir()
    await screen.findByLabelText("Peso (Costo total)")
    const antes = api.mock.calls.length
    // «1000» no es un peso: no debe contar como 0 y dejar el total en 100.
    await escribirPesos("1000", "50", "25", "25")
    expect(screen.queryByText("Total: 100 de 100")).not.toBeInTheDocument()
    expect(
      screen.getByText("Total: 100 de 100 · Revise los campos.")
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Recalcular" }))
    expect(
      await screen.findByText("Cada peso debe ser un número entero de 0 a 100.")
    ).toBeInTheDocument()
    expect(api.mock.calls).toHaveLength(antes)
    // Los campos piden enteros de 0 a 100.
    const campo = screen.getByLabelText("Peso (Costo total)")
    expect(campo).toHaveAttribute("min", "0")
    expect(campo).toHaveAttribute("max", "100")
    expect(campo).toHaveAttribute("step", "1")
  })

  it("un 422 de pesos se muestra junto a los campos", async () => {
    simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
      [`GET ${EVALUACION}`]: () => respuestaJson(CON_RECOMENDACION),
      [`GET ${PESOS_25}`]: () =>
        respuestaJson(
          {
            title: "Solicitud inválida",
            detail: "Revise los datos marcados.",
            codigo: "pesos_invalidos",
            errores: [{ campo: "pesos", mensaje: PESOS_INVALIDOS }],
          },
          422
        ),
    })
    abrir()
    await screen.findByLabelText("Peso (Costo total)")
    await escribirPesos("25", "25", "25", "25")
    await userEvent.click(screen.getByRole("button", { name: "Recalcular" }))
    const grupo = await screen.findByRole("group", { name: /Ajustar pesos/ })
    expect(await within(grupo).findByText(PESOS_INVALIDOS)).toBeInTheDocument()
    // No es una falla de la evaluación: no se ofrece reintentar y los campos siguen.
    expect(
      screen.queryByRole("button", { name: "Reintentar" })
    ).not.toBeInTheDocument()
    expect(screen.getByLabelText("Peso (Costo total)")).toHaveValue(25)
    // La última recomendación calculada sigue a la vista, y se dice que es la anterior.
    expect(fila("Nube Norte").getByText("Recomendado")).toBeInTheDocument()
    expect(screen.getByText(RECOMENDACION.explicacion[0])).toBeInTheDocument()
    expect(
      screen.getByText(
        "Se muestran los resultados de los últimos pesos que se calcularon."
      )
    ).toBeInTheDocument()
    // Al corregir un campo, el rechazo ya no se muestra.
    await userEvent.type(screen.getByLabelText("Peso (Costo total)"), "1")
    expect(within(grupo).queryByText(PESOS_INVALIDOS)).not.toBeInTheDocument()
  })

  it("no vuelve a pedir la evaluación al volver a la ventana", async () => {
    const api = simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
      [`GET ${EVALUACION}`]: () => respuestaJson(CON_RECOMENDACION),
    })
    const veces = (url: string) =>
      api.mock.calls.filter(([u]) => u === url).length
    abrir()
    await screen.findByRole("table", { name: "Candidatos de la evaluación" })
    try {
      await act(async () => {
        focusManager.setFocused(false)
        focusManager.setFocused(true)
      })
      // La negociación sí se actualiza al volver (prueba de que el enfoque llegó a las consultas)...
      await waitFor(() => expect(veces(RUTA)).toBe(2))
      // ...pero la evaluación cambia solo al recalcular, tras una acción o con «Reintentar».
      expect(veces(EVALUACION)).toBe(1)
    } finally {
      focusManager.setFocused(undefined)
    }
  })

  it("con inteligencia caída la evaluación ofrece reintentar y las sesiones siguen", async () => {
    let caida = true
    simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
      [`GET ${EVALUACION}`]: () =>
        caida
          ? respuestaJson(
              {
                title: "Servicio no disponible",
                detail:
                  "No se pudo consultar la recomendación; intente de nuevo.",
              },
              503
            )
          : respuestaJson(CON_RECOMENDACION),
    })
    abrir()
    expect(
      await screen.findByText(
        "No se pudo consultar la recomendación; intente de nuevo."
      )
    ).toBeInTheDocument()
    // Las sesiones y la configuración no dependen de la evaluación.
    expect(
      screen.getByRole("heading", { name: "Sesiones" })
    ).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Cielo Azul" })).toBeInTheDocument()
    expect(
      screen.getByRole("heading", { name: "Configuración" })
    ).toBeInTheDocument()

    caida = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(
      await screen.findByRole("table", { name: "Candidatos de la evaluación" })
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Reintentar" })
    ).not.toBeInTheDocument()
  })

  it("sin acuerdos dice que no hay qué evaluar", async () => {
    simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
      [`GET ${EVALUACION}`]: () => respuestaJson(SIN_ACUERDOS),
    })
    abrir()
    expect(
      await screen.findByText("No hay acuerdos tentativos para evaluar.")
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Recalcular" })
    ).not.toBeInTheDocument()
  })

  it("quien solo lee la negociación también ve la evaluación", async () => {
    sesionDePrueba.roles = ["aprobador"]
    simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
      [`GET ${EVALUACION}`]: () => respuestaJson(CON_RECOMENDACION),
    })
    abrir()
    expect(
      await screen.findByRole("table", { name: "Candidatos de la evaluación" })
    ).toBeInTheDocument()
  })

  it("no aparece si la negociación no está en evaluación", async () => {
    const api = simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson({ ...EVENTO, estado: "abierto" }),
    })
    abrir()
    expect(
      await screen.findByRole("heading", { name: "Sesiones" })
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("heading", { name: "Evaluación" })
    ).not.toBeInTheDocument()
    expect(api).not.toHaveBeenCalledWith(EVALUACION, expect.anything())
  })

  it("no tiene violaciones de axe en claro ni en oscuro", async () => {
    simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
      [`GET ${EVALUACION}`]: () => respuestaJson(CON_RECOMENDACION),
    })
    const { container } = abrir()
    await screen.findByRole("table", { name: "Candidatos de la evaluación" })
    await esperarSinViolaciones(container)
  })

  describe("tras un rechazo", () => {
    const AVISO = "Se rechazó la última propuesta"

    it("avisa de la propuesta rechazada más reciente, con quién la propuso y la rechazó y el motivo", async () => {
      simularRutas({
        [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
        [`GET ${EVALUACION}`]: () => respuestaJson(TRAS_RECHAZOS),
      })
      abrir()
      const aviso = await screen.findByRole("region", { name: AVISO })
      // El proveedor sale de la foto de esa propuesta, no de la evaluación de ahora.
      expect(aviso).toHaveTextContent("Datos del Sur, S.A.")
      expect(aviso).toHaveTextContent(
        `Propuso Marta Ruiz, ${fecha("2026-10-21T10:00:00Z")}`
      )
      expect(aviso).toHaveTextContent(
        `Rechazó Luis Pérez, ${fecha("2026-10-21T15:00:00Z")}`
      )
      expect(aviso).toHaveTextContent(
        "Motivo del rechazo: El proveedor no cumple los límites del contrato."
      )
      // Solo la más reciente, y con texto: no depende del color.
      expect(aviso).not.toHaveTextContent("Falta la cotización firmada.")
      expect(aviso).not.toHaveTextContent("Sofía Díaz")
      // La tabla sigue debajo para volver a proponer.
      expect(
        screen.getByRole("table", { name: "Candidatos de la evaluación" })
      ).toBeInTheDocument()
    })

    it("un motivo con una palabra larguísima parte las palabras para no ensanchar la tarjeta a 375 px", async () => {
      // jsdom no calcula el diseño: se fija la clase.
      const larga = {
        ...RECHAZADA,
        motivo_rechazo: "x".repeat(300),
      }
      simularRutas({
        [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
        [`GET ${EVALUACION}`]: () =>
          respuestaJson({ ...CON_RECOMENDACION, historial: [larga] }),
      })
      abrir()
      const aviso = await screen.findByRole("region", { name: AVISO })
      expect(aviso).toHaveClass("break-words")
      expect(within(aviso).getByText(/^Motivo del rechazo: x+$/)).toBeVisible()
    })

    it("sin rechazos no hay aviso", async () => {
      simularRutas({
        [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
        [`GET ${EVALUACION}`]: () => respuestaJson(CON_RECOMENDACION),
      })
      abrir()
      await screen.findByRole("table", { name: "Candidatos de la evaluación" })
      expect(
        screen.queryByRole("region", { name: AVISO })
      ).not.toBeInTheDocument()
    })

    it("lo ve también quien solo lee la negociación", async () => {
      sesionDePrueba.roles = ["aprobador"]
      simularRutas({
        [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
        [`GET ${EVALUACION}`]: () => respuestaJson(TRAS_RECHAZOS),
      })
      abrir()
      expect(
        await screen.findByRole("region", { name: AVISO })
      ).toBeInTheDocument()
    })

    it("no tiene violaciones de axe en claro ni en oscuro", async () => {
      simularRutas({
        [`GET ${RUTA}`]: () => respuestaJson(EVENTO),
        [`GET ${EVALUACION}`]: () => respuestaJson(TRAS_RECHAZOS),
      })
      const { container } = abrir()
      await screen.findByRole("region", { name: AVISO })
      await esperarSinViolaciones(container)
    })
  })
})

describe("TablaCandidatos", () => {
  it("marca la propuesta y dibuja la acción de cada fila", async () => {
    const { container } = renderizarPagina(
      <TablaCandidatos
        recomendacion={RECOMENDACION}
        evento={EVENTO as unknown as Evento}
        destacada="s2"
        accion={(c) => <button type="button">Elegir a {c.nombre}</button>}
      />
    )
    expect(fila("Datos del Sur").getByText("Propuesta")).toBeInTheDocument()
    expect(fila("Nube Norte").queryByText("Propuesta")).not.toBeInTheDocument()
    expect(
      fila("Nube Norte").getByRole("button", { name: "Elegir a Nube Norte" })
    ).toBeInTheDocument()
    expect(
      fila("Datos del Sur").getByRole("button", {
        name: "Elegir a Datos del Sur",
      })
    ).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })

  it("los distintivos verde y ámbar llevan fondo propio para no perder contraste sobre la fila resaltada", () => {
    // Sobre bg-info-suave (#E0F2FE) el verde #15803D y el ámbar #B45309 de 12 px dan 4.37:1 y
    // 4.38:1 (< 4.5:1); sobre bg-card (#FFFFFF) dan 5.02:1. jsdom no calcula contraste, así que se
    // fija la clase; los valores salen de los tokens de index.css.
    renderizarPagina(
      <TablaCandidatos
        recomendacion={RECOMENDACION}
        evento={EVENTO as unknown as Evento}
        destacada="s1"
      />
    )
    expect(fila("Nube Norte").getByText("Recomendado")).toHaveClass("bg-card")
    // El texto es el término del glosario; el fondo es el de la etiqueta que lo contiene.
    expect(
      fila("Datos del Sur")
        .getByText("Fuera de límites")
        .closest("[data-slot=badge]")
    ).toHaveClass("bg-card")
  })

  it("define «fuera de límites» solo en la primera fila que lo lleva", () => {
    const dos = {
      ...EVENTO,
      sesiones: [
        sesion("s1", "Nube Norte", "acuerdo_tentativo", true),
        sesion("s2", "Datos del Sur", "acuerdo_tentativo", true),
      ],
    }
    renderizarPagina(
      <TablaCandidatos
        recomendacion={RECOMENDACION}
        evento={dos as unknown as Evento}
      />
    )
    expect(screen.getAllByText("Fuera de límites")).toHaveLength(2)
    const terminos = screen.getAllByRole("button", { name: "Fuera de límites" })
    expect(terminos).toHaveLength(1)
    expect(
      fila("Nube Norte").getByRole("button", { name: "Fuera de límites" })
    ).toBe(terminos[0])
  })
})
