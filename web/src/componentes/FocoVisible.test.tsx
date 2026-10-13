import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Select, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

afterEach(cleanup)

// outline-none es `outline-style: none`: el modo de alto contraste de Windows no pinta el foco.
// outline-hidden deja un contorno transparente que ese modo sí muestra.
describe("foco visible en alto contraste", () => {
  it("los controles usan outline-hidden y no outline-none", () => {
    render(
      <>
        <Button>Guardar</Button>
        <Input aria-label="Nombre" />
        <Checkbox aria-label="Acepto" />
        <Select>
          <SelectTrigger aria-label="Opción">
            <SelectValue />
          </SelectTrigger>
        </Select>
        <Tabs defaultValue="a">
          <TabsList>
            <TabsTrigger value="a">A</TabsTrigger>
          </TabsList>
          <TabsContent value="a">Contenido</TabsContent>
        </Tabs>
      </>
    )
    for (const control of [
      screen.getByRole("button", { name: "Guardar" }),
      screen.getByRole("textbox", { name: "Nombre" }),
      screen.getByRole("checkbox", { name: "Acepto" }),
      screen.getByRole("combobox", { name: "Opción" }),
      screen.getByRole("tabpanel"),
    ]) {
      expect(control).toHaveClass("outline-hidden")
      expect(control).not.toHaveClass("outline-none")
    }
  })
})
