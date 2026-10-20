import { describe, expect, it } from "vitest"
import {
  ARTICULOS,
  articuloPorSlug,
  articulosVisibles,
  buscarArticulos,
  esSoloAdmin,
  PREGUNTAS,
  TEMAS,
} from "@/ayuda"
import { GLOSARIO } from "@/glosario"

describe("contenido de la ayuda", () => {
  it("cada artículo tiene un slug único, un tema conocido y enlaces internos", () => {
    const slugs = ARTICULOS.map((a) => a.slug)
    expect(new Set(slugs).size).toBe(slugs.length)
    const temas = new Set(TEMAS.map((t) => t.clave))
    for (const articulo of ARTICULOS) {
      expect(temas.has(articulo.tema)).toBe(true)
      expect(articulo.slug).toMatch(/^[a-z0-9-]+$/)
      expect(articulo.secciones.length).toBeGreaterThan(0)
      for (const enlace of articulo.enlaces ?? [])
        expect(enlace.ruta).toMatch(/^\//)
    }
    expect(PREGUNTAS.every((p) => p.pregunta && p.respuesta)).toBe(true)
  })

  it("los artículos de administración solo los ve administración", () => {
    const deAdmin = ARTICULOS.filter(esSoloAdmin)
    expect(deAdmin.length).toBeGreaterThan(0)
    expect(articulosVisibles(false)).not.toContain(deAdmin[0])
    expect(articulosVisibles(true)).toContain(deAdmin[0])
  })

  it("busca sin acentos ni mayúsculas y exige todas las palabras", () => {
    expect(
      buscarArticulos("CONTRASENA temporal", true).map((a) => a.slug)
    ).toContain("contrasenas-y-correos")
    expect(
      buscarArticulos("contrasena temporal", false).map((a) => a.slug)
    ).not.toContain("contrasenas-y-correos")
    expect(buscarArticulos("precio justo", false).map((a) => a.slug)).toEqual([
      "precio-justo",
    ])
    expect(buscarArticulos("zzz inexistente", true)).toEqual([])
  })

  it("ignora los signos de puntuación: se puede buscar con una pregunta", () => {
    expect(
      buscarArticulos("¿cómo importar?", true).map((a) => a.slug)
    ).toContain("importar-datos")
    expect(
      buscarArticulos("«Importar», datos.", true).map((a) => a.slug)
    ).toContain("importar-datos")
  })

  it("la ayuda de Correos y de Actividad menciona los avisos de negociación", () => {
    const texto = (slug: string) =>
      JSON.stringify(articuloPorSlug(slug)?.secciones)
    expect(texto("contrasenas-y-correos")).toContain(
      "invitaciones a negociar y los resultados"
    )
    expect(texto("revisar-actividad")).toContain("adjudicación")
  })

  it("encuentra un artículo por su slug", () => {
    expect(articuloPorSlug("importar-datos")?.titulo).toBe(
      "Importar los datos del ERP"
    )
    expect(articuloPorSlug("no-existe")).toBeUndefined()
    expect(articuloPorSlug(undefined)).toBeUndefined()
  })

  it("solo administración encuentra cómo configurar la puntuación y el modelo", () => {
    expect(
      buscarArticulos("reentrenar modelo", true).map((a) => a.slug)
    ).toContain("configurar-puntuacion-y-modelo")
    expect(buscarArticulos("reentrenar modelo", false)).toEqual([])
  })

  it("explica cómo negocia el agente y cómo supervisarlo", () => {
    expect(
      buscarArticulos("cuándo acepta el agente", false).map((a) => a.slug)
    ).toContain("como-negocia-el-agente")
    expect(
      buscarArticulos("tomar el control", false).map((a) => a.slug)
    ).toContain("negociar-con-proveedores")
    expect(articuloPorSlug("como-negocia-el-agente")?.tema).toBe("negociacion")
  })

  it("dice quién puede crear y atender las negociaciones, antes de los pasos", () => {
    const primera = articuloPorSlug("negociar-con-proveedores")?.secciones[0]
    expect(primera?.parrafos?.[0]).toBe(
      "Solo el rol de compras crea, publica, reenvía, cancela y atiende a mano las negociaciones; quien aprueba o administra las ve sin poder cambiarlas."
    )
  })

  it("describe cuánto cede el agente según el estilo, sin prometer lo que no hace", () => {
    const seccion = articuloPorSlug("como-negocia-el-agente")?.secciones.find(
      (s) => s.titulo === "Cuánto cede en cada ronda"
    )
    expect(seccion?.parrafos).toEqual([
      "El agente empieza pidiendo casi su ideal y, ronda tras ronda, se conforma con un poco menos, hasta llegar a su límite en la última. El estilo decide el ritmo: firme cede muy poco hasta las últimas rondas, balanceado cede poco al principio y más hacia el final, y flexible cede de forma pareja desde la primera ronda.",
      "Nunca pide algo peor para usted que lo que el proveedor ya ofreció, no revela su límite antes de la última ronda y casi nunca vuelve a pedir más de lo que pidió en la ronda anterior.",
    ])
  })

  it("el artículo Adjudicar y aprobar existe y se encuentra al buscar", () => {
    const articulo = articuloPorSlug("adjudicar-y-aprobar")
    expect(articulo?.titulo).toBe("Adjudicar y aprobar")
    expect(articulo?.tema).toBe("negociacion")
    // Lo ve quien no administra: es de quien compra y de quien aprueba.
    expect(esSoloAdmin(articulo!)).toBe(false)
    for (const consulta of ["aprobador", "desierta", "umbral de aprobación"])
      expect(
        buscarArticulos(consulta, false).map((a) => a.slug),
        consulta
      ).toContain("adjudicar-y-aprobar")
  })

  it("Adjudicar y aprobar explica la regla, la separación de funciones y el aviso a los proveedores", () => {
    const texto = JSON.stringify(
      articuloPorSlug("adjudicar-y-aprobar")?.secciones
    )
    for (const frase of [
      "Ajustar pesos",
      "500,000 MXN",
      "administración lo cambie en Configuración",
      "fuera de sus límites",
      "Quien propone no aprueba",
      "Revisar la propuesta nueva",
      "Declarar desierta",
      "se declara desierta sola",
      "ni se les muestra ningún monto",
    ])
      expect(texto, frase).toContain(frase)
  })

  it("los artículos de negociación llevan al de Adjudicar y aprobar", () => {
    for (const slug of ["negociar-con-proveedores", "como-negocia-el-agente"])
      expect(articuloPorSlug(slug)?.enlaces?.map((e) => e.ruta)).toContain(
        "/ayuda/adjudicar-y-aprobar"
      )
  })

  it("Cómo usar PluriOne ya no promete la aprobación para después", () => {
    const texto = JSON.stringify(articuloPorSlug("como-usar-pluri-one"))
    expect(texto).not.toContain("próxima versión")
    expect(texto).toContain("un aprobador")
  })

  it("los términos nuevos de la adjudicación están en el glosario", () => {
    expect(GLOSARIO.adjudicacion.termino).toBe("Adjudicación")
    expect(GLOSARIO.adjudicacion.definicion).toContain("contrato")
    expect(GLOSARIO.umbral_aprobacion.termino).toBe("Umbral de aprobación")
    expect(GLOSARIO.umbral_aprobacion.definicion).toContain("500,000")
    expect(GLOSARIO.desierta.termino).toBe("Desierta")
    expect(GLOSARIO.desierta.definicion).toContain("sin adjudicar")
    expect(GLOSARIO.fuera_de_limites.termino).toBe("Fuera de límites")
    expect(GLOSARIO.fuera_de_limites.definicion).toContain("aprobador")
  })

  it("para reenviar una invitación manda al botón «Reenviar» de la tabla de sesiones", () => {
    const seccion = articuloPorSlug("negociar-con-proveedores")?.secciones.find(
      (s) => s.titulo === "Publicar y compartir los enlaces"
    )
    const texto = seccion?.parrafos?.join(" ")
    expect(texto).toContain("use «Reenviar» en la tabla de sesiones")
    expect(texto).not.toContain("Reenviar invitación")
  })
})
