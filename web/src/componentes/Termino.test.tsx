import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it } from "vitest"
import { Termino } from "@/componentes/Termino"
import { GLOSARIO } from "@/glosario"
import { esperarSinViolaciones, renderizarPagina } from "@/pruebas/utilidades"

afterEach(cleanup)

describe("Termino", () => {
  it("su nombre accesible es el texto visible y abre la definición con un clic", async () => {
    renderizarPagina(
      <p>
        Pagas <Termino clave="sobreprecio">sobreprecio</Termino> en 2 contratos.
      </p>
    )
    const disparador = screen.getByRole("button", { name: "sobreprecio" })
    await userEvent.click(disparador)

    const ayuda = await screen.findByRole("dialog", { name: "Sobreprecio" })
    expect(ayuda).toHaveTextContent(GLOSARIO.sobreprecio.definicion)
    expect(ayuda).toHaveAccessibleDescription(GLOSARIO.sobreprecio.definicion)
  })

  it("se abre con Enter, se cierra con Escape y devuelve el foco al término", async () => {
    renderizarPagina(<Termino clave="sla" />)
    const disparador = screen.getByRole("button", { name: "SLA" })
    disparador.focus()

    await userEvent.keyboard("{Enter}")
    expect(
      await screen.findByRole("dialog", { name: "SLA" })
    ).toBeInTheDocument()

    await userEvent.keyboard("{Escape}")
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(disparador).toHaveFocus()
  })

  it("sin texto propio muestra el nombre del término del glosario", () => {
    renderizarPagina(<Termino clave="percentiles" />)
    expect(
      screen.getByRole("button", { name: GLOSARIO.percentiles.termino })
    ).toBeInTheDocument()
  })

  it("todas las definiciones del glosario existen y no están vacías", () => {
    for (const { termino, definicion } of Object.values(GLOSARIO)) {
      expect(termino.length).toBeGreaterThan(0)
      expect(definicion.length).toBeGreaterThan(20)
    }
  })

  it("el ideal y el acuerdo tentativo dicen lo que hace el agente, no más", () => {
    expect(GLOSARIO.ideal.definicion).toBe(
      "El valor que a usted le gustaría conseguir. El agente empieza pidiendo casi ese valor y cede poco a poco hacia el límite."
    )
    expect(GLOSARIO.acuerdoTentativo.definicion).toBe(
      "El proveedor aceptó o propuso una oferta que se registró como acuerdo. No es vinculante hasta que se adjudique y se apruebe; si sale de sus límites, se marca para el aprobador."
    )
  })

  it("no tiene violaciones de accesibilidad abierto ni cerrado", async () => {
    const { container } = renderizarPagina(<Termino clave="ahorroPotencial" />)
    await esperarSinViolaciones(container)
    await userEvent.click(
      screen.getByRole("button", { name: "Ahorro potencial" })
    )
    await esperarSinViolaciones(document.body)
  })
})
