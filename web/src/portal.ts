import { pedir } from "@/api"

const CLAVE = "portal-negociacion"
// Respaldo si el navegador bloquea sessionStorage: el token dura mientras la página siga abierta.
let enMemoria: string | null = null

function guardar(token: string): void {
  enMemoria = token
  try {
    sessionStorage.setItem(CLAVE, token)
  } catch {
    // Bloqueado: queda en memoria.
  }
}

function leer(): string | null {
  try {
    // Si solo falló guardar, la copia en memoria sigue valiendo.
    return sessionStorage.getItem(CLAVE) ?? enMemoria
  } catch {
    return enMemoria
  }
}

/** Borra el token de la pestaña y de la memoria; lo usan las pruebas para no arrastrar uno al siguiente caso. */
export function olvidarToken(): void {
  enMemoria = null
  try {
    sessionStorage.removeItem(CLAVE)
  } catch {
    // Bloqueado: no había nada guardado ahí.
  }
}

/**
 * El token de invitación (spec §8.1): llega en el fragmento (#t=…), que no viaja al servidor ni
 * en el Referer. Se guarda en la pestaña y se borra de la barra y del historial. Un enlace nuevo
 * reemplaza al anterior; sin fragmento, se usa el guardado (al recargar).
 */
export function tomarToken(): string | null {
  const nuevo = new URLSearchParams(window.location.hash.slice(1)).get("t")
  if (!nuevo) return leer()
  guardar(nuevo)
  window.history.replaceState(
    window.history.state,
    "",
    window.location.pathname + window.location.search
  )
  return nuevo
}

/** GET o POST a /api/negociacion/portal{ruta} con el token de invitación, nunca con un Bearer. */
export function pedirPortal<T>(
  ruta: string,
  token: string,
  init: RequestInit = {}
): Promise<T> {
  const cabeceras = new Headers(init.headers)
  cabeceras.set("Authorization", `Invitacion ${token}`)
  // Sin token de Keycloak, `pedir` respeta el Authorization de las cabeceras.
  return pedir<T>(`/negociacion/portal${ruta}`, undefined, {
    ...init,
    headers: cabeceras,
  })
}
