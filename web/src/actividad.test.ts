import { describe, expect, it } from "vitest"
import { describirActividad, TIPOS_ACTIVIDAD } from "@/actividad"
import type { RegistroActividad } from "@/tipos"

const base: RegistroActividad = {
  id: "1",
  fecha: "2026-10-08T00:00:00Z",
  actor_id: "admin-1",
  actor_nombre: "admin1",
  tipo: "",
  objeto_tipo: "usuario",
  objeto_id: "u-ana",
  objeto_nombre: "Ana López",
  detalle: {},
  resultado: "exito",
  ip: null,
}

describe("describirActividad", () => {
  it("todo tipo tiene texto propio", () => {
    for (const tipo of TIPOS_ACTIVIDAD) {
      expect(describirActividad({ ...base, tipo })).not.toBe(tipo)
    }
  })

  it.each([
    ["sesion.iniciada", {}, "Inició sesión"],
    [
      "sesion.fallida",
      { error: "invalid_user_credentials" },
      "Intento fallido de inicio de sesión: contraseña incorrecta",
    ],
    [
      "sesion.fallida",
      { error: "user_temporarily_disabled" },
      "Intento fallido de inicio de sesión: cuenta bloqueada temporalmente",
    ],
    ["usuario.creado", {}, "Dio de alta a Ana López"],
    [
      "usuario.creado",
      { pendiente: "roles" },
      "Dio de alta a Ana López; faltó asignar los roles",
    ],
    [
      "usuario.creado",
      { pendiente: "contrasena" },
      "Dio de alta a Ana López; faltó la contraseña",
    ],
    [
      "usuario.roles_cambiados",
      { antes: ["comprador"], despues: ["comprador", "aprobador"] },
      "Cambió los roles de Ana López: Compras → Compras, Aprobación",
    ],
    [
      "usuario.correo_contrasena",
      {},
      "Envió a Ana López un correo para definir su contraseña",
    ],
  ])("%s", (tipo, detalle, esperado) => {
    expect(describirActividad({ ...base, tipo, detalle })).toBe(esperado)
  })

  it("un tipo desconocido se muestra tal cual", () => {
    expect(describirActividad({ ...base, tipo: "otro.tipo" })).toBe("otro.tipo")
  })
})
