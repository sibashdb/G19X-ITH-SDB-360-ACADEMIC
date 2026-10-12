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
    [
      "configuracion.actualizada",
      {
        cambios: [
          { campo: "peso_sla", anterior: 30, nuevo: 40 },
          { campo: "peso_entregas", anterior: 15, nuevo: 5 },
          { campo: "inflacion_anual", anterior: "4.50", nuevo: "5.20" },
        ],
      },
      "Cambió la configuración de la puntuación: pesos, inflación anual",
    ],
    [
      "modelo.entrenado",
      { version: 4, mape: 0.112, promovido: true },
      "Reentrenó el modelo de precios: versión 4, MAPE 11.2 %, promovido",
    ],
    [
      "modelo.entrenado",
      { version: 5, mape: 0.0934, promovido: false },
      "Reentrenó el modelo de precios: versión 5, MAPE 9.3 %, no se promovió (no mejoró la línea base)",
    ],
    [
      "modelo.entrenado",
      { version: 6, mape: 0.1125, promovido: true },
      "Reentrenó el modelo de precios: versión 6, MAPE 11.3 %, promovido",
    ],
  ])("%s", (tipo, detalle, esperado) => {
    expect(describirActividad({ ...base, tipo, detalle })).toBe(esperado)
  })

  it("un tipo desconocido se muestra tal cual", () => {
    expect(describirActividad({ ...base, tipo: "otro.tipo" })).toBe("otro.tipo")
  })
})
