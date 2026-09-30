import { describe, expect, it } from "vitest"
import { rolesDeToken } from "@/auth"

function tokenCon(carga: object): string {
  const base64url = btoa(JSON.stringify(carga))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "")
  return `cabecera.${base64url}.firma`
}

describe("rolesDeToken", () => {
  it("devuelve solo los roles de la plataforma", () => {
    const token = tokenCon({ realm_access: { roles: ["comprador", "offline_access", "admin"] } })
    expect(rolesDeToken(token)).toEqual(["comprador", "admin"])
  })

  it("tolera tokens ausentes o mal formados", () => {
    expect(rolesDeToken(undefined)).toEqual([])
    expect(rolesDeToken("no-es-un-jwt")).toEqual([])
    expect(rolesDeToken("a.%%%.c")).toEqual([])
  })

  it("tolera tokens sin realm_access", () => {
    expect(rolesDeToken(tokenCon({ sub: "u-1" }))).toEqual([])
  })
})
