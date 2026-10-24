import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Tablero } from "@/paginas/Tablero"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const ALERTA = {
  id: "riesgo:p2",
  tipo: "riesgo",
  severidad: "alta",
  titulo: "Puntuación baja: Datos del Norte",
  explicacion: "Su puntuación es 31.0 de 100, por debajo del umbral de 40.",
  entidad_tipo: "proveedor",
  entidad_id: "p2",
  entidad_nombre: "Datos del Norte",
  proveedor_id: "p2",
  proveedor_nombre: "Datos del Norte",
  fecha: "2026-10-12",
  ahorro_potencial: null,
  moneda: null,
}

const TABLERO = {
  fecha: "2026-10-12",
  moneda: "MXN",
  gasto_anual: "48200000.00",
  variacion_pct: 3.1,
  por_vencer: 12,
  en_riesgo: 4,
  total_proveedores: 60,
  ahorro_potencial: "1900000.00",
  gasto_por_categoria: [
    { categoria: "nube", monto: "30000000.00" },
    { categoria: "soporte", monto: "18200000.00" },
  ],
  gasto_por_mes: [
    { mes: "2026-09-01", monto: "3900000.00" },
    { mes: "2026-10-01", monto: "4016666.67" },
  ],
  proximos_vencimientos: [
    {
      contrato_id: "c1",
      folio: "CT-0001",
      proveedor_id: "p1",
      proveedor: "Nube Andina",
      servicios: ["Nube pública"],
      fecha_fin: "2026-10-30",
      dias: 18,
      monto_mensual: "125000.00",
    },
  ],
  alertas_principales: [ALERTA],
  mejores: [{ proveedor_id: "p1", nombre: "Nube Andina", puntuacion: 91.2 }],
  peores: [{ proveedor_id: "p2", nombre: "Datos del Norte", puntuacion: 31 }],
  distribucion: [
    { rango: "0-19", proveedores: 0 },
    { rango: "20-39", proveedores: 4 },
    { rango: "40-59", proveedores: 20 },
    { rango: "60-79", proveedores: 30 },
    { rango: "80-100", proveedores: 6 },
  ],
}

const VACIO = {
  ...TABLERO,
  gasto_anual: "0.00",
  variacion_pct: null,
  por_vencer: 0,
  en_riesgo: 0,
  total_proveedores: 0,
  ahorro_potencial: "0.00",
  gasto_por_categoria: [],
  gasto_por_mes: [{ mes: "2026-10-01", monto: "0.00" }],
  proximos_vencimientos: [],
  alertas_principales: [],
  mejores: [],
  peores: [],
  distribucion: TABLERO.distribucion.map((r) => ({ ...r, proveedores: 0 })),
}

const NEGOCIACIONES = {
  por_estado: {
    borrador: 1,
    abierto: 2,
    en_evaluacion: 1,
    pendiente_aprobacion: 1,
    adjudicado: 3,
    desierto: 1,
    cancelado: 0,
  },
  escaladas: 2,
  ahorro: {
    adjudicadas: 3,
    primera_oferta_mxn: "1250000.00",
    adjudicado_mxn: "937500.00",
    ahorro_mxn: "312500.00",
    ahorro_pct: 25.0,
  },
}

const SIN_ADJUDICADAS = {
  por_estado: { ...NEGOCIACIONES.por_estado, adjudicado: 0 },
  escaladas: 0,
  ahorro: {
    adjudicadas: 0,
    primera_oferta_mxn: "0.00",
    adjudicado_mxn: "0.00",
    ahorro_mxn: "0.00",
    ahorro_pct: null,
  },
}

function api(
  tablero: () => Response = () => respuestaJson(TABLERO),
  negociaciones: () => Response = () => respuestaJson(NEGOCIACIONES)
) {
  return simularApi((url) => {
    if (url === "/api/inteligencia/tablero") return tablero()
    if (url === "/api/negociacion/tablero") return negociaciones()
    if (url.startsWith("/api/proveedores/proveedores?"))
      return respuestaJson({ total: 60, elementos: [] })
    return new Response("", { status: 404 })
  })
}

