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
      "configuracion.actualizada",
      {
        cambios: [
          { campo: "adjudicacion_costo", anterior: 40, nuevo: 50 },
          { campo: "adjudicacion_desempeno", anterior: 30, nuevo: 20 },
          { campo: "adjudicacion_riesgo", anterior: 15, nuevo: 15 },
          { campo: "adjudicacion_sla", anterior: 15, nuevo: 15 },
          {
            campo: "umbral_aprobacion",
            anterior: "500000.00",
            nuevo: "750000.00",
          },
        ],
      },
      "Cambió la configuración de la puntuación: peso del costo en la adjudicación, peso del desempeño en la adjudicación, peso del riesgo en la adjudicación, peso del SLA en la adjudicación, umbral de aprobación",
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

  it.each([
    [
      "negociacion.publicada",
      { proveedores: 3 },
      "Publicó la negociación NEG-2026-0001 «CRM 2027» con 3 proveedores",
    ],
    [
      "negociacion.publicada",
      { proveedores: 1 },
      "Publicó la negociación NEG-2026-0001 «CRM 2027» con 1 proveedor",
    ],
    [
      "negociacion.cancelada",
      { motivo: "Se pospuso" },
      "Canceló la negociación NEG-2026-0001 «CRM 2027»: Se pospuso",
    ],
    [
      "negociacion.invitacion_enviada",
      { proveedor: "Nube Norte", estado: "enviado", reenvio: false },
      "Envió a Nube Norte la invitación a negociar NEG-2026-0001 «CRM 2027»",
    ],
    [
      "negociacion.invitacion_enviada",
      { proveedor: "Nube Norte", estado: "enviado", reenvio: true },
      "Reenvió a Nube Norte la invitación a negociar NEG-2026-0001 «CRM 2027»",
    ],
    [
      "negociacion.invitacion_enviada",
      { proveedor: "Nube Norte", estado: "fallido", reenvio: false },
      "No se pudo enviar a Nube Norte la invitación a negociar NEG-2026-0001 «CRM 2027»",
    ],
    [
      "negociacion.adjudicada",
      { proveedor: "Nube Norte", aprobacion: "directa" },
      "Adjudicó la negociación NEG-2026-0001 «CRM 2027» a Nube Norte (directa)",
    ],
    [
      "negociacion.adjudicada",
      { proveedor: "Nube Norte", aprobacion: "aprobada" },
      "Adjudicó la negociación NEG-2026-0001 «CRM 2027» a Nube Norte (aprobada)",
    ],
    [
      "negociacion.desierta",
      { motivo: "Cambió el presupuesto" },
      "Declaró desierta la negociación NEG-2026-0001 «CRM 2027»: Cambió el presupuesto",
    ],
    [
      "negociacion.desierta",
      {},
      "Declaró desierta la negociación NEG-2026-0001 «CRM 2027»",
    ],
    [
      "negociacion.desierta",
      { motivo: "sin_acuerdos" },
      "La negociación NEG-2026-0001 «CRM 2027» quedó desierta: ningún proveedor llegó a un acuerdo",
    ],
    [
      "negociacion.resultado_enviado",
      { proveedor: "Nube Norte", estado: "enviado", resultado: "adjudicada" },
      "Envió a Nube Norte el resultado de la negociación NEG-2026-0001 «CRM 2027»",
    ],
    [
      "negociacion.resultado_enviado",
      { proveedor: "Nube Norte", estado: "fallido", resultado: "desierta" },
      "No se pudo enviar a Nube Norte el resultado de la negociación NEG-2026-0001 «CRM 2027»",
    ],
  ])("negociación: %s", (tipo, detalle, esperado) => {
    const objeto_nombre = "NEG-2026-0001 «CRM 2027»"
    expect(describirActividad({ ...base, tipo, detalle, objeto_nombre })).toBe(
      esperado
    )
  })

  it("un tipo desconocido se muestra tal cual", () => {
    expect(describirActividad({ ...base, tipo: "otro.tipo" })).toBe("otro.tipo")
  })
})
