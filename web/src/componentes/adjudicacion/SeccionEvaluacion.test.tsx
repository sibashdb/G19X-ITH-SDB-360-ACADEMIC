import { focusManager } from "@tanstack/react-query"
import { act, cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { Candidato, Evaluacion, Recomendacion } from "@/adjudicacion"
import { TablaCandidatos } from "@/componentes/adjudicacion/TablaCandidatos"
import type { Evento } from "@/negociacion"
import { Negociacion } from "@/paginas/Negociacion"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaDiferida,
  respuestaJson,
  simularRutas,
} from "@/pruebas/utilidades"
import { formatoMoneda } from "@/tipos"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const ID = "5d1c2b0e-6f4a-4a8e-9f61-3c2a7e0b9d42"
const RUTA = `/api/negociacion/eventos/${ID}`
const EVALUACION = `${RUTA}/evaluacion`
const PESOS_25 = `${EVALUACION}?pesos=25,25,25,25`

const sesion = (
  id: string,
  proveedor: string,
  estado: string,
  fueraDeLimites = false
) => ({
  id,
  proveedor_id: `p-${id}`,
  proveedor_nombre: proveedor,
  estado,
  modo: "agente",
  ronda: 3,
  utilidad: 0.62,
  correo_estado: "enviado",
  correo_error: null,
  fuera_de_limites: fueraDeLimites,
  actualizado_en: "2026-10-14T18:30:00Z",
})

const EVENTO = {
  id: ID,
  folio: "NEG-2026-0001",
  tipo: "compra",
  titulo: "Licencias de correo 2027",
  moneda: "MXN",
  plazo_meses: 12,
  estado: "en_evaluacion",
  fecha_limite: "2026-10-21T23:00:00Z",
  rondas_max: 6,
  estilo: "balanceado",
  contrato_origen_id: null,
  proveedor_vigente_id: null,
  invitados: [
    { id: "p-s1", nombre: "Nube Norte" },
    { id: "p-s2", nombre: "Datos del Sur" },
    { id: "p-s3", nombre: "Cielo Azul" },
  ],
  lineas: [],
  palancas: [],
  referencia_fecha: null,
  creado_por_nombre: "Ana López",
  creado_en: "2026-10-14T18:00:00Z",
  publicado_en: "2026-10-14T18:00:00Z",
  cerrado_en: "2026-10-21T23:00:00Z",
  motivo_cancelacion: null,
  motivo_desierta: null,
  version: 5,
  errores: [],
  avisos: [],
  sesiones: [
    sesion("s1", "Nube Norte", "acuerdo_tentativo"),
    sesion("s2", "Datos del Sur", "acuerdo_tentativo", true),
    sesion("s3", "Cielo Azul", "sin_acuerdo"),
  ],
}

const NORMALIZADOS = { costo: 1, desempeno: 1, riesgo: 1, sla: 1 }

const NUBE_NORTE: Candidato = {
  id: "s1",
  proveedor_id: "p-s1",
  nombre: "Nube Norte",
  costo_total: "480000.00",
  costo_total_mxn: "480000.00",
  desempeno: 82.4,
  riesgo: {
    valor: 0.2,
    nivel: "bajo",
    concentracion: 0.35,
    tendencia: 0.1,
    sin_historial: false,
  },
  sla: "99.90",
  normalizados: NORMALIZADOS,
  aportes: { costo: 40, desempeno: 24, riesgo: 12, sla: 12 },
  puntaje: 78.3,
  lugar: 1,
}
const DATOS_DEL_SUR: Candidato = {
  id: "s2",
  proveedor_id: "p-s2",
  nombre: "Datos del Sur",
  costo_total: "510000.00",
  costo_total_mxn: "510000.00",
  desempeno: 75,
  riesgo: {
    valor: 0.5,
    nivel: "medio",
    concentracion: 0.6,
    tendencia: 0.25,
    sin_historial: true,
  },
  sla: null,
  normalizados: NORMALIZADOS,
  aportes: { costo: 20, desempeno: 20, riesgo: 6, sla: 0 },
  puntaje: 66.1,
  lugar: 2,
}

const RECOMENDACION: Recomendacion = {
  pesos: { costo: 40, desempeno: 30, riesgo: 15, sla: 15 },
  umbral_aprobacion: "500000.00",
  tipo_cambio: null,
  candidatos: [NUBE_NORTE, DATOS_DEL_SUR],
  recomendado: "s1",
  margen: 12.2,
  explicacion: [
    "Nube Norte obtiene el mejor puntaje: 78.3 contra 66.1 de Datos del Sur.",
    "Costo: $480,000.00 aporta 40.0 puntos con un peso de 40.",
    "Si el peso del costo bajara a 10, Datos del Sur quedaría primero.",
  ],
  sensibilidad: [],
}

const CON_RECOMENDACION: Evaluacion = {
  recomendacion: RECOMENDACION,
  vigente: null,
  historial: [],
}
const SIN_ACUERDOS: Evaluacion = {
  recomendacion: null,
  vigente: null,
  historial: [],
}

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

/** Testing Library compara con los espacios duros de Intl ya convertidos en espacios. */
const sinEspaciosDuros = (texto: string) => texto.replace(/\s+/g, " ")

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
    expect(fila("Datos del Sur").getByText("Fuera de límites")).toHaveClass(
      "bg-card"
    )
  })
})
