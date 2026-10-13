import { useMutation } from "@tanstack/react-query"
import { CircleAlert, Database, LoaderCircle, RefreshCw } from "lucide-react"
import { useState } from "react"
import { enviarJson, pedir } from "@/api"
import { useToken } from "@/auth"
import { ContenidoConsulta, EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Termino } from "@/componentes/Termino"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
  fraccionComoPorcentaje,
  useInteligencia,
  type ModeloPrecios,
  type RegistroModelos,
} from "@/inteligencia"

function Estado({
  modelo,
  enUso,
}: {
  modelo: ModeloPrecios
  enUso: number | null
}) {
  if (modelo.version === enUso) return <Badge variant="success">En uso</Badge>
  return modelo.promovido ? (
    <Badge variant="outline">Promovido</Badge>
  ) : (
    <Badge variant="secondary">No promovido</Badge>
  )
}

/**
 * Lo que pasó con el entrenamiento que pidió esta persona (o el que está corriendo).
 * `ocupado` incluye la petición y su nueva lectura: mientras dura, `datos` aún es el registro
 * anterior y no puede decir ni la versión nueva ni el motivo de un fallo.
 */
function Resultado({
  datos,
  antes,
  ocupado,
}: {
  datos: RegistroModelos
  antes: number | null
  ocupado: boolean
}) {
  if (ocupado) {
    return (
      <>
        <LoaderCircle
          aria-hidden
          className="size-4 animate-spin motion-reduce:animate-none"
        />
        Entrenando el modelo de precios; puede tardar un minuto.
      </>
    )
  }
  if (antes === null) return null
  const nuevo = datos.elementos.find((m) => m.version > antes)
  if (nuevo) {
    return (
      <>
        Versión {nuevo.version}: MAPE {fraccionComoPorcentaje(nuevo.mape)}{" "}
        (línea base {fraccionComoPorcentaje(nuevo.mape_linea_base)}).{" "}
        {nuevo.promovido
          ? "Se promovió: ahora calcula el precio de referencia."
          : "No se promovió: no mejoró la línea base."}
      </>
    )
  }
  return datos.ultimo_error ? (
    <span className="text-destructive">
      No se pudo entrenar: {datos.ultimo_error}
    </span>
  ) : null
}

function Contenido({ datos }: { datos: RegistroModelos }) {
  const token = useToken()
  // La versión más reciente al pedir el entrenamiento; null si esta persona no pidió ninguno.
  const [antes, setAntes] = useState<number | null>(null)
  const modelos = useInteligencia<RegistroModelos>("/modelos")
  const entrenar = useMutation({
    mutationFn: () =>
      pedir<{ entrenando: boolean }>(
        "/inteligencia/modelos/entrenar",
        token,
        enviarJson("POST")
      ),
    // Se espera la nueva lectura: así el resultado no se calcula con el registro anterior.
    onSettled: () => modelos.refetch(),
  })
  const ocupado = entrenar.isPending || datos.entrenando
  const enUso = datos.elementos.find((m) => m.version === datos.en_uso)

  function reentrenar() {
    if (ocupado) return
    setAntes(datos.elementos[0]?.version ?? 0)
    entrenar.mutate()
  }

  return (
    <div className="space-y-4">
      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-muted-foreground">Modelo en uso</dt>
          <dd className="font-medium">
            {datos.en_uso !== null ? (
              `Versión ${datos.en_uso}`
            ) : (
              <Termino clave="lineaBase">Línea base</Termino>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">
            <Termino clave="mape">MAPE</Termino> del modelo en uso
          </dt>
          <dd className="font-medium">
            {enUso ? fraccionComoPorcentaje(enUso.mape) : "—"}
          </dd>
        </div>
      </dl>
      {datos.activo !== null && datos.en_uso !== datos.activo && (
        <Alert>
          <CircleAlert aria-hidden />
          <AlertTitle>El modelo promovido no está en uso</AlertTitle>
          <AlertDescription>
            La versión {datos.activo} no se pudo cargar (por ejemplo, tras
            actualizar scikit-learn o si se perdió su archivo). Mientras tanto,
            el precio de referencia usa la línea base. Reentrene el modelo para
            corregirlo.
          </AlertDescription>
        </Alert>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={reentrenar} aria-disabled={ocupado}>
          <RefreshCw aria-hidden />
          Reentrenar modelo de precios
        </Button>
        <p role="status" className="flex items-center gap-2 text-sm">
          <Resultado datos={datos} antes={antes} ocupado={ocupado} />
        </p>
      </div>
      {entrenar.isError && (
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertDescription>{entrenar.error.message}</AlertDescription>
        </Alert>
      )}
      {antes === null && !datos.entrenando && datos.ultimo_error && (
        <p className="text-sm text-muted-foreground">
          El último entrenamiento no se completó: {datos.ultimo_error}
        </p>
      )}
      {datos.elementos.length === 0 ? (
        <EstadoVacio
          icono={Database}
          titulo="Aún no se ha entrenado el modelo"
          descripcion="Se entrena solo al acumular 50 precios nuevos; también puede reentrenarlo ahora."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Versión</TableHead>
              <TableHead>Entrenado</TableHead>
              <TableHead>Origen</TableHead>
              <TableHead className="text-right">Contratos</TableHead>
              <TableHead className="text-right">MAPE</TableHead>
              <TableHead className="text-right">Línea base</TableHead>
              <TableHead>Estado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {datos.elementos.map((m) => (
              <TableRow key={m.version}>
                <TableCell>v{m.version}</TableCell>
                <TableCell>{formatoFechaHora(m.entrenado_en)}</TableCell>
                <TableCell>
                  {m.origen === "manual"
                    ? `Manual · ${m.actor_nombre}`
                    : "Automático"}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {m.observaciones.toLocaleString("es-MX")}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {fraccionComoPorcentaje(m.mape)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {fraccionComoPorcentaje(m.mape_linea_base)}
                </TableCell>
                <TableCell>
                  <Estado modelo={m} enUso={datos.en_uso} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}

/** Modelo en uso, reentrenamiento a pedido y registro de entrenamientos. */
export function PanelModeloPrecios() {
  // Mientras hay un entrenamiento en curso, se vuelve a consultar cada 2 s hasta que termine.
  const modelos = useInteligencia<RegistroModelos>("/modelos", {
    refetchInterval: (consulta) =>
      consulta.state.data?.entrenando ? 2000 : false,
  })
  return (
    <Seccion
      titulo="Modelo de precios"
      descripcion="Estima el precio de referencia. Se reentrena solo al acumular 50 precios nuevos; aquí puede hacerlo a mano."
    >
      <ContenidoConsulta consulta={modelos}>
        {(datos) => <Contenido datos={datos} />}
      </ContenidoConsulta>
    </Seccion>
  )
}
