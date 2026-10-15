import { useMutation, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, Bot, Hand, TriangleAlert } from "lucide-react"
import { useState } from "react"
import { Link, useParams } from "react-router"
import { enviarJson, pedir } from "@/api"
import { useRoles, useToken } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { Seccion } from "@/componentes/Seccion"
import { Termino } from "@/componentes/Termino"
import { ContenidoVivo } from "@/componentes/negociacion/ContenidoVivo"
import { Conversacion } from "@/componentes/negociacion/Conversacion"
import { EtiquetaEstadoSesion } from "@/componentes/negociacion/Etiquetas"
import { TablaOfertas } from "@/componentes/negociacion/TablaOfertas"
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
import { formatoFechaHora } from "@/fechas"
import {
  esFinal,
  formatoTermino,
  useNegociacion,
  type MensajeSesion,
  type SesionDetalle,
} from "@/negociacion"
import { formatoMoneda } from "@/tipos"

function ultimoDelProveedor(mensajes: MensajeSesion[]) {
  return mensajes.findLast((m) => m.autor === "proveedor")
}

export function SesionNegociacion() {
  const { sesion = "" } = useParams()
  const consulta = useNegociacion<SesionDetalle>(
    `/sesiones/${encodeURIComponent(sesion)}`,
    {
      // Supervisión en vivo (spec D6); una sesión terminada ya no cambia.
      refetchInterval: (q) =>
        q.state.data && esFinal(q.state.data.estado) ? false : 3000,
    }
  )
  return (
    <div className="space-y-6">
      <ContenidoVivo consulta={consulta}>
        {/* La clave reinicia «visto al abrir» si la caché trae los datos de otra sesión. */}
        {(datos) => <Supervision key={datos.id} datos={datos} />}
      </ContenidoVivo>
    </div>
  )
}

function Supervision({ datos }: { datos: SesionDetalle }) {
  const esComprador = useRoles().includes("comprador")
  // Solo se anuncia lo que llega después de abrir la página, no lo que ya estaba (spec §10.1).
  const [vistoAlAbrir] = useState(
    () => ultimoDelProveedor(datos.mensajes)?.id ?? null
  )
  const ultimo = ultimoDelProveedor(datos.mensajes)
  // La fecha llega al minuto: sin el conteo, dos mensajes del mismo minuto darían el mismo texto
  // y el segundo no se anunciaría.
  const totalDelProveedor = datos.mensajes.filter(
    (m) => m.autor === "proveedor"
  ).length
  const anuncio =
    ultimo && ultimo.id !== vistoAlAbrir
      ? `Nuevo mensaje del proveedor, ${formatoFechaHora(ultimo.fecha)} (mensaje ${totalDelProveedor})`
      : ""

  return (
    <>
      <EncabezadoPagina
        titulo={datos.proveedor_nombre}
        descripcion={`${datos.folio} · ${datos.titulo}`}
        acciones={
          <Button asChild variant="outline">
            <Link to={`/negociaciones/${encodeURIComponent(datos.evento_id)}`}>
              <ArrowLeft aria-hidden />
              Volver a la negociación
            </Link>
          </Button>
        }
      />
      <p aria-live="polite" aria-atomic="true" className="sr-only">
        {anuncio}
      </p>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <EtiquetaEstadoSesion estado={datos.estado} />
        <span>
          {datos.modo === "agente"
            ? "Atiende el agente"
            : "Atiende una persona de Compras"}
        </span>
        <span>
          · <Termino clave="ronda">Ronda</Termino>{" "}
          {`${datos.ronda} de ${datos.rondas_max}`}
        </span>
        {datos.fuera_de_limites && (
          <Badge variant="warning">
            <TriangleAlert aria-hidden />
            Acuerdo fuera de sus límites: lo verá el aprobador
          </Badge>
        )}
      </div>
      {datos.estado === "acuerdo_tentativo" && (
        <p className="text-sm">
          Quedó un <Termino clave="acuerdoTentativo">acuerdo tentativo</Termino>
          : no es vinculante hasta que se adjudique y se apruebe.
        </p>
      )}
      {esComprador && !esFinal(datos.estado) && <Control datos={datos} />}
      <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
        <Seccion titulo="Conversación">
          <Conversacion datos={datos} />
        </Seccion>
        <Seccion titulo="Sus límites" descripcion="El proveedor nunca los ve.">
          <Limites datos={datos} />
        </Seccion>
      </div>
      <Seccion
        titulo="Ofertas"
        descripcion="«Para usted» es qué tan buena es cada oferta frente a su ideal y su límite."
      >
        <TablaOfertas datos={datos} />
      </Seccion>
    </>
  )
}

function Control({ datos }: { datos: SesionDetalle }) {
  const token = useToken()
  const cliente = useQueryClient()
  const [aviso, setAviso] = useState("")
  const cambiar = useMutation({
    mutationFn: (accion: "tomar" | "devolver") =>
      pedir<SesionDetalle>(
        `/negociacion/sesiones/${encodeURIComponent(datos.id)}/control`,
        token,
        enviarJson("POST", { accion })
      ),
    onSuccess: async (respuesta, accion) => {
      setAviso(
        accion === "tomar"
          ? "Ahora usted atiende esta sesión: el agente no responderá hasta que la devuelva."
          : "El agente vuelve a atender la sesión."
      )
      // La respuesta es la sesión completa: el botón cambia de texto sin esperar a la recarga.
      cliente.setQueryData(
        ["negociacion", `/sesiones/${encodeURIComponent(datos.id)}`],
        respuesta
      )
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
    },
    onError: (error) => setAviso(error.message),
  })
  const tomar = datos.modo === "agente"
  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* Un solo botón que cambia de texto: el foco se queda en él al tomar o devolver. */}
      <Button
        variant={tomar ? "default" : "outline"}
        aria-disabled={cambiar.isPending}
        onClick={() => {
          if (!cambiar.isPending) cambiar.mutate(tomar ? "tomar" : "devolver")
        }}
      >
        {tomar ? <Hand aria-hidden /> : <Bot aria-hidden />}
        {tomar ? "Tomar el control" : "Devolver al agente"}
      </Button>
      <p
        role="status"
        className={aviso ? "text-sm text-muted-foreground" : "sr-only"}
      >
        {aviso}
      </p>
    </div>
  )
}

function Limites({ datos }: { datos: SesionDetalle }) {
  const monto = (valor: string | null) =>
    valor ? formatoMoneda(valor, datos.moneda) : "—"
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Término</TableHead>
          <TableHead className="text-right">Ideal</TableHead>
          <TableHead className="text-right">Límite</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {datos.lineas.map((l) => (
          <TableRow key={l.id}>
            <TableCell className="whitespace-normal">{`Precio: ${l.nombre}`}</TableCell>
            <TableCell className="text-right tabular-nums">
              {monto(l.ideal)}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {monto(l.limite)}
            </TableCell>
          </TableRow>
        ))}
        {datos.palancas
          .filter((p) => p.clave !== "precio")
          .map((p) => (
            <TableRow key={p.clave}>
              <TableCell className="whitespace-normal">{`${p.nombre} (peso ${p.peso})`}</TableCell>
              <TableCell className="text-right tabular-nums">
                {p.ideal
                  ? formatoTermino(p.ideal, p.unidad, datos.moneda)
                  : "—"}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {p.limite
                  ? formatoTermino(p.limite, p.unidad, datos.moneda)
                  : "—"}
              </TableCell>
            </TableRow>
          ))}
      </TableBody>
    </Table>
  )
}
