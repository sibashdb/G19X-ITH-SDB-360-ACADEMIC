import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { BarraPuntuacion } from "@/componentes/BarraPuntuacion"
import { ElementoAlerta } from "@/componentes/ElementoAlerta"
import { PosicionMercado } from "@/componentes/PosicionMercado"
import { Tendencia } from "@/componentes/Tendencia"
import type { Alerta, MercadoLinea } from "@/inteligencia"
import { esperarSinViolaciones, renderizarPagina } from "@/pruebas/utilidades"

// ElementoAlerta lee los roles de la sesión para ofrecer «Renovar».
vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

afterEach(cleanup)

const LINEA: MercadoLinea = {
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
  confianza: "baja",
  ahorro_potencial: "3600.00",
}

const ALERTA: Alerta = {
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

describe("BarraPuntuacion", () => {
  it("muestra la cifra, pinta la barra según su rango y marca el historial corto", () => {
    const { container } = renderizarPagina(
      <BarraPuntuacion puntuacion={72.4} confianza="baja" umbral={40} />
    )
    expect(screen.getByText("72.4")).toBeInTheDocument()
    expect(screen.getByText("Historial corto")).toBeInTheDocument()
    const barra = container.querySelector("[data-rango]")
    expect(barra).toHaveAttribute("data-rango", "alto")
    expect(barra).toHaveStyle({ width: "72.4%" })
  })

  it("debajo del umbral la barra es de riesgo", () => {
    const { container } = renderizarPagina(
      <BarraPuntuacion puntuacion={31} confianza="normal" umbral={40} />
    )
    expect(container.querySelector("[data-rango]")).toHaveAttribute(
      "data-rango",
      "bajo"
    )
    expect(screen.queryByText("Historial corto")).not.toBeInTheDocument()
  })

  it("sin puntuación lo dice con texto", () => {
    renderizarPagina(
      <BarraPuntuacion puntuacion={null} confianza={null} umbral={40} />
    )
    expect(screen.getByText("Sin datos")).toBeInTheDocument()
  })
})

describe("Tendencia", () => {
  it.each([
    [3.2, "+3.2 puntos en 3 meses"],
    [-4.1, "-4.1 puntos en 3 meses"],
    [0, "0.0 puntos en 3 meses"],
  ])("con %s dice el cambio con su signo", (valor, texto) => {
    const { container } = renderizarPagina(<Tendencia valor={valor} />)
    expect(container).toHaveTextContent(texto)
  })

  it("sin historia suficiente lo dice al lector de pantalla", () => {
    renderizarPagina(<Tendencia valor={null} />)
    expect(screen.getByText("Sin tendencia")).toHaveClass("sr-only")
  })
})

describe("PosicionMercado", () => {
  it("dice la posición con texto y abre el detalle del mercado", async () => {
    renderizarPagina(<PosicionMercado linea={LINEA} />)

    await userEvent.click(screen.getByRole("button", { name: "Sobre P75" }))

    const detalle = await screen.findByRole("dialog", {
      name: "Nube pública frente al mercado",
    })
    expect(detalle).toHaveTextContent("$1,500.00")
    expect(detalle).toHaveTextContent("$1,400.00")
    expect(detalle).toHaveTextContent("Ahorro potencial")
    expect(detalle).toHaveTextContent("$3,600.00")
    expect(detalle).toHaveTextContent("baja confianza")
  })

  it("sin referencia lo dice con texto", () => {
    renderizarPagina(
      <PosicionMercado
        linea={{ ...LINEA, posicion: null, p25: null, p50: null, p75: null }}
      />
    )
    expect(screen.getByText("Sin referencia")).toBeInTheDocument()
  })
})

describe("ElementoAlerta", () => {
  it("muestra la severidad con texto, enlaza a su proveedor y no tiene violaciones", async () => {
    const { container } = renderizarPagina(<ElementoAlerta alerta={ALERTA} />)

    // "Severidad" es solo para lectores de pantalla; a la vista queda "Alta".
    expect(container.querySelector("[data-slot=badge]")).toHaveTextContent(
      "Severidad Alta"
    )
    expect(
      screen.getByRole("link", { name: "Puntuación baja: Datos del Norte" })
    ).toHaveAttribute("href", "/proveedores/p2")
    expect(screen.getByText(ALERTA.explicacion)).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })
})
