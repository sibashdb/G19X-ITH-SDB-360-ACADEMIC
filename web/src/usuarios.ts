/** "Ana López", o el nombre de usuario si la cuenta no tiene nombre. */
export function nombreCompleto(u: {
  nombre: string
  apellidos: string
  usuario: string
}): string {
  return `${u.nombre} ${u.apellidos}`.trim() || u.usuario
}

/** Usuario sugerido a partir del correo: minúsculas, sin acentos, solo letras, números, punto y guion. */
export function sugerirUsuario(correo: string): string {
  return (correo.split("@")[0] ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9.-]/g, "")
    .slice(0, 30)
}
