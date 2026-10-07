import { useSyncExternalStore } from "react"

/** Clave de localStorage con las visitas y la preferencia de la guía de uso. */
export const CLAVE_GUIA = "plataforma-guia"

export type EstadoGuia = {
  oculta: boolean
  visitas: { proveedores: boolean; precios: boolean }
}

const INICIAL: EstadoGuia = {
  oculta: false,
  visitas: { proveedores: false, precios: false },
}

function interpretar(crudo: string | null): EstadoGuia {
  try {
    const valor = JSON.parse(crudo ?? "null")
    return {
      oculta: valor?.oculta === true,
      visitas: {
        proveedores: valor?.visitas?.proveedores === true,
        precios: valor?.visitas?.precios === true,
      },
    }
  } catch {
    return INICIAL
  }
}

// useSyncExternalStore exige devolver el mismo objeto mientras el estado no cambie.
let ultimoCrudo: string | null | undefined
let ultimo: EstadoGuia = INICIAL

function instantanea(): EstadoGuia {
  let crudo: string | null
  try {
    crudo = localStorage.getItem(CLAVE_GUIA)
  } catch {
    return INICIAL
  }
  if (crudo !== ultimoCrudo) {
    ultimoCrudo = crudo
    ultimo = interpretar(crudo)
  }
  return ultimo
}

const oyentes = new Set<() => void>()

function suscribir(oyente: () => void) {
  oyentes.add(oyente)
  window.addEventListener("storage", oyente)
  return () => {
    oyentes.delete(oyente)
    window.removeEventListener("storage", oyente)
  }
}

function guardar(cambiar: (estado: EstadoGuia) => EstadoGuia) {
  try {
    localStorage.setItem(CLAVE_GUIA, JSON.stringify(cambiar(instantanea())))
  } catch {
    // Sin almacenamiento: la guía sigue visible y sin visitas registradas.
  }
  oyentes.forEach((oyente) => oyente())
}

export function marcarVisita(seccion: "proveedores" | "precios"): void {
  if (instantanea().visitas[seccion]) return
  guardar((estado) => ({
    ...estado,
    visitas: { ...estado.visitas, [seccion]: true },
  }))
}

export function ocultarGuia(): void {
  guardar((estado) => ({ ...estado, oculta: true }))
}

export function mostrarGuia(): void {
  guardar((estado) => ({ ...estado, oculta: false }))
}

export function useGuia(): EstadoGuia {
  return useSyncExternalStore(suscribir, instantanea)
}
