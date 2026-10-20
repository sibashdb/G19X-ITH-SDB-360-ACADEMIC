import { NOMBRES_ROL, type Rol } from "@/auth"
import type { RegistroActividad } from "@/tipos"

export const TIPOS_ACTIVIDAD = [
  "sesion.iniciada",
  "sesion.fallida",
  "sesion.cerrada",
  "usuario.creado",
  "usuario.actualizado",
  "usuario.roles_cambiados",
  "usuario.desactivado",
  "usuario.activado",
  "usuario.correo_contrasena",
  "usuario.contrasena_temporal",
  "usuario.sesiones_cerradas",
  "importacion.completada",
  "importacion.rechazada",
  "servicio.creado",
  "servicio.actualizado",
  "servicio.desactivado",
  "servicio.activado",
  "configuracion.actualizada",
  "modelo.entrenado",
  "negociacion.publicada",
  "negociacion.cancelada",
  "negociacion.invitacion_enviada",
  "negociacion.adjudicada",
  "negociacion.desierta",
  "negociacion.resultado_enviado",
] as const
type TipoActividad = (typeof TIPOS_ACTIVIDAD)[number]

const ERRORES_SESION: Record<string, string> = {
  invalid_user_credentials: "contraseña incorrecta",
  user_not_found: "usuario inexistente",
  user_disabled: "cuenta desactivada",
  user_temporarily_disabled: "cuenta bloqueada temporalmente",
}

function roles(valor: unknown): string {
  return Array.isArray(valor)
    ? valor.map((r) => NOMBRES_ROL[r as Rol] ?? String(r)).join(", ")
    : ""
}

const NOMBRES_AJUSTE: Record<string, string> = {
  umbral_riesgo: "umbral de riesgo",
  inflacion_anual: "inflación anual",
  adjudicacion_costo: "peso del costo en la adjudicación",
  adjudicacion_desempeno: "peso del desempeño en la adjudicación",
  adjudicacion_riesgo: "peso del riesgo en la adjudicación",
  adjudicacion_sla: "peso del SLA en la adjudicación",
  umbral_aprobacion: "umbral de aprobación",
}
const CONFIGURACION = "Cambió la configuración"

/** La sección de Configuración a la que pertenece el campo. */
function area(campo: string): string {
  return campo.startsWith("adjudicacion_") || campo === "umbral_aprobacion"
    ? "de la adjudicación"
    : "de la puntuación"
}

/** Los campos cambiados en lenguaje llano; los cinco pesos se nombran una vez. */
function ajustes(a: RegistroActividad): string {
  const cambios = Array.isArray(a.detalle.cambios) ? a.detalle.cambios : []
  const nombres: string[] = []
  const areas: string[] = []
  for (const cambio of cambios) {
    const campo =
      cambio && typeof cambio === "object"
        ? String((cambio as { campo?: unknown }).campo ?? "")
        : ""
    const nombre = campo.startsWith("peso_")
      ? "pesos"
      : (NOMBRES_AJUSTE[campo] ?? campo)
    if (!nombres.includes(nombre)) nombres.push(nombre)
    if (!areas.includes(area(campo))) areas.push(area(campo))
  }
  return nombres.length
    ? `${CONFIGURACION} ${areas.join(" y ")}: ${nombres.join(", ")}`
    : CONFIGURACION
}

function entrenamiento(a: RegistroActividad): string {
  const mape = a.detalle.mape
  const porcentaje = typeof mape === "number" ? (mape * 100).toFixed(1) : "?"
  const resultado = a.detalle.promovido
    ? "promovido"
    : "no se promovió (no mejoró la línea base)"
  return `Reentrenó el modelo de precios: versión ${String(a.detalle.version ?? "?")}, MAPE ${porcentaje} %, ${resultado}`
}

function proveedores(valor: unknown): string {
  const cuantos = typeof valor === "number" ? valor : 0
  return cuantos === 1 ? "1 proveedor" : `${cuantos} proveedores`
}

function invitacion(a: RegistroActividad): string {
  const proveedor = String(a.detalle.proveedor ?? "")
  if (a.detalle.estado === "fallido")
    return `No se pudo enviar a ${proveedor} la invitación a negociar ${a.objeto_nombre}`
  const accion = a.detalle.reenvio ? "Reenvió" : "Envió"
  return `${accion} a ${proveedor} la invitación a negociar ${a.objeto_nombre}`
}

const APROBACIONES: Record<string, string> = {
  directa: " (directa)",
  aprobada: " (aprobada)",
}