const tarjeta = (elemento: HTMLElement) =>
  elemento.closest<HTMLElement>("[data-slot=card]")!
const seccion = (titulo: string) =>
  tarjeta(screen.getByRole("heading", { name: titulo }))

afterEach(() => {
  cleanup()
  sesionDePrueba.roles = ["admin"]
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe("Tablero", () => {
  it("muestra un esqueleto mientras carga", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    renderizarPagina(<Tablero />)
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando…")
  })

  it("muestra la guía de uso arriba del tablero", async () => {
    api()
    renderizarPagina(<Tablero />)
    expect(
      await screen.findByRole("heading", { name: "Cómo usar PluriOne" })
    ).toBeInTheDocument()
  })

  it("saluda y muestra los cuatro indicadores con su cifra y su enlace", async () => {
    sesionDePrueba.roles = ["comprador"]
    api()
    renderizarPagina(<Tablero />)

    const gasto = tarjeta(await screen.findByText("$48.2 M MXN"))
    expect(screen.getByText(/Hola, Ana\./)).toBeInTheDocument()
    expect(gasto).toHaveTextContent("+3.1 % contra hace 12 meses")
    expect(
      within(gasto).getByRole("link", { name: "Ver proveedores" })
    ).toHaveAttribute("href", "/proveedores?orden=gasto_anual&direccion=desc")
    expect(tarjeta(screen.getByText("Por vencer (90 días)"))).toHaveTextContent(
      "12"
    )
    expect(
      tarjeta(screen.getByText("Proveedores en riesgo"))
    ).toHaveTextContent("4 de 60")
    expect(
      tarjeta(screen.getByRole("button", { name: "Ahorro potencial" }))
    ).toHaveTextContent("$1.9 M MXN")
    expect(
      screen.getByRole("link", { name: "Ver vencimientos" })
    ).toHaveAttribute("href", "/alertas?tipo=vencimiento")
    expect(
      screen.getByRole("link", { name: "Ver proveedores en riesgo" })
    ).toHaveAttribute("href", "/proveedores?en_riesgo=true")
    expect(
      screen.getByRole("link", { name: "Ver sobreprecios" })
    ).toHaveAttribute("href", "/precios?vista=sobreprecios")
    // El aviso temporal y el estado de los datos ya no están en el Tablero.
    expect(screen.queryByRole("note")).not.toBeInTheDocument()
    expect(
      screen.queryByRole("heading", { name: "Estado de los datos" })
    ).not.toBeInTheDocument()
  })

  it("muestra el gasto, los vencimientos, las alertas y los mejores y peores proveedores", async () => {
    api()
    renderizarPagina(<Tablero />)
    await screen.findByText("$48.2 M MXN")

    const categorias = seccion("Gasto por categoría")
    expect(within(categorias).getByText("Nube")).toBeInTheDocument()
    expect(within(categorias).getByText("$30.0 M MXN")).toBeInTheDocument()

    expect(
      screen.getByRole("figure", { name: /Gasto comprometido por mes/ })
    ).toBeInTheDocument()
    expect(screen.getByText("Ver los datos")).toBeInTheDocument()
    expect(screen.getByText("$4,016,666.67")).toBeInTheDocument()

    const vencimientos = seccion("Próximos vencimientos")
    expect(within(vencimientos).getByText("CT-0001")).toBeInTheDocument()
    expect(within(vencimientos).getByText("en 18 días")).toBeInTheDocument()
    expect(within(vencimientos).getByText("$125,000.00")).toBeInTheDocument()
    expect(
      within(vencimientos).getByRole("link", { name: "Nube Andina" })
    ).toHaveAttribute("href", "/proveedores/p1?pestana=contratos")

    expect(
      screen.getByRole("link", { name: "Puntuación baja: Datos del Norte" })
    ).toHaveAttribute("href", "/proveedores/p2")

    const destacados = seccion("Mejores y peores proveedores")
    expect(
      within(destacados).getByRole("link", { name: "Nube Andina" })
    ).toHaveAttribute("href", "/proveedores/p1")
    expect(within(destacados).getByText("91.2")).toBeInTheDocument()
    expect(within(destacados).getByText("31.0")).toBeInTheDocument()
    expect(within(destacados).getByText("20 proveedores")).toBeInTheDocument()
    expect(
      within(destacados).getByRole("button", { name: "puntuación" })
    ).toBeInTheDocument()
  })

  it("en los próximos vencimientos, el contrato y el proveedor se parten en líneas para no ensanchar la tarjeta", async () => {
    api()
    renderizarPagina(<Tablero />)
    await screen.findByText("$48.2 M MXN")

    const vencimientos = seccion("Próximos vencimientos")
    expect(within(vencimientos).getByText("CT-0001").closest("td")).toHaveClass(
      "whitespace-normal"
    )
    expect(
      within(vencimientos)
        .getByRole("link", { name: "Nube Andina" })
        .closest("td")
    ).toHaveClass("whitespace-normal")
  })

  it("el monto mensual de los próximos vencimientos dice que está en MXN", async () => {
    api()
    renderizarPagina(<Tablero />)
    await screen.findByText("$48.2 M MXN")

    expect(
      within(seccion("Próximos vencimientos")).getByRole("columnheader", {
        name: "Monto mensual (MXN)",
      })
    ).toBeInTheDocument()
  })

  it("el comprador puede renovar desde los próximos vencimientos; otros roles no", async () => {
    sesionDePrueba.roles = ["comprador"]
    api()
    renderizarPagina(<Tablero />)
    expect(
      await screen.findByRole("link", { name: "Renovar el contrato CT-0001" })
    ).toHaveAttribute("href", "/negociaciones/nueva?proveedor=p1&contrato=c1")
    cleanup()
    sesionDePrueba.roles = ["admin"]
    api()
    renderizarPagina(<Tablero />)
    await screen.findByText("CT-0001")
    expect(
      screen.queryByRole("link", { name: /^Renovar/ })
    ).not.toBeInTheDocument()
  })

  it("sin datos, cada sección explica qué falta", async () => {
    api(() => respuestaJson(VACIO))
    renderizarPagina(<Tablero />)

    expect(
      await screen.findByText("Sin contratos vigentes")
    ).toBeInTheDocument()
    expect(screen.getByText("Sin gasto comprometido")).toBeInTheDocument()
    expect(screen.getByText("Nada vence pronto")).toBeInTheDocument()
    expect(screen.getByText("No hay alertas activas")).toBeInTheDocument()
    expect(screen.getByText("Aún no hay puntuaciones")).toBeInTheDocument()
    expect(
      tarjeta(screen.getByText("Proveedores en riesgo"))
    ).toHaveTextContent("0 de 0")
  })

  it("si la inteligencia no responde, lo dice y permite reintentar", async () => {
    let fallar = true
    api(() =>
      fallar ? new Response("", { status: 502 }) : respuestaJson(TABLERO)
    )
    renderizarPagina(<Tablero />)

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servicio no está disponible"
    )
    fallar = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(await screen.findByText("$48.2 M MXN")).toBeInTheDocument()
  })

  it("muestra el ahorro logrado y el estado de las negociaciones", async () => {
    sesionDePrueba.roles = ["comprador"]
    api()
    renderizarPagina(<Tablero />)

    const ahorro = tarjeta(
      await screen.findByRole("button", { name: "Ahorro logrado" })
    )
    expect(ahorro).toHaveTextContent("$312.5 mil MXN")
    expect(ahorro).toHaveTextContent(
      "25.0 % frente a la primera oferta, en 3 negociaciones adjudicadas."
    )
    expect(
      within(ahorro).getByRole("link", { name: "Ver adjudicadas" })
    ).toHaveAttribute("href", "/negociaciones?estado=adjudicado")
    const estados = seccion("Estado de las negociaciones")
    expect(within(estados).getAllByRole("link")).toHaveLength(8)
    expect(
      within(estados).getByRole("link", { name: "Escaladas 2" })
    ).toHaveAttribute("href", "/negociaciones?estado=abierto")
    expect(
      within(estados).getByRole("link", { name: "Abierta 2" })
    ).toHaveAttribute("href", "/negociaciones?estado=abierto")
    expect(
      within(estados).getByRole("link", { name: "Por aprobar 1" })
    ).toHaveAttribute("href", "/negociaciones?estado=pendiente_aprobacion")
    expect(
      within(estados).getByRole("link", { name: "Cancelada 0" })
    ).toHaveAttribute("href", "/negociaciones?estado=cancelado")
  })

  it("sin adjudicadas, el ahorro lo explica", async () => {
    api(undefined, () => respuestaJson(SIN_ADJUDICADAS))
    renderizarPagina(<Tablero />)

    const ahorro = tarjeta(
      await screen.findByRole("button", { name: "Ahorro logrado" })
    )
    expect(ahorro).toHaveTextContent(
      "Todavía no hay negociaciones adjudicadas."
    )
    expect(ahorro).not.toHaveTextContent("NaN")
    expect(ahorro).not.toHaveTextContent("%")
  })

  it("si la primera oferta suma 0, el ahorro omite el porcentaje", async () => {
    const cero = {
      ...SIN_ADJUDICADAS,
      ahorro: { ...SIN_ADJUDICADAS.ahorro, adjudicadas: 1 },
    }
    api(undefined, () => respuestaJson(cero))
    renderizarPagina(<Tablero />)

    const ahorro = tarjeta(
      await screen.findByRole("button", { name: "Ahorro logrado" })
    )
    expect(ahorro).toHaveTextContent("En 1 negociación adjudicada.")
    expect(ahorro).not.toHaveTextContent("%")
  })

  it("si la inteligencia no responde, la fila de negociaciones carga por su cuenta", async () => {
    api(() => new Response("", { status: 502 }))
    renderizarPagina(<Tablero />)

    expect(
      await screen.findByRole("button", { name: "Ahorro logrado" })
    ).toBeInTheDocument()
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servicio no está disponible"
    )
  })

  it("un ahorro negativo se muestra con su signo y como advertencia", async () => {
    const negativo = {
      ...NEGOCIACIONES,
      ahorro: {
        ...NEGOCIACIONES.ahorro,
        ahorro_mxn: "-30000.00",
        ahorro_pct: -2.4,
      },
    }
    api(undefined, () => respuestaJson(negativo))
    renderizarPagina(<Tablero />)

    const ahorro = tarjeta(
      await screen.findByRole("button", { name: "Ahorro logrado" })
    )
    expect(ahorro).toHaveTextContent("-30.0 mil MXN")
    expect(ahorro).toHaveTextContent("-2.4 % frente a la primera oferta")
    expect(ahorro.querySelector("[data-tono]")).toHaveAttribute(
      "data-tono",
      "advertencia"
    )
  })

  it("si negociacion no responde, el resto del tablero sigue y la fila permite reintentar", async () => {
    let fallar = true
    api(undefined, () =>
      fallar ? new Response("", { status: 502 }) : respuestaJson(NEGOCIACIONES)
    )
    renderizarPagina(<Tablero />)

    const alerta = await screen.findByRole("alert")
    expect(tarjeta(alerta)).toHaveTextContent("Estado de las negociaciones")
    expect(screen.getByText("$48.2 M MXN")).toBeInTheDocument()
    expect(tarjeta(screen.getByText("Por vencer (90 días)"))).toHaveTextContent(
      "12"
    )
    fallar = false
    await userEvent.click(
      within(tarjeta(alerta)).getByRole("button", { name: "Reintentar" })
    )
    expect(
      await screen.findByRole("button", { name: "Ahorro logrado" })
    ).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    api()
    const { container } = renderizarPagina(<Tablero />)
    await screen.findByText("$48.2 M MXN")
    await screen.findByRole("button", { name: "Ahorro logrado" })
    await screen.findByRole("heading", { name: "Cómo usar PluriOne" })
    await esperarSinViolaciones(container)
  })
})
