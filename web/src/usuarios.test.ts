import { describe, expect, it } from "vitest"
import { nombreCompleto, sugerirUsuario } from "@/usuarios"

describe("sugerirUsuario", () => {
  it.each([
    ["Ana.López@Empresa.mx", "ana.lopez"],
    ["juan_perez+compras@x.mx", "juanperezcompras"],
    ["", ""],
    ["a".repeat(40) + "@x.mx", "a".repeat(30)],
  ])("%s → %s", (correo, esperado) => {
    expect(sugerirUsuario(correo)).toBe(esperado)
  })
})

describe("nombreCompleto", () => {
  it("usa el usuario si no hay nombre", () => {
    expect(nombreCompleto({ nombre: "", apellidos: "", usuario: "ana" })).toBe(
      "ana"
    )
    expect(
      nombreCompleto({ nombre: "Ana", apellidos: "López", usuario: "ana" })
    ).toBe("Ana López")
  })
})
