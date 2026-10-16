import { render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { TablaContratos } from "@/componentes/TablaContratos"
import type { MercadoLinea } from "@/inteligencia"
import { rutaRenovacion } from "@/negociacion"
import { sesionDePrueba } from "@/pruebas/sesion"
import { renderizarPagina } from "@/pruebas/utilidades"
import type { Contrato } from "@/tipos"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

afterEach(() => {
  sesionDePrueba.roles = ["admin"]
})

const linea = (precio_unitario: string) => ({
  codigo_servicio: "NUBE-01",
  nombre_servicio: "Nube pública",
  unidad: "mes",
  cantidad: "12",
  precio_unitario,
})

const CONTRATO_CON_SERVICIO_REPETIDO = {
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
  // La API permite el mismo servicio en varias líneas del contrato, a precios distintos.
  lineas: [linea("1500.0000"), linea("900.0000")],
} as Contrato

// La inteligencia guarda una sola línea por (contrato, servicio): aquí, la de 1,500.
const MERCADO: MercadoLinea[] = [
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

describe("TablaContratos", () => {
  it("con un servicio repetido a precios distintos, solo la línea que coincide se compara con el mercado", () => {
    render(
      <TablaContratos
        contratos={[CONTRATO_CON_SERVICIO_REPETIDO]}
        mercado={MERCADO}
      />
    )

    const [, coincide, distinta] = screen.getAllByRole("row")
    expect(
      within(coincide).getByRole("button", { name: "Sobre P75" })
    ).toBeInTheDocument()
    expect(within(distinta).queryByRole("button")).not.toBeInTheDocument()
    expect(within(distinta).getByText("—")).toBeInTheDocument()
    expect(
      within(distinta).getByText("Sin comparación con el mercado")
    ).toBeInTheDocument()
  })

  it("ofrece «Renovar» solo al comprador y solo en contratos vigentes", () => {
    sesionDePrueba.roles = ["comprador"]
    const vigente = {
      ...CONTRATO_CON_SERVICIO_REPETIDO,
      fecha_inicio: "2000-01-01",
      fecha_fin: "2999-12-31",
    }
    const vencido = {
      ...vigente,
      id: "c2",
      folio: "CT-0002",
      fecha_fin: "2000-12-31",
    }
    renderizarPagina(
      <TablaContratos contratos={[vigente, vencido]} proveedorId="p1" />
    )
    expect(
      screen.getByRole("link", { name: "Renovar el contrato CT-0001" })
    ).toHaveAttribute("href", rutaRenovacion("p1", "c1"))
    expect(
      screen.queryByRole("link", { name: "Renovar el contrato CT-0002" })
    ).not.toBeInTheDocument()
  })
})
