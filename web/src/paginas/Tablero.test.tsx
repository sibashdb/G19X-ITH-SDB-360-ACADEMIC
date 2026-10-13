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

function api(tablero: () => Response = () => respuestaJson(TABLERO)) {
  return simularApi((url) => {
    if (url === "/api/inteligencia/tablero") return tablero()
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

  it("no tiene violaciones de accesibilidad", async () => {
    api()
    const { container } = renderizarPagina(<Tablero />)
    await screen.findByText("$48.2 M MXN")
    await screen.findByRole("heading", { name: "Cómo usar PluriOne" })
    await esperarSinViolaciones(container)
  })
})
