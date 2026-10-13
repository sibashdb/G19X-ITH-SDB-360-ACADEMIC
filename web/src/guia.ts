import { useSyncExternalStore } from "react"

/** Prefijo de las claves de localStorage de la guía de uso. */
export const PREFIJO_GUIA = "plataforma-guia"

/** Clave de la guía de una persona (el `sub` de su token): en un equipo compartido, cada quien la suya. */
export function claveGuia(usuario: string): string {
  return `${PREFIJO_GUIA}:${usuario}`
}

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
const ultimos = new Map<string, { crudo: string | null; estado: EstadoGuia }>()
// Respaldo cuando el almacenamiento falla: la preferencia dura mientras la página siga abierta.
const memoria = new Map<string, string>()

function leer(clave: string): string | null {
  try {
    return localStorage.getItem(clave)
  } catch {
    return memoria.get(clave) ?? null
  }
}

function instantanea(usuario: string): EstadoGuia {
  const clave = claveGuia(usuario)
  const crudo = leer(clave)
  const ultimo = ultimos.get(clave)
  if (ultimo && ultimo.crudo === crudo) return ultimo.estado
  const estado = interpretar(crudo)
  ultimos.set(clave, { crudo, estado })
  return estado
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

function guardar(usuario: string, cambiar: (estado: EstadoGuia) => EstadoGuia) {
  const clave = claveGuia(usuario)
  const valor = JSON.stringify(cambiar(instantanea(usuario)))
  try {
    localStorage.setItem(clave, valor)
  } catch {
    memoria.set(clave, valor)
  }
  oyentes.forEach((oyente) => oyente())
}

export function marcarVisita(
  usuario: string,
  seccion: "proveedores" | "precios"
): void {
  if (instantanea(usuario).visitas[seccion]) return
  guardar(usuario, (estado) => ({
    ...estado,
    visitas: { ...estado.visitas, [seccion]: true },
  }))
}

export function ocultarGuia(usuario: string): void {
  guardar(usuario, (estado) => ({ ...estado, oculta: true }))
}

export function mostrarGuia(usuario: string): void {
  guardar(usuario, (estado) => ({ ...estado, oculta: false }))
}

export function useGuia(usuario: string): EstadoGuia {
  return useSyncExternalStore(suscribir, () => instantanea(usuario))
}
