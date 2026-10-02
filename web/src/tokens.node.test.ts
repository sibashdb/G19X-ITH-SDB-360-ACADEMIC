import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const css = readFileSync(resolve(import.meta.dirname, "index.css"), "utf8")

/** Variables declaradas en el bloque `selector { … }` de index.css. */
function variables(selector: string): Record<string, string> {
  const inicio = css.indexOf(`${selector} {`)
  if (inicio < 0) throw new Error(`index.css no tiene el bloque ${selector}`)
  const bloque = css.slice(inicio, css.indexOf("}", inicio))
  return Object.fromEntries(
    [...bloque.matchAll(/--([\w-]+):\s*([^;]+);/g)].map(([, nombre, valor]) => [
      nombre,
      valor.trim(),
    ])
  )
}

const CLARO = variables(":root")
const TEMAS = { claro: CLARO, oscuro: { ...CLARO, ...variables(".dark") } }

/** Resuelve `var(--x)` y exige un color #RRGGBB. */
function color(tema: Record<string, string>, token: string): string {
  let valor = tema[token]
  for (let saltos = 0; valor?.startsWith("var(--") && saltos < 5; saltos++) {
    valor = tema[valor.slice(6, -1)]
  }
  if (!/^#[0-9a-f]{6}$/i.test(valor ?? "")) {
    throw new Error(`El token --${token} debe ser un color #RRGGBB (es ${valor})`)
  }
  return valor
}

function luminancia(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contraste(a: string, b: string): number {
  const [claro, oscuro] = [luminancia(a), luminancia(b)].sort((x, y) => y - x)
  return (claro + 0.05) / (oscuro + 0.05)
}

const TEXTO = 4.5
const GRAFICO = 3

function par(frente: string, fondo: string, minimo: number): [string, string, number] {
  return [frente, fondo, minimo]
}

/** Pares que la interfaz usa: [primer plano, fondo, contraste mínimo]. */
const PARES = [
  ...["background", "card", "muted"].flatMap((fondo) => [
    par("foreground", fondo, TEXTO),
    par("muted-foreground", fondo, TEXTO),
    par("accent", fondo, TEXTO),
  ]),
  ...["success", "warning", "destructive"].flatMap((estado) => [
    par(estado, "background", TEXTO),
    par(estado, "card", TEXTO),
  ]),
  par("card-foreground", "card", TEXTO),
  par("popover-foreground", "popover", TEXTO),
  par("primary-foreground", "primary", TEXTO),
  par("secondary-foreground", "secondary", TEXTO),
  par("accent-foreground", "accent", TEXTO),
  par("destructive-foreground", "destructive", TEXTO),
  par("sidebar-foreground", "sidebar", TEXTO),
  par("sidebar-accent-foreground", "sidebar-accent", TEXTO),
  par("sidebar-primary-foreground", "sidebar-primary", TEXTO),
  ...[1, 2, 3, 4, 5].map((n) => par(`chart-${n}`, "card", GRAFICO)),
  // Los campos tienen fondo transparente: su borde es el único contorno (WCAG 1.4.11).
  par("input", "card", GRAFICO),
  par("input", "background", GRAFICO),
  par("ring", "background", GRAFICO),
  par("sidebar-ring", "sidebar", GRAFICO),
]

describe("contraste de los tokens", () => {
  it("calcula el contraste WCAG", () => {
    expect(contraste("#000000", "#FFFFFF")).toBeCloseTo(21, 1)
    expect(contraste("#777777", "#FFFFFF")).toBeCloseTo(4.48, 2)
  })

  for (const [nombre, tema] of Object.entries(TEMAS)) {
    it.each(PARES)(`tema ${nombre}: --%s sobre --%s cumple %d:1`, (frente, fondo, minimo) => {
      expect(contraste(color(tema, frente), color(tema, fondo))).toBeGreaterThanOrEqual(minimo)
    })
  }
})
