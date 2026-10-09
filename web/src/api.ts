export type ErrorFila = { fila?: number; campo: string; mensaje: string }

/** Error de la API con los datos de Problem Details (RFC 9457). */
export class ErrorApi extends Error {
  readonly estado: number
  readonly titulo: string
  readonly errores: ErrorFila[]
  readonly codigo: string | null

  constructor(
    estado: number,
    titulo: string,
    detalle: string,
    errores: ErrorFila[] = [],
    codigo: string | null = null
  ) {
    super(detalle)
    this.estado = estado
    this.titulo = titulo
    this.errores = errores
    this.codigo = codigo
  }
}

/** Mensajes en español para respuestas de error sin Problem Details (p. ej. las del proxy). */
function problemaPorEstado(estado: number): {
  titulo: string
  detalle: string
} {
  if (estado === 413) {
    return {
      titulo: "Contenido demasiado grande",
      detalle: "El archivo excede el límite de 10 MB.",
    }
  }
  if (estado === 429) {
    return {
      titulo: "Demasiadas solicitudes",
      detalle: "Espere unos segundos e intente de nuevo.",
    }
  }
  if (estado >= 500) {
    return {
      titulo: "Servicio no disponible",
      detalle: "El servicio no está disponible; intente más tarde.",
    }
  }
  return { titulo: "Error", detalle: `Ocurrió un error (código ${estado}).` }
}

export async function pedir<T>(
  ruta: string,
  token: string | undefined,
  init: RequestInit = {}
): Promise<T> {
  const cabeceras = new Headers(init.headers)
  if (token) cabeceras.set("Authorization", `Bearer ${token}`)
  let respuesta: Response
  try {
    respuesta = await fetch(`/api${ruta}`, { ...init, headers: cabeceras })
  } catch (error) {
    // Una cancelación pedida por el llamador no es un fallo de red.
    if (init.signal?.aborted) throw error
    // fetch rechaza, con un mensaje en inglés, cuando no hay red o el gateway no responde.
    throw new ErrorApi(
      0,
      "Sin conexión",
      "No se pudo conectar con el servidor; revise su conexión e intente de nuevo."
    )
  }
  if (!respuesta.ok) {
    const cuerpo: unknown = await respuesta.json().catch(() => null)
    const problema =
      typeof cuerpo === "object" && cuerpo !== null
        ? (cuerpo as {
            title?: string
            detail?: string
            errores?: ErrorFila[]
            codigo?: string
          })
        : {}
    const porDefecto = problemaPorEstado(respuesta.status)
    throw new ErrorApi(
      respuesta.status,
      problema.title ?? porDefecto.titulo,
      problema.detail ?? porDefecto.detalle,
      problema.errores ?? [],
      problema.codigo ?? null
    )
  }
  if (respuesta.status === 204) return undefined as T
  return (await respuesta.json()) as T
}

/** Opciones de fetch para enviar JSON. */
export function enviarJson(
  metodo: "POST" | "PATCH",
  datos?: unknown
): RequestInit {
  return {
    method: metodo,
    headers: { "Content-Type": "application/json" },
    body: datos === undefined ? undefined : JSON.stringify(datos),
  }
}

/** Mensajes de error por campo ("body.correo" → "correo") para mostrarlos junto a cada campo. */
export function erroresPorCampo(error: unknown): Record<string, string> {
  if (!(error instanceof ErrorApi)) return {}
  return Object.fromEntries(
    error.errores.map((e) => [e.campo.replace(/^body\./, ""), e.mensaje])
  )
}
