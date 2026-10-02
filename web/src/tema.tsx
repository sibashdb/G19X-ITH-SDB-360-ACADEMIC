import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react"

export type Tema = "claro" | "oscuro" | "sistema"

/** Clave de localStorage; public/tema.js usa la misma. */
export const CLAVE_TEMA = "plataforma-tema"

export const NOMBRES_TEMA: Record<Tema, string> = {
  claro: "Claro",
  oscuro: "Oscuro",
  sistema: "Sistema",
}

const CONSULTA_OSCURO = "(prefers-color-scheme: dark)"

/** Tema guardado; un valor desconocido o un almacenamiento bloqueado cuentan como "sistema". */
function temaGuardado(): Tema {
  try {
    const valor = localStorage.getItem(CLAVE_TEMA)
    return valor === "claro" || valor === "oscuro" ? valor : "sistema"
  } catch {
    return "sistema"
  }
}

export function aplicarTema(tema: Tema): void {
  const oscuro =
    tema === "oscuro" ||
    (tema === "sistema" && window.matchMedia(CONSULTA_OSCURO).matches)
  document.documentElement.classList.toggle("dark", oscuro)
  document.documentElement.style.colorScheme = oscuro ? "dark" : "light"
}

type EstadoTema = { tema: Tema; cambiarTema: (tema: Tema) => void }

const ContextoTema = createContext<EstadoTema | null>(null)

export function ProveedorTema({ children }: { children: ReactNode }) {
  const [tema, setTema] = useState<Tema>(temaGuardado)

  useEffect(() => {
    aplicarTema(tema)
    if (tema !== "sistema") return
    // En "sistema" se sigue al sistema operativo también mientras la app está abierta.
    const consulta = window.matchMedia(CONSULTA_OSCURO)
    const alCambiar = () => aplicarTema("sistema")
    consulta.addEventListener("change", alCambiar)
    return () => consulta.removeEventListener("change", alCambiar)
  }, [tema])

  function cambiarTema(nuevo: Tema) {
    try {
      localStorage.setItem(CLAVE_TEMA, nuevo)
    } catch {
      // Sin almacenamiento (modo privado estricto): el tema dura lo que la pestaña.
    }
    setTema(nuevo)
  }

  return <ContextoTema value={{ tema, cambiarTema }}>{children}</ContextoTema>
}

export function useTema(): EstadoTema {
  const contexto = useContext(ContextoTema)
  if (!contexto) throw new Error("useTema debe usarse dentro de ProveedorTema")
  return contexto
}
