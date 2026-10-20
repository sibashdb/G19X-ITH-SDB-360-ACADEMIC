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
    throw new Error(
      `El token --${token} debe ser un color #RRGGBB (es ${valor})`
    )
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

function par(
  frente: string,
  fondo: string,
  minimo: number
): [string, string, number] {
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
  // Tintes del estilo refinado: el icono es gráfico (3:1); las iniciales son texto (4.5:1).
  par("accent", "info-suave", TEXTO),
  par("success", "exito-suave", GRAFICO),
  par("warning", "advertencia-suave", GRAFICO),
  par("destructive", "riesgo-suave", GRAFICO),
  par("ring", "background", GRAFICO),
  par("sidebar-ring", "sidebar", GRAFICO),
]

describe("contraste de los tokens", () => {
  it("calcula el contraste WCAG", () => {
    expect(contraste("#000000", "#FFFFFF")).toBeCloseTo(21, 1)
    expect(contraste("#777777", "#FFFFFF")).toBeCloseTo(4.48, 2)
  })

  for (const [nombre, tema] of Object.entries(TEMAS)) {
    it.each(PARES)(
      `tema ${nombre}: --%s sobre --%s cumple %d:1`,
      (frente, fondo, minimo) => {
        expect(
          contraste(color(tema, frente), color(tema, fondo))
        ).toBeGreaterThanOrEqual(minimo)
      }
    )
  }
})

// El hover del botón destructivo mezcla su fondo con otro token (`color-mix(in oklch, …)`), así que
// el fondo no es un token y no cabe en PARES: se calcula la mezcla y se lee de button.tsx, para que
// un cambio de la clase (p. ej. `hover:bg-destructive/90`, que da 4.32:1 en claro) lo detecte.
const boton = readFileSync(
  resolve(import.meta.dirname, "components/ui/button.tsx"),
  "utf8"
)
const DESTRUCTIVE = boton.match(/destructive:\s*"([^"]+)"/)?.[1] ?? ""
const HOVER = DESTRUCTIVE.match(
  /hover:bg-\[color-mix\(in_oklch,var\(--([\w-]+)\),var\(--([\w-]+)\)_(\d+)%\)\]/
)

type Lab = [number, number, number]

/** sRGB (#RRGGBB) a OKLab (Ottosson), con los canales en 0-1 lineales. */
function aOklab(hex: string): Lab {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ]
}

function deOklab([L, a, b]: Lab): string {
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3
  const lineal = [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ]
  return (
    "#" +
    lineal
      .map((c) => {
        const g = c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055
        return Math.round(Math.min(1, Math.max(0, g)) * 255)
          .toString(16)
          .padStart(2, "0")
      })
      .join("")
  )
}

/** `color-mix(in oklch, a, b p%)`: interpola luminosidad, croma y matiz (por el arco corto). */
function mezclaOklch(a: string, b: string, porcentaje: number): string {
  const lch = ([L, x, y]: Lab) => [L, Math.hypot(x, y), Math.atan2(y, x)]
  const [l1, c1, h1] = lch(aOklab(a))
  const [l2, c2, h2] = lch(aOklab(b))
  let dh = h2 - h1
  if (dh > Math.PI) dh -= 2 * Math.PI
  if (dh < -Math.PI) dh += 2 * Math.PI
  const t = porcentaje / 100
  const [L, C, h] = [l1 + (l2 - l1) * t, c1 + (c2 - c1) * t, h1 + dh * t]
  return deOklab([L, C * Math.cos(h), C * Math.sin(h)])
}

describe("contraste del botón destructivo en hover", () => {
  it("mezcla en OKLCH, como CSS: 0 % es el color base y 100 %, el otro", () => {
    expect(mezclaOklch("#DC2626", "#020617", 0)).toBe("#dc2626")
    expect(mezclaOklch("#DC2626", "#020617", 100)).toBe("#020617")
    expect(mezclaOklch("#000000", "#FFFFFF", 50)).toBe("#636363")
  })

  it("la variante es un relleno sólido que mezcla su fondo en hover", () => {
    expect(DESTRUCTIVE).toContain("bg-destructive ")
    expect(DESTRUCTIVE).toContain("text-destructive-foreground")
    expect(HOVER).not.toBeNull()
  })

  for (const [nombre, tema] of Object.entries(TEMAS)) {
    it(`tema ${nombre}: --destructive-foreground sobre el hover cumple ${TEXTO}:1`, () => {
      const [, base, otro, porcentaje] = HOVER!
      const fondo = mezclaOklch(
        color(tema, base),
        color(tema, otro),
        Number(porcentaje)
      )
      expect(
        contraste(color(tema, "destructive-foreground"), fondo)
      ).toBeGreaterThanOrEqual(TEXTO)
    })
  }
})
