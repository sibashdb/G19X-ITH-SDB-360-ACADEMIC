import { RefreshCw } from "lucide-react"
import { Link } from "react-router"
import { ContenidoConsulta } from "@/componentes/Estados"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { IndicadorEstado } from "@/componentes/IndicadorEstado"
import { ListaActividad } from "@/componentes/ListaActividad"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Seccion } from "@/componentes/Seccion"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { haceCuanto } from "@/fechas"
import { useEstadoSistema, useRegistros } from "@/sistema"

export function EstadoSistema() {
  return (
    <RequiereRol rol="admin">
      <ContenidoEstado />
    </RequiereRol>
  )
}

function ContenidoEstado() {
  const estado = useEstadoSistema()
  const importaciones = useRegistros({ tipo: "importaciones", tamano: "5" })
  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Estado del sistema"
        descripcion="Si cada servicio de la plataforma responde. Se vuelve a comprobar solo cada 30 segundos."
        acciones={
          <Button
            variant="outline"
            aria-disabled={estado.isFetching}
            onClick={() => {
              if (!estado.isFetching) void estado.refetch()
            }}
          >
            <RefreshCw aria-hidden />
            {estado.isFetching ? "Comprobando…" : "Volver a comprobar"}
          </Button>
        }
      />
      <ContenidoConsulta consulta={estado}>
        {(datos) => {
          const sanos = datos.servicios.filter(
            (s) => s.estado === "sano"
          ).length
          return (
            <div className="space-y-4">
              <p aria-live="polite" className="text-sm text-muted-foreground">
                {sanos} de {datos.servicios.length} servicios sanos · Versión{" "}
                {datos.version} · Comprobado {haceCuanto(datos.comprobado_en)}
              </p>
              <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {datos.servicios.map((s) => (
                  <li key={s.clave}>
                    <Card size="sm" className="h-full">
                      <CardContent className="space-y-2">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <h2 className="font-medium">{s.nombre}</h2>
                          <IndicadorEstado estado={s.estado} />
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {s.detalle}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {s.tiempo_ms === null
                            ? "Sin respuesta"
                            : `Respondió en ${s.tiempo_ms} ms`}
                        </p>
                      </CardContent>
                    </Card>
                  </li>
                ))}
              </ul>
            </div>
          )
        }}
      </ContenidoConsulta>
      <Seccion
        titulo="Últimas importaciones"
        acciones={
          <Link
            to="/sistema/actividad?tipo=importaciones"
            className="text-sm font-medium text-accent hover:underline"
          >
            Ver todas las importaciones
          </Link>
        }
      >
        <ContenidoConsulta consulta={importaciones}>
          {(datos) =>
            datos.elementos.length > 0 ? (
              <ListaActividad elementos={datos.elementos} />
            ) : (
              <p className="text-sm text-muted-foreground">
                Aún no hay importaciones registradas.
              </p>
            )
          }
        </ContenidoConsulta>
      </Seccion>
    </section>
  )
}
