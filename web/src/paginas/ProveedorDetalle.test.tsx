import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { formatearValorTooltip } from "@/componentes/DesempenoProveedor"
import { ProveedorDetalle } from "@/paginas/ProveedorDetalle"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
} from "@/pruebas/utilidades"
import { formatoPeriodo } from "@/tipos"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const RUTA = "/api/proveedores/proveedores/p1"

const PROVEEDOR = {
  id: "p1",
  rfc: "AAA010101AAA",
  nombre: "Proveedor Uno",
  tamano: "mediana",
  categorias: ["nube"],
  activo: true,
  contacto_nombre: "Ana Pérez",
  contacto_email: "ana@ejemplo.test",
  contratos_vigentes: 1,
}

const CONTRATO = {
  id: "c1",
  folio: "CT-0001",
  tipo: "nuevo",
  fecha_inicio: "2026-01-01",
  fecha_fin: "2026-12-31",
  moneda: "MXN",
  plazo_pago_dias: 30,
  sla_disponibilidad: null,
  tope_aumento_pct: null,
  cuota_implementacion: "0",
  lineas: [
    {
      codigo_servicio: "NUBE-01",
      nombre_servicio: "Nube pública",
      unidad: "mes",
      cantidad: "12",
      precio_unitario: "1500.0000",
    },
  ],
}

const DESEMPENO = [
  {
    periodo: "2026-08-01",
    sla_cumplimiento_pct: "99.10",
    tiempo_resolucion_h: "4.50",
    incidentes_criticos: 1,
    entregas_a_tiempo_pct: "95.00",
    satisfaccion: "4.40",
  },
  {
    periodo: "2026-07-01",
    sla_cumplimiento_pct: "98.70",
    tiempo_resolucion_h: "5.20",
    incidentes_criticos: 2,
    entregas_a_tiempo_pct: "92.00",
    satisfaccion: "4.10",
  },
]

const INTELIGENCIA = "/api/inteligencia/proveedores/p1"
const ALERTAS_URL = "/api/inteligencia/alertas?proveedor=p1&limite=3"

const PUNTUACION = {
  proveedor_id: "p1",
  categoria: "nube",
  puntuacion: 72.4,
  sin_ajuste: 74,
  meses: 12,
  historial_corto: false,
  tendencia: 3.2,
  componentes: [
    { kpi: "sla", valor: 99.12, mediana_categoria: 98.7, percentil: 80 },
    { kpi: "resolucion", valor: 4.5, mediana_categoria: 5.1, percentil: 65 },
    { kpi: "incidentes", valor: 1.2, mediana_categoria: 1.5, percentil: 60 },
    { kpi: "entregas", valor: 95, mediana_categoria: 92, percentil: 70 },
    { kpi: "satisfaccion", valor: 4.4, mediana_categoria: 4.1, percentil: 75 },
  ],
  historial: [
    { mes: "2025-11-01", puntuacion: 65 },
    { mes: "2026-10-01", puntuacion: 72.4 },
  ],
}

const MERCADO = [
  {
    contrato_id: "c1",
    folio: "CT-0001",
    codigo_servicio: "NUBE-01",
    servicio: "Nube pública",
    moneda: "MXN",
    precio: "1500.0000",
    posicion: "sobre_p75",
    p25: "1000.0000",
    p50: "1200.0000",
    p75: "1400.0000",
    metodo: "modelo",
    confianza: "normal",
    ahorro_potencial: "3600.00",
  },
]

const ALERTAS = {
  total: 2,
  elementos: [
    {
      id: "sobreprecio:c1:NUBE-01",
      tipo: "sobreprecio",
      severidad: "media",
      titulo: "Sobreprecio en CT-0001: Nube pública",
      explicacion:
        "Paga 1,500.00 MXN por mes; el mercado paga hasta 1,400.00 (P75).",
      entidad_tipo: "contrato",
      entidad_id: "c1",
      entidad_nombre: "CT-0001",
      proveedor_id: "p1",
      proveedor_nombre: "Proveedor Uno",
      fecha: "2026-10-12",
      ahorro_potencial: "3600.00",
      moneda: "MXN",
    },
  ],
}

