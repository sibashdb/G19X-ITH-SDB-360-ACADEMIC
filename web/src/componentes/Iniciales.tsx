import { cn } from "@/lib/utils"

/** Iniciales de las dos primeras palabras con mayúscula (ignora "S.A.", "de", "C.V."). */
export function iniciales(nombre: string): string {
  const letras = nombre
    .split(/\s+/)
    .filter((palabra) => /^\p{Lu}/u.test(palabra) && !palabra.includes("."))
    .slice(0, 2)
    .map((palabra) => palabra[0])
    .join("")
  return letras || nombre.match(/[\p{L}\p{N}]/u)?.[0]?.toUpperCase() || "?"
}

export function Iniciales({
  nombre,
  tamano = "sm",
}: {
  nombre: string
  tamano?: "sm" | "lg"
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full bg-info-suave font-semibold text-accent",
        tamano === "lg" ? "size-12 text-base" : "size-8 text-xs"
      )}
    >
      {iniciales(nombre)}
    </span>
  )
}
