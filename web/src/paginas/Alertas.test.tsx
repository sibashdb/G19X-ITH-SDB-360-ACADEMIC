import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Alertas } from "@/paginas/Alertas"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
  urlDeLlamada,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const PROVEEDOR = "0b6a3f5e-1c2d-4e5f-8a9b-0c1d2e3f4a5b"
const VENCIMIENTO = {
  id: "vencimiento:c1",
  tipo: "vencimiento",
  severidad: "alta",
  titulo: "Vence en 12 días: CT-0001",
  explicacion:
    "El contrato con Nube Andina (Nube pública) termina el 24/10/2026.",
  entidad_tipo: "contrato",
  entidad_id: "c1",
  entidad_nombre: "CT-0001",
  proveedor_id: PROVEEDOR,
  proveedor_nombre: "Nube Andina",
  fecha: "2026-10-24",
  ahorro_potencial: null,
  moneda: null,
}
const SOBREPRECIO = {
  ...VENCIMIENTO,
  id: "sobreprecio:c1:NUBE-01",
  tipo: "sobreprecio",
  severidad: "media",
  titulo: "Sobreprecio en CT-0001: Nube pública",
  explicacion:
    "Paga 1,500.00 MXN por mes; el mercado paga hasta 1,400.00 (P75). Pagando el precio típico (1,200.00) ahorraría 3,600.00 MXN en lo que resta del contrato.",
  fecha: "2026-10-12",
  ahorro_potencial: "3600.00",
  moneda: "MXN",
}
const PAGINA = { total: 2, elementos: [VENCIMIENTO, SOBREPRECIO] }
const VACIA = { total: 0, elementos: [] }

function api(respuesta: () => Response = () => respuestaJson(PAGINA)) {
  return simularApi((url) =>
    url.startsWith("/api/inteligencia/alertas?")
      ? respuesta()
      : new Response("", { status: 404 })
  )
}

const renderizar = (ruta = "/alertas") =>
  renderizarPagina(<Alertas />, { ruta })

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Alertas", () => {
  it("muestra un esqueleto mientras carga", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    renderizar()
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando…")
  })

  it("lista las alertas con su severidad, su explicación y el enlace a su proveedor", async () => {
    api()
    renderizar()

    expect(
      await screen.findByRole("link", { name: "Vence en 12 días: CT-0001" })
    ).toHaveAttribute("href", `/proveedores/${PROVEEDOR}?pestana=contratos`)
    expect(screen.getByText(SOBREPRECIO.explicacion)).toBeInTheDocument()
    expect(screen.getByText("Mostrando 1–2 de 2 alertas")).toBeInTheDocument()
  })

  it("lee los filtros de la URL, los envía y los quita con un solo botón que deja el foco en Tipo", async () => {
    const simulado = api(() => respuestaJson(VACIA))
    renderizar(
      `/alertas?tipo=vencimiento&severidad=alta&proveedor=${PROVEEDOR}`
    )

    expect(
      await screen.findByText("Ninguna alerta coincide con los filtros")
    ).toBeInTheDocument()
    expect(screen.getByRole("combobox", { name: "Tipo" })).toHaveTextContent(
      "Contrato por vencer"
    )
    expect(
      screen.getByRole("combobox", { name: "Severidad" })
    ).toHaveTextContent("Alta")
    const url = urlDeLlamada(simulado)
    expect(url.searchParams.get("tipo")).toBe("vencimiento")
    expect(url.searchParams.get("severidad")).toBe("alta")
    expect(url.searchParams.get("proveedor")).toBe(PROVEEDOR)
    expect(url.searchParams.get("limite")).toBe("25")
    expect(url.searchParams.get("pagina")).toBe("1")

    const quitar = screen.getAllByRole("button", { name: "Quitar filtros" })
    expect(quitar).toHaveLength(1)
    await userEvent.click(quitar[0])

    expect(ubicacionActual()).toBe("/alertas")
    expect(screen.getByRole("combobox", { name: "Tipo" })).toHaveFocus()
  })

  it("cambiar el tipo actualiza la URL y vuelve a la primera página", async () => {
    api()
    renderizar("/alertas?pagina=2")
    await userEvent.click(screen.getByRole("combobox", { name: "Tipo" }))
    await userEvent.click(
      await screen.findByRole("option", { name: "Sobreprecio" })
    )
    expect(ubicacionActual()).toBe("/alertas?tipo=sobreprecio")
  })

  it("un proveedor inválido en la URL se ignora, igual que los demás valores inválidos", async () => {
    const simulado = api()
    renderizar(
      "/alertas?tipo=inventado&severidad=x&proveedor=no-es-uuid&pagina=abc"
    )
    await screen.findByText("Mostrando 1–2 de 2 alertas")

    const url = urlDeLlamada(simulado)
    expect(url.searchParams.has("tipo")).toBe(false)
    expect(url.searchParams.has("severidad")).toBe(false)
    expect(url.searchParams.has("proveedor")).toBe(false)
    expect(url.searchParams.get("pagina")).toBe("1")
    expect(screen.getByRole("combobox", { name: "Tipo" })).toHaveTextContent(
      "Todos los tipos"
    )
    expect(
      screen.queryByRole("button", { name: "Quitar filtros" })
    ).not.toBeInTheDocument()
  })

  it("pagina de 25 en 25", async () => {
    const simulado = api(() => respuestaJson({ ...PAGINA, total: 60 }))
    renderizar()
    expect(
      await screen.findByText("Mostrando 1–25 de 60 alertas")
    ).toBeInTheDocument()

    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }))

    expect(ubicacionActual()).toBe("/alertas?pagina=2")
    expect(urlDeLlamada(simulado).searchParams.get("pagina")).toBe("2")
  })

  it("una página fuera de rango ofrece volver a la primera", async () => {
    api(() => respuestaJson({ total: 30, elementos: [] }))
    renderizar("/alertas?pagina=5")

    expect(
      await screen.findByText("Esta página no tiene resultados")
    ).toBeInTheDocument()
    expect(screen.getByText(/Hay 30 alertas activas/)).toBeInTheDocument()
    await userEvent.click(
      screen.getByRole("button", { name: "Ir a la primera página" })
    )
    expect(ubicacionActual()).toBe("/alertas")
    expect(screen.getByRole("combobox", { name: "Tipo" })).toHaveFocus()
  })

  it("sin alertas explica qué aparecerá aquí", async () => {
    api(() => respuestaJson(VACIA))
    renderizar()
    expect(
      await screen.findByText("No hay alertas activas")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "sobreprecio" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "puntuación" })
    ).toBeInTheDocument()
  })

  it("si el servicio no responde, lo dice y permite reintentar", async () => {
    let fallar = true
    api(() =>
      fallar ? new Response("", { status: 502 }) : respuestaJson(PAGINA)
    )
    renderizar()

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servicio no está disponible"
    )
    fallar = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(
      await screen.findByText("Mostrando 1–2 de 2 alertas")
    ).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    api()
    const { container } = renderizar()
    await screen.findByText("Mostrando 1–2 de 2 alertas")
    await esperarSinViolaciones(container)
  })

  it("sugiere ver proveedores y revisar precios", async () => {
    api()
    renderizar()
    expect(
      await screen.findByRole("link", { name: /Ver proveedores/ })
    ).toHaveAttribute("href", "/proveedores")
    expect(
      screen.getByRole("link", { name: /Revisar precios/ })
    ).toHaveAttribute("href", "/precios")
  })
})
