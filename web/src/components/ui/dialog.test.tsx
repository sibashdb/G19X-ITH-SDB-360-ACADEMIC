import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/dialog"

afterEach(cleanup)

describe("Dialog", () => {
  it("el botón de cierre está en español", () => {
    render(
      <Dialog open>
        <DialogContent aria-describedby={undefined}>
          <DialogTitle>Título</DialogTitle>
        </DialogContent>
      </Dialog>
    )

    expect(screen.getByRole("button", { name: "Cerrar" })).toBeInTheDocument()
  })

  it("el botón de cierre del pie también", () => {
    render(
      <Dialog open>
        <DialogContent aria-describedby={undefined} showCloseButton={false}>
          <DialogTitle>Título</DialogTitle>
          <DialogFooter showCloseButton />
        </DialogContent>
      </Dialog>
    )

    expect(screen.getByRole("button", { name: "Cerrar" })).toBeInTheDocument()
  })
})