function adjudicada(a: RegistroActividad): string {
  const aprobacion = APROBACIONES[String(a.detalle.aprobacion)] ?? ""
  return `Adjudicó la negociación ${a.objeto_nombre} a ${String(a.detalle.proveedor ?? "")}${aprobacion}`
}

function desierta(a: RegistroActividad): string {
  const motivo = a.detalle.motivo
  // La automática la publica el sistema (sin actor_id); un comprador puede escribir lo mismo.
  if (motivo === "sin_acuerdos" && a.actor_id === null)
    return `La negociación ${a.objeto_nombre} quedó desierta: ningún proveedor llegó a un acuerdo`
  const texto = `Declaró desierta la negociación ${a.objeto_nombre}`
  return motivo ? `${texto}: ${String(motivo)}` : texto
}

function resultado(a: RegistroActividad): string {
  const proveedor = String(a.detalle.proveedor ?? "")
  if (a.detalle.estado === "fallido")
    return `No se pudo enviar a ${proveedor} el resultado de la negociación ${a.objeto_nombre}`
  return `Envió a ${proveedor} el resultado de la negociación ${a.objeto_nombre}`
}

const TEXTOS: Record<TipoActividad, (a: RegistroActividad) => string> = {
  "sesion.iniciada": () => "Inició sesión",
  "sesion.fallida": (a) => {
    const motivo = ERRORES_SESION[String(a.detalle.error ?? "")]
    return motivo
      ? `Intento fallido de inicio de sesión: ${motivo}`
      : "Intento fallido de inicio de sesión"
  },
  "sesion.cerrada": () => "Cerró sesión",
  "usuario.creado": (a) => `Dio de alta a ${a.objeto_nombre}`,
  "usuario.actualizado": (a) => `Editó los datos de ${a.objeto_nombre}`,
  "usuario.roles_cambiados": (a) =>
    `Cambió los roles de ${a.objeto_nombre}: ${roles(a.detalle.antes)} → ${roles(a.detalle.despues)}`,
  "usuario.desactivado": (a) => `Desactivó a ${a.objeto_nombre}`,
  "usuario.activado": (a) => `Activó a ${a.objeto_nombre}`,
  "usuario.correo_contrasena": (a) =>
    `Envió a ${a.objeto_nombre} un correo para definir su contraseña`,
  "usuario.contrasena_temporal": (a) =>
    `Asignó una contraseña temporal a ${a.objeto_nombre}`,
  "usuario.sesiones_cerradas": (a) =>
    `Cerró las sesiones de ${a.objeto_nombre}`,
  "importacion.completada": (a) =>
    `Importó ${Number(a.detalle.registros ?? 0).toLocaleString("es-MX")} ${a.objeto_nombre}`,
  "importacion.rechazada": (a) =>
    `Intentó importar ${a.objeto_nombre}; el archivo tenía ${Number(a.detalle.errores ?? 0).toLocaleString("es-MX")} errores`,
  "servicio.creado": (a) => `Dio de alta el servicio ${a.objeto_nombre}`,
  "servicio.actualizado": (a) => `Editó el servicio ${a.objeto_nombre}`,
  "servicio.desactivado": (a) => `Desactivó el servicio ${a.objeto_nombre}`,
  "servicio.activado": (a) => `Activó el servicio ${a.objeto_nombre}`,
  "configuracion.actualizada": ajustes,
  "modelo.entrenado": entrenamiento,
  "negociacion.publicada": (a) =>
    `Publicó la negociación ${a.objeto_nombre} con ${proveedores(a.detalle.proveedores)}`,
  "negociacion.cancelada": (a) =>
    `Canceló la negociación ${a.objeto_nombre}: ${String(a.detalle.motivo ?? "")}`,
  "negociacion.invitacion_enviada": invitacion,
  "negociacion.adjudicada": adjudicada,
  "negociacion.desierta": desierta,
  "negociacion.resultado_enviado": resultado,
}

// Un alta que quedó a medias trae en el detalle qué faltó.
const PENDIENTES: Record<string, string> = {
  roles: "; faltó asignar los roles",
  contrasena: "; faltó la contraseña",
}

/** La acción en lenguaje llano; un tipo desconocido se muestra tal cual. */
export function describirActividad(registro: RegistroActividad): string {
  const texto = TEXTOS[registro.tipo as TipoActividad]
  if (!texto) return registro.tipo
  return (
    texto(registro) + (PENDIENTES[String(registro.detalle.pendiente)] ?? "")
  )
}
