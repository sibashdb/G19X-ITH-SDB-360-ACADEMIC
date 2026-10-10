import type { ReactNode, Ref } from "react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

export function Seccion({
  titulo,
  descripcion,
  acciones,
  children,
  className,
  refTitulo,
}: {
  titulo: string
  descripcion?: ReactNode
  acciones?: ReactNode
  children: ReactNode
  className?: string
  /** Para mover el foco al título (p. ej. al cambiar de paso); lo vuelve enfocable. */
  refTitulo?: Ref<HTMLHeadingElement>
}) {
  return (
    <Card className={className}>
      <CardHeader className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1">
          <h2
            ref={refTitulo}
            tabIndex={refTitulo ? -1 : undefined}
            className="text-base font-semibold"
          >
            {titulo}
          </h2>
          {descripcion && (
            <p className="text-sm text-muted-foreground">{descripcion}</p>
          )}
        </div>
        {acciones}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}
