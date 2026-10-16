import { cleanup, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ElementoAlerta } from "@/componentes/ElementoAlerta"
import type { Alerta } from "@/inteligencia"
import { sesionDePrueba } from "@/pruebas/sesion"
import { renderizarPagina } from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const VENCIMIENTO: Alerta = {
  id: "vencimiento:c1",
  tipo: "vencimiento",
  severidad: "alta",
  titulo: "El contrato CT-0001 vence en 25 días",
  explicacion: "Nube pública con Nube Andina.",
  entidad_tipo: "contrato",
  entidad_id: "c1",
  entidad_nombre: "CT-0001",
  proveedor_id: "p1",
  proveedor_nombre: "Nube Andina",
  fecha: "2026-11-07",
  ahorro_potencial: null,
  moneda: null,
}

afterEach(() => {
  cleanup()
  sesionDePrueba.roles = ["admin"]
})

describe("ElementoAlerta", () => {
  it("una alerta de vencimiento ofrece renovar el contrato al comprador", () => {
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<ElementoAlerta alerta={VENCIMIENTO} />)
    expect(
      screen.getByRole("link", { name: "Renovar el contrato CT-0001" })
    ).toHaveAttribute("href", "/negociaciones/nueva?proveedor=p1&contrato=c1")
  })

  it("no lo ofrece a otros roles ni en alertas que no son de vencimiento", () => {
    renderizarPagina(<ElementoAlerta alerta={VENCIMIENTO} />)
    expect(
      screen.queryByRole("link", { name: /^Renovar/ })
    ).not.toBeInTheDocument()
    cleanup()
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(
      <ElementoAlerta
        alerta={{ ...VENCIMIENTO, tipo: "riesgo", entidad_tipo: "proveedor" }}
      />
    )
    expect(
      screen.queryByRole("link", { name: /^Renovar/ })
    ).not.toBeInTheDocument()
  })
})
