export type ErrorFila = { fila: number; campo: string; mensaje: string }

/** Error de la API con los datos de Problem Details (RFC 9457). */
export class ErrorApi extends Error {
  readonly estado: number
  readonly titulo: string
  readonly errores: ErrorFila[]

  constructor(estado: number, titulo: string, detalle: string, errores: ErrorFila[] = []) {
    super(detalle)
    this.estado = estado
    this.titulo = titulo
    this.errores = errores
  }
}

export async function pedir<T>(
  ruta: string,
  token: string | undefined,
  init: RequestInit = {},
): Promise<T> {
  const cabeceras = new Headers(init.headers)
  if (token) cabeceras.set("Authorization", `Bearer ${token}`)
  const respuesta = await fetch(`/api${ruta}`, { ...init, headers: cabeceras })
  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({}))
    throw new ErrorApi(
      respuesta.status,
      cuerpo.title ?? "Error",
      cuerpo.detail ?? respuesta.statusText,
      cuerpo.errores ?? [],
    )
  }
  return (await respuesta.json()) as T
}
