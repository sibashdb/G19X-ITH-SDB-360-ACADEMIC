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
