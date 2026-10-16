import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Bot, TriangleAlert, UserRound } from "lucide-react"
import { useRef, useState } from "react"
import { Link } from "react-router"
import { pedir } from "@/api"
import { useToken } from "@/auth"
import { ConfirmarAccion } from "@/componentes/ConfirmarAccion"
import { EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Termino } from "@/componentes/Termino"
import { EtiquetaEstadoSesion } from "@/componentes/negociacion/Etiquetas"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { haceCuanto } from "@/fechas"
import {
  esFinal,
  formatoUtilidad,
  type EnlaceInvitacion,
  type EstadoCorreo,
  type Evento,
  type SesionResumen,
} from "@/negociacion"

const CORREO: Record<EstadoCorreo, string> = {
  pendiente: "Pendiente",
  enviado: "Enviada",
  fallido: "No se envió",
}

/** Una fila por proveedor: cómo va su sesión, quién la atiende y su invitación (spec §10.1). */
export function TablaSesiones({
  evento,
  esComprador,
  alReenviar,
}: {
  evento: Evento
  esComprador: boolean
  /** `abridor`: el botón «Reenviar» de la fila, para devolverle el foco al cerrar el enlace. */
  alReenviar: (enlace: EnlaceInvitacion, abridor: HTMLElement | null) => void
}) {
  const token = useToken()
  const cliente = useQueryClient()
  const [aviso, setAviso] = useState("")
  const boton = useRef<HTMLElement | null>(null)
  const reenviar = useMutation({
    mutationFn: (s: SesionResumen) =>
      pedir<EnlaceInvitacion>(
        `/negociacion/sesiones/${encodeURIComponent(s.id)}/invitacion`,
        token,
        { method: "POST" }
      ),
    // El enlace solo vive en el diálogo: al terminar, reset() (en `mutate`) suelta la mutación y
    // gcTime 0 la borra de la caché.
    gcTime: 0,
    onSuccess: async (enlace) => {
      setAviso("")
      alReenviar(enlace, boton.current)
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
    },
    onError: (error) => setAviso(error.message),
  })

  return (
    <Seccion
      titulo="Sesiones"
      descripcion={
        <>
          Una por proveedor. «Qué tan buena es para usted» compara su última
          oferta con su <Termino clave="ideal">ideal</Termino> y su{" "}
          <Termino clave="limite">límite</Termino>.
        </>
      }
    >
      <p
        role="status"
        className={aviso ? "mb-2 text-sm text-destructive" : "sr-only"}
      >
        {aviso}
      </p>
      {evento.sesiones.length === 0 ? (
        <EstadoVacio
          titulo="Sin sesiones"
          descripcion="Las sesiones se crean al publicar la negociación."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Proveedor</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Atiende</TableHead>
              <TableHead>
                <Termino clave="ronda">Ronda</Termino>
              </TableHead>
              <TableHead className="text-right">
                Qué tan buena es para usted
              </TableHead>
              <TableHead>Última actividad</TableHead>
              <TableHead>Invitación</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {evento.sesiones.map((s) => (
              <TableRow key={s.id}>
                <TableCell className="whitespace-normal">
                  <Link
                    to={`/negociaciones/${encodeURIComponent(evento.id)}/sesiones/${encodeURIComponent(s.id)}`}
                    className="text-accent hover:underline"
                  >
                    {s.proveedor_nombre}
                  </Link>
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    <EtiquetaEstadoSesion estado={s.estado} />
                    {s.fuera_de_limites && (
                      <Badge variant="warning">
                        <TriangleAlert aria-hidden />
                        Fuera de límites
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <span className="inline-flex items-center gap-1">
                    {s.modo === "agente" ? (
                      <>
                        <Bot aria-hidden className="size-4" />
                        Agente
                      </>
                    ) : (
                      <>
                        <UserRound aria-hidden className="size-4" />
                        Persona
                      </>
                    )}
                  </span>
                </TableCell>
                <TableCell className="tabular-nums">
                  {s.ronda === 0
                    ? "Sin ofertas"
                    : `${s.ronda} de ${evento.rondas_max}`}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatoUtilidad(s.utilidad)}
                </TableCell>
                <TableCell>{haceCuanto(s.actualizado_en)}</TableCell>
                <TableCell className="min-w-40 whitespace-normal">
                  <div className="space-y-1">
                    <p
                      className={
                        s.correo_estado === "fallido"
                          ? "text-destructive"
                          : undefined
                      }
                    >
                      {CORREO[s.correo_estado]}
                    </p>
                    {s.correo_error && (
                      <p className="text-xs text-muted-foreground">
                        {s.correo_error}
                      </p>
                    )}
                    {esComprador &&
                      evento.estado === "abierto" &&
                      !esFinal(s.estado) && (
                        <ConfirmarAccion
                          titulo={`¿Reenviar la invitación a ${s.proveedor_nombre}?`}
                          descripcion="Se envía un enlace nuevo por correo y el anterior deja de servir."
                          textoConfirmar="Reenviar"
                          alConfirmar={() => {
                            if (!reenviar.isPending)
                              reenviar.mutate(s, {
                                onSuccess: () => reenviar.reset(),
                              })
                          }}
                        >
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => {
                              boton.current = e.currentTarget
                            }}
                          >
                            {/* El espacio va fuera del sr-only: dentro, el nombre sale «Reenviarla…». */}
                            Reenviar{" "}
                            <span className="sr-only">
                              la invitación a {s.proveedor_nombre}
                            </span>
                          </Button>
                        </ConfirmarAccion>
                      )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Seccion>
  )
}
