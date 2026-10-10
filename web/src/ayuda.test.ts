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

  it("encuentra un artículo por su slug", () => {
    expect(articuloPorSlug("importar-datos")?.titulo).toBe(
      "Importar los datos del ERP"
    )
    expect(articuloPorSlug("no-existe")).toBeUndefined()
    expect(articuloPorSlug(undefined)).toBeUndefined()
  })
})
