import { act, cleanup, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
import { afterEach, describe, expect, it } from "vitest"
import { DialogoEnlaces } from "@/componentes/negociacion/DialogoEnlaces"
import type { EnlaceInvitacion } from "@/negociacion"

const ENLACE: EnlaceInvitacion = {
  sesion_id: "s1",
  proveedor_nombre: "Nube Norte",
  destinatario: "lucia@nubenorte.example",
  enlace: "http://localhost:8080/portal#t=secreto-123",
  correo_estado: "enviado",
}

/** Un botón abre el diálogo; `#contenido` es el contenedor enfocable del Layout. */
function Arnes({
  abierto = false,
  sinBoton = false,
}: {
  abierto?: boolean
  sinBoton?: boolean
}) {
  const [enlaces, setEnlaces] = useState<EnlaceInvitacion[] | null>(
    abierto ? [ENLACE] : null
  )
  return (
    <>
      <div id="contenido" tabIndex={-1} />
      {!sinBoton && (
        <button type="button" onClick={() => setEnlaces([ENLACE])}>
          Reenviar invitación
        </button>
      )}
      <DialogoEnlaces enlaces={enlaces} alCerrar={() => setEnlaces(null)} />
    </>
  )
}

/** Con `sinFoco`, el diálogo ya está abierto al montar y nada tenía el foco antes. */
async function abrir(sinFoco = false) {
  const { rerender } = render(<Arnes abierto={sinFoco} />)
  if (!sinFoco)
    await userEvent.click(
      screen.getByRole("button", { name: "Reenviar invitación" })
    )
  const dialogo = await screen.findByRole("dialog", {
    name: "Enlace de invitación",
  })
  return { dialogo, rerender }
}

afterEach(cleanup)

describe("DialogoEnlaces", () => {
  it("al cerrar devuelve el foco al botón que lo abrió si sigue en pantalla", async () => {
    const { dialogo } = await abrir()
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Listo" })
    )
    await act(async () => {})
    expect(
      screen.getByRole("button", { name: "Reenviar invitación" })
    ).toHaveFocus()
  })

  it("si el botón que lo abrió ya no está, el foco pasa al contenido", async () => {
    const { dialogo, rerender } = await abrir()
    rerender(<Arnes sinBoton />)
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Listo" })
    )
    await act(async () => {})
    expect(document.getElementById("contenido")).toHaveFocus()
  })

  it("si nada tenía el foco al abrirlo, el foco pasa al contenido y no a <body>", async () => {
    const { dialogo } = await abrir(true)
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Listo" })
    )
    await act(async () => {})
    expect(document.getElementById("contenido")).toHaveFocus()
  })

  it("el aviso de copia está en el árbol aunque esté vacío y se ve al copiar", async () => {
    const { dialogo } = await abrir()
    const aviso = dialogo.querySelector("p[aria-live=polite]")
    expect(aviso).toHaveClass("sr-only")
    await userEvent.click(
      within(dialogo).getByRole("button", {
        name: "Copiar el enlace de Nube Norte",
      })
    )
    expect(aviso).not.toHaveClass("sr-only")
    expect(aviso).not.toBeEmptyDOMElement()
  })
})
