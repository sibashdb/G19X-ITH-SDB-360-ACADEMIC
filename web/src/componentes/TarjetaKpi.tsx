import { ArrowRight, type LucideIcon } from "lucide-react"
import { Link } from "react-router"
import { Card, CardContent } from "@/components/ui/card"

export function TarjetaKpi({
  titulo,
  valor,
  detalle,
  icono: Icono,
  enlace,
  textoEnlace,
}: {
  titulo: string
  valor: string | null
  detalle?: string
  icono: LucideIcon
  enlace: string
  textoEnlace: string
}) {
  return (
    <Card size="sm">
      <CardContent className="space-y-2">
        <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
          <span>{titulo}</span>
          <Icono aria-hidden className="size-4" />
        </div>
        <p className="text-2xl font-semibold">
          {valor ?? (
            <>
              <span aria-hidden>—</span>
              <span className="sr-only">Sin datos</span>
            </>
          )}
        </p>
        {detalle && <p className="text-xs text-muted-foreground">{detalle}</p>}
        <Link
          to={enlace}
          className="inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline"
        >
          {textoEnlace}
          <ArrowRight aria-hidden className="size-3.5" />
        </Link>
      </CardContent>
    </Card>
  )
}
