import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import { Button } from "@/components/ui/button"

afterEach(cleanup)

describe("Button", () => {
  it("«destructive» es un relleno sólido con el texto del token de primer plano, para pasar 4.5:1", () => {
    // jsdom no calcula contraste: se fija la clase. Antes era `bg-destructive/10 text-destructive`
    // (texto de 14 px): axe midió 3.82:1 en claro (#DC2626 sobre #F1E1E3) y 4.38:1 en oscuro
    // (#F87171 sobre #43303F), por debajo de 4.5:1. Con los tokens de index.css, el texto
    // --destructive-foreground sobre --destructive da:
    //   claro:  #FFFFFF sobre #DC2626 = 4.83:1 en reposo; en hover (mezcla de 10 % de
    //           --foreground, #020617, que oscurece el rojo) = 5.82:1.
    //   oscuro: #0B1220 sobre #F87171 = 6.77:1 en reposo; en hover (mezcla de 10 % de
    //           --foreground, #E2E8F0, que lo aclara) = 7.36:1.
    // El hover no usa `bg-destructive/90`: aclara el rojo en el tema claro y baja a 4.32:1.
    // El reposo también lo cubre tokens.node.test.ts (destructive-foreground sobre destructive).
    render(<Button variant="destructive">Rechazar propuesta</Button>)
    const boton = screen.getByRole("button", { name: "Rechazar propuesta" })
    expect(boton).toHaveClass("bg-destructive", "text-destructive-foreground")
    expect(boton).toHaveClass(
      "hover:bg-[color-mix(in_oklch,var(--destructive),var(--foreground)_10%)]"
    )
    // Nada del tinte translúcido de antes, en ningún tema ni estado.
    expect(boton.className).not.toMatch(/(^|\s|:)bg-destructive\/\d+/)
    expect(boton.className).not.toMatch(/(^|\s)text-destructive(\s|$)/)
  })
})
