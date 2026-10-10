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
      "Sistema",
    ])
    expect(titulos(["admin"])).toContain("Configuración")
  })

  it("descarta las secciones que quedan vacías", () => {
    expect(navegacionPara(["aprobador"]).map((s) => s.titulo)).not.toContain(
      "Sistema"
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
    ["/sistema/usuarios", [{ titulo: "Sistema" }, { titulo: "Usuarios" }]],
    [
      "/sistema/usuarios/abc",
      [
        { titulo: "Sistema" },
        { titulo: "Usuarios", ruta: "/sistema/usuarios" },
        { titulo: "Detalle" },
      ],
    ],
    ["/sistema/actividad", [{ titulo: "Sistema" }, { titulo: "Actividad" }]],
    ["/sistema/catalogo", [{ titulo: "Sistema" }, { titulo: "Catálogo" }]],
    ["/importacion", [{ titulo: "Sistema" }, { titulo: "Importación" }]],
    ["/sistema", [{ titulo: "Página no encontrada" }]],
    ["/no-existe", [{ titulo: "Página no encontrada" }]],
  ])("%s", (pathname, esperado) => {
    expect(migasDe(pathname)).toEqual(esperado)
  })
})

describe("descripciones del menú", () => {
  it("cada elemento dice para qué sirve", () => {
    const descripciones = Object.fromEntries(
      navegacionPara(["admin"]).flatMap((s) =>
        s.elementos.map((e) => [e.titulo, e.descripcion])
      )
    )
    expect(descripciones).toEqual({
      Tablero: "Resumen del gasto y lo urgente",
      Proveedores: "Quién le vende y cómo rinde",
      Ranking: "Los mejores proveedores por categoría",
      Precios: "Cuánto debería pagar",
      Alertas: "Qué atender hoy",
      Usuarios: "Quién entra y con qué rol",
      Actividad: "Quién hizo qué y cuándo",
      Catálogo: "Servicios de TI que se compran",
      Correos: "Invitaciones y restablecimientos enviados",
      Importación: "Cargar datos del ERP",
      Configuración: "Ajustes de puntuación y precios",
    })
  })
})