function api(cambios: Record<string, () => Response | Promise<Response>> = {}) {
  return simularApi({
    [RUTA]: () => respuestaJson(PROVEEDOR),
    [`${RUTA}/contratos`]: () => respuestaJson([CONTRATO]),
    [`${RUTA}/desempeno?meses=24`]: () => respuestaJson(DESEMPENO),
    [`${INTELIGENCIA}/puntuacion`]: () => respuestaJson(PUNTUACION),
    [`${INTELIGENCIA}/mercado`]: () => respuestaJson(MERCADO),
    [ALERTAS_URL]: () => respuestaJson(ALERTAS),
    ...cambios,
  })
}

const renderizar = (ruta = "/proveedores/p1") =>
  renderizarPagina(<ProveedorDetalle />, { ruta, patron: "/proveedores/:id" })

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("ProveedorDetalle", () => {
  it("muestra la ficha del proveedor", async () => {
    api()
    renderizar()

    expect(
      await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })
    ).toBeInTheDocument()
    expect(screen.getByText("AAA010101AAA")).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: "ana@ejemplo.test" })
    ).toHaveAttribute("href", "mailto:ana@ejemplo.test")
    expect(screen.getByText("Activo")).toBeInTheDocument()
  })

  it("el resumen muestra el desempeño del último mes", async () => {
    api()
    renderizar()

    expect(
      await screen.findByRole("heading", {
        name: `Desempeño de ${formatoPeriodo("2026-08-01")}`,
      })
    ).toBeInTheDocument()
    expect(screen.getByText("99.10 %")).toBeInTheDocument()
    expect(screen.getByText("4.40 de 5")).toBeInTheDocument()
  })

  it("muestra Cargando mientras llega el desempeño", async () => {
    let liberar = () => {}
    const espera = new Promise<void>((resolver) => {
      liberar = resolver
    })
    api({
      [`${RUTA}/desempeno?meses=24`]: () =>
        espera.then(() => respuestaJson(DESEMPENO)),
    })
    renderizar()

    await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })
    expect(screen.getByRole("status")).toHaveTextContent("Cargando…")
    liberar()
    expect(await screen.findByText("99.10 %")).toBeInTheDocument()
  })

  it("la pestaña Contratos se refleja en la URL y lista las líneas", async () => {
    api()
    renderizar()
    await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })

    await userEvent.click(screen.getByRole("tab", { name: "Contratos" }))

    expect(await screen.findByText("CT-0001")).toBeInTheDocument()
    expect(screen.getByText("Nube pública")).toBeInTheDocument()
    expect(ubicacionActual()).toBe("/proveedores/p1?pestana=contratos")
    // Con scroll horizontal y sin elementos enfocables, el teclado solo llega si el contenedor lo es.
    expect(screen.getByRole("table").parentElement).toHaveAttribute(
      "tabindex",
      "0"
    )
    // outline-none es outline-style: none y el modo de alto contraste no muestra el foco.
    expect(screen.getByRole("table").parentElement).toHaveClass(
      "outline-hidden"
    )
  })

  it("no repite claves de fila cuando un contrato incluye el mismo servicio dos veces", async () => {
    const repetida = { ...CONTRATO.lineas[0], cantidad: "3" }
    api({
      [`${RUTA}/contratos`]: () =>
        respuestaJson([
          { ...CONTRATO, lineas: [CONTRATO.lineas[0], repetida] },
        ]),
    })
    const registro = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined)
    renderizar("/proveedores/p1?pestana=contratos")

    await screen.findByText("CT-0001")

    expect(screen.getAllByText("Nube pública")).toHaveLength(2)
    expect(registro).not.toHaveBeenCalled()
    registro.mockRestore()
  })

  it("avisa con una alerta cuando falla la consulta de contratos", async () => {
    api({
      [`${RUTA}/contratos`]: () => new Response("Bad Gateway", { status: 502 }),
    })
    renderizar("/proveedores/p1?pestana=contratos")

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servicio no está disponible; intente más tarde."
    )
    expect(
      screen.queryByText("Sin contratos registrados")
    ).not.toBeInTheDocument()
  })

  it("muestra que no hay contratos cuando la lista llega vacía", async () => {
    api({ [`${RUTA}/contratos`]: () => respuestaJson([]) })
    renderizar("/proveedores/p1?pestana=contratos")

    expect(
      await screen.findByText("Sin contratos registrados")
    ).toBeInTheDocument()
  })

  it("muestra que no hay datos cuando el desempeño llega vacío", async () => {
    api({ [`${RUTA}/desempeno?meses=24`]: () => respuestaJson([]) })
    renderizar()

    expect(
      await screen.findByText("Sin datos de desempeño")
    ).toBeInTheDocument()
  })

  it("la pestaña Desempeño muestra la gráfica y la tabla del indicador elegido", async () => {
    api()
    renderizar("/proveedores/p1?pestana=desempeno")

    expect(
      await screen.findByRole("figure", {
        name: "Cumplimiento de SLA de los últimos 2 meses",
      })
    ).toBeInTheDocument()
    const tabla = screen.getByRole("table")
    expect(within(tabla).getAllByRole("row")).toHaveLength(3)
    expect(tabla.parentElement).toHaveAttribute("tabindex", "0")

    await userEvent.click(screen.getByRole("combobox", { name: "Indicador" }))
    await userEvent.click(
      await screen.findByRole("option", { name: "Satisfacción" })
    )

    expect(
      screen.getByRole("figure", {
        name: "Satisfacción de los últimos 2 meses",
      })
    ).toBeInTheDocument()
  })

  // Recharts no dibuja la gráfica en jsdom (el contenedor mide 0), así que la leyenda y el tooltip
  // no se pueden consultar en el DOM; el formato del valor del tooltip se prueba directamente.
  it("el tooltip de la gráfica muestra el valor con su unidad, igual que la tabla", () => {
    expect(formatearValorTooltip(99.1, "99.10", "%")).toBe("99.10 %")
    expect(formatearValorTooltip(4.4, "4.40", "de 5")).toBe("4.40 de 5")
    expect(formatearValorTooltip(2, "2", "")).toBe("2")
    expect(formatearValorTooltip(95, undefined, "%")).toBe("95 %")
  })

  it("una pestaña desconocida en la URL muestra el resumen", async () => {
    api()
    renderizar("/proveedores/p1?pestana=inventada")

    expect(await screen.findByRole("tab", { name: "Resumen" })).toHaveAttribute(
      "aria-selected",
      "true"
    )
  })

  it("el encabezado muestra la puntuación, su tendencia y las alertas activas", async () => {
    api()
    renderizar()

    expect(await screen.findByText("72.4")).toBeInTheDocument()
    expect(screen.getByText("de 100")).toBeInTheDocument()
    expect(
      screen.getByText("puntos en 3 meses", { exact: false }).parentElement
    ).toHaveTextContent("+3.2 puntos en 3 meses")
    expect(
      screen.getByText("Últimos 2 meses: de 65.0 a 72.4")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("heading", { name: "Alertas activas (2)" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: "Sobreprecio en CT-0001: Nube pública" })
    ).toHaveAttribute("href", "/proveedores/p1?pestana=contratos")
    expect(
      screen.getByRole("link", { name: "Ver sus 2 alertas" })
    ).toHaveAttribute("href", "/alertas?proveedor=p1")
  })

  it("el resumen compara cada indicador con la mediana de su categoría", async () => {
    api()
    renderizar()

    expect(
      await screen.findByRole("heading", { name: "Frente a su categoría" })
    ).toBeInTheDocument()
    const sla = screen.getByText("Percentil 80.0").closest("li")!
    expect(sla).toHaveTextContent("Cumplimiento de SLA")
    expect(sla).toHaveTextContent("99.12 %")
    expect(sla).toHaveTextContent("mediana 98.7 %")
    expect(
      screen.getByRole("button", { name: "percentil" })
    ).toBeInTheDocument()
  })

  it("la pestaña Contratos compara cada línea vigente con el mercado", async () => {
    api()
    renderizar("/proveedores/p1?pestana=contratos")

    expect(
      await screen.findByRole("button", { name: "Sobre P75" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("columnheader", { name: "Precio vs. mercado" })
    ).toBeInTheDocument()
  })

  it("la ficha se muestra aunque la inteligencia no responda", async () => {
    const caida = () => new Response("", { status: 502 })
    api({
      [`${INTELIGENCIA}/puntuacion`]: caida,
      [`${INTELIGENCIA}/mercado`]: caida,
      [ALERTAS_URL]: caida,
    })
    renderizar("/proveedores/p1?pestana=contratos")

    expect(
      await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })
    ).toBeInTheDocument()
    expect(await screen.findByText("No se pudo consultar.")).toBeInTheDocument()
    expect(
      screen.getByText("No se pudieron consultar sus alertas.")
    ).toBeInTheDocument()
    expect(
      screen.getByText("No se pudo comparar con el mercado.")
    ).toBeInTheDocument()
    expect(await screen.findByText("CT-0001")).toBeInTheDocument()
    expect(
      screen.queryByRole("columnheader", { name: "Precio vs. mercado" })
    ).not.toBeInTheDocument()
  })

  it("un proveedor que la inteligencia aún no conoce se ve sin puntuación", async () => {
    api({
      [`${INTELIGENCIA}/puntuacion`]: () => new Response("", { status: 404 }),
    })
    renderizar()

    expect(
      await screen.findByText("Sin puntuación todavía")
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("heading", { name: "Frente a su categoría" })
    ).not.toBeInTheDocument()
  })

  it("codifica el id al construir la ruta de la API", async () => {
    simularApi({
      "/api/proveedores/proveedores/a%20b%3Fx": () => respuestaJson(PROVEEDOR),
      "/api/proveedores/proveedores/a%20b%3Fx/contratos": () =>
        respuestaJson([]),
      "/api/proveedores/proveedores/a%20b%3Fx/desempeno?meses=24": () =>
        respuestaJson([]),
    })
    renderizar("/proveedores/a%20b%3Fx")

    expect(
      await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })
    ).toBeInTheDocument()
  })

  it("un proveedor inexistente ofrece volver a la lista", async () => {
    simularApi({})
    renderizar()

    expect(
      await screen.findByText("El proveedor no existe")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: "Volver a proveedores" })
    ).toHaveAttribute("href", "/proveedores")
  })

  it("un error al cargar la ficha permite reintentar", async () => {
    let fallar = true
    api({
      [RUTA]: () =>
        fallar ? new Response("", { status: 503 }) : respuestaJson(PROVEEDOR),
    })
    renderizar()

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Servicio no disponible"
    )
    fallar = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(
      await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })
    ).toBeInTheDocument()
  })

  it.each(["resumen", "contratos", "desempeno"])(
    "la pestaña %s no tiene violaciones de accesibilidad",
    async (pestana) => {
      api()
      const { container } = renderizar(`/proveedores/p1?pestana=${pestana}`)
      await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })
      await screen.findByRole("tabpanel")
      await esperarSinViolaciones(container)
    }
  )

  it("sugiere ver precios y compararlo en el ranking de su categoría", async () => {
    api()
    renderizar()
    await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })
    expect(
      screen.getByRole("link", { name: /Ver precios de sus servicios/ })
    ).toHaveAttribute("href", "/precios")
    expect(
      screen.getByRole("link", { name: /Compararlo en el ranking/ })
    ).toHaveAttribute("href", "/ranking?categoria=nube")
  })

  it("un proveedor sin categorías lleva al ranking general", async () => {
    api({ [RUTA]: () => respuestaJson({ ...PROVEEDOR, categorias: [] }) })
    renderizar()
    await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })
    expect(
      screen.getByRole("link", { name: /Compararlo en el ranking/ })
    ).toHaveAttribute("href", "/ranking")
  })
})
