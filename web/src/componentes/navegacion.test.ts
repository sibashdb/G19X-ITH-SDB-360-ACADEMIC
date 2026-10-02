import { describe, expect, it } from "vitest"
import { estaActiva, migasDe, navegacionPara } from "@/componentes/navegacion"

const titulos = (roles: Parameters<typeof navegacionPara>[0]) =>
  navegacionPara(roles).flatMap((s) => s.elementos.map((e) => e.titulo))

describe("navegacionPara", () => {
  it("oculta Importación y Configuración a quien no es admin", () => {
    expect(titulos(["comprador"])).toEqual([
      "Tablero",
      "Proveedores",
      "Ranking",
      "Precios",
      "Alertas",
    ])
    expect(titulos([])).toEqual([
      "Tablero",
      "Proveedores",
      "Ranking",
      "Precios",
      "Alertas",
    ])
  })

  it("muestra todo al admin, agrupado por sección", () => {
    const secciones = navegacionPara(["admin"])
    expect(secciones.map((s) => s.titulo)).toEqual([
      "Resumen",
      "Proveedores",
      "Inteligencia",
      "Datos",
    ])
    expect(titulos(["admin"])).toContain("Configuración")
  })

  it("descarta las secciones que quedan vacías", () => {
    expect(navegacionPara(["aprobador"]).map((s) => s.titulo)).not.toContain(
      "Datos"
    )
  })
})

describe("estaActiva", () => {
  it.each([
    ["/", "/", true],
    ["/", "/proveedores", false],
    ["/proveedores", "/proveedores", true],
    ["/proveedores", "/proveedores/abc", true],
    ["/proveedores", "/proveedoresx", false],
  ])("ruta %s en %s → %s", (ruta, pathname, esperado) => {
    expect(estaActiva(ruta, pathname)).toBe(esperado)
  })
})

describe("migasDe", () => {
  it.each([
    ["/", [{ titulo: "Resumen" }, { titulo: "Tablero" }]],
    ["/proveedores", [{ titulo: "Proveedores" }]],
    ["/proveedores/", [{ titulo: "Proveedores" }]],
    [
      "/proveedores/abc",
      [{ titulo: "Proveedores", ruta: "/proveedores" }, { titulo: "Detalle" }],
    ],
    ["/ranking", [{ titulo: "Proveedores" }, { titulo: "Ranking" }]],
    ["/precios", [{ titulo: "Inteligencia" }, { titulo: "Precios" }]],
    ["/no-existe", [{ titulo: "Página no encontrada" }]],
  ])("%s", (pathname, esperado) => {
    expect(migasDe(pathname)).toEqual(esperado)
  })
})
