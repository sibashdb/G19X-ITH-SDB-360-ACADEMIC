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
      "Negociaciones",
      "Centro de ayuda",
    ])
    expect(titulos([])).toEqual([
      "Tablero",
      "Proveedores",
      "Ranking",
      "Precios",
      "Alertas",
      "Negociaciones",
      "Centro de ayuda",
    ])
  })

  it("muestra todo al admin, agrupado por sección", () => {
    const secciones = navegacionPara(["admin"])
    expect(secciones.map((s) => s.titulo)).toEqual([
      "Resumen",
      "Proveedores",
      "Inteligencia",
      "Negociación",
      "Sistema",
      "Soporte",
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

  it("una ruta exacta no se activa en sus subrutas", () => {
    expect(estaActiva("/sistema", "/sistema", true)).toBe(true)
    expect(estaActiva("/sistema", "/sistema/usuarios", true)).toBe(false)
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
    [
      "/negociaciones",
      [{ titulo: "Negociación" }, { titulo: "Negociaciones" }],
    ],
    [
      "/negociaciones/nueva",
      [
        { titulo: "Negociación" },
        { titulo: "Negociaciones", ruta: "/negociaciones" },
        { titulo: "Nueva" },
      ],
    ],
    [
      "/negociaciones/abc/sesiones/def",
      [
        { titulo: "Negociación" },
        { titulo: "Negociaciones", ruta: "/negociaciones" },
        { titulo: "Detalle" },
      ],
    ],
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
    ["/sistema", [{ titulo: "Sistema" }, { titulo: "Panel" }]],
    [
      "/sistema/estado",
      [{ titulo: "Sistema" }, { titulo: "Estado del sistema" }],
    ],
    ["/ayuda", [{ titulo: "Soporte" }, { titulo: "Centro de ayuda" }]],
    [
      "/ayuda/importar-datos",
      [
        { titulo: "Soporte" },
        { titulo: "Centro de ayuda", ruta: "/ayuda" },
        { titulo: "Detalle" },
      ],
    ],
    ["/sistema/no-existe", [{ titulo: "Página no encontrada" }]],
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
      Negociaciones: "Negociar con proveedores dentro de sus límites",
      Panel: "Lo importante de un vistazo",
      Usuarios: "Quién entra y con qué rol",
      Actividad: "Quién hizo qué y cuándo",
      Catálogo: "Servicios de TI que se compran",
      "Estado del sistema": "Si cada servicio responde",
      Correos:
        "Invitaciones, restablecimientos, invitaciones a negociar y sus resultados",
      Importación: "Cargar datos del ERP",
      Configuración: "Ajustes de puntuación y precios",
      "Centro de ayuda": "Guías y preguntas frecuentes",
    })
  })
})
