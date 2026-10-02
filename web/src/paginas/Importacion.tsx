import { useMutation, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, ArrowRight, Check, CircleCheck, FileSpreadsheet, Upload } from "lucide-react"
import { useState, type DragEvent } from "react"
import { ErrorApi, pedir } from "@/api"
import { useToken } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Seccion } from "@/componentes/Seccion"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"
import type { ResumenImportacion } from "@/tipos"

const ENTIDADES = [
  { valor: "servicios", nombre: "Catálogo de servicios", descripcion: "Servicios de TI con su categoría, unidad y moneda." },
  { valor: "proveedores", nombre: "Proveedores", descripcion: "RFC, nombre, tamaño, categorías y contacto." },
  { valor: "tipo_cambio", nombre: "Tipo de cambio", descripcion: "Tipo de cambio mensual de USD a MXN." },
  { valor: "contratos", nombre: "Contratos", descripcion: "Contratos y sus líneas; requiere proveedores y servicios." },
  { valor: "desempeno", nombre: "Desempeño", descripcion: "Indicadores mensuales por proveedor; requiere proveedores." },
] as const

type Entidad = (typeof ENTIDADES)[number]["valor"]

const PASOS = ["Tipo de archivo", "Archivo", "Resultado"]
const MAX_BYTES = 10 * 1024 * 1024

/** Revisa en el navegador lo que el servidor rechazaría de todos modos, para avisar antes de subir. */
export function validarArchivo(archivo: File): string | null {
  if (!archivo.name.toLowerCase().endsWith(".csv")) return "El archivo debe tener extensión .csv."
  if (archivo.size > MAX_BYTES) return "El archivo excede el límite de 10 MB."
  if (archivo.size === 0) return "El archivo está vacío."
  return null
}

function tamanoLegible(bytes: number): string {
  const formato = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 1 })
  return bytes < 1024 * 1024
    ? `${formato.format(bytes / 1024)} KB`
    : `${formato.format(bytes / (1024 * 1024))} MB`
}

function Pasos({ actual }: { actual: number }) {
  return (
    <ol aria-label="Pasos de la importación" className="flex flex-wrap gap-4">
      {PASOS.map((nombre, i) => {
        const numero = i + 1
        const hecho = numero < actual
        const enCurso = numero === actual
        return (
          <li
            key={nombre}
            aria-current={enCurso ? "step" : undefined}
            className="flex items-center gap-2 text-sm"
          >
            <span
              aria-hidden
              className={cn(
                "flex size-6 items-center justify-center rounded-full border text-xs font-semibold",
                enCurso && "border-accent bg-accent text-accent-foreground",
                hecho && "border-success text-success"
              )}
            >
              {hecho ? <Check className="size-3.5" /> : numero}
            </span>
            <span className={enCurso || hecho ? "font-medium" : "text-muted-foreground"}>{nombre}</span>
            {hecho && <span className="sr-only">(completado)</span>}
          </li>
        )
      })}
    </ol>
  )
}

function DetalleError({ error }: { error: Error }) {
  const deApi = error instanceof ErrorApi ? error : null
  return (
    <Alert variant="destructive">
      <AlertTitle>{deApi?.titulo ?? "No se pudo importar"}</AlertTitle>
      <AlertDescription>
        <p>{error.message}</p>
        {deApi && deApi.errores.length > 0 && (
          <Table className="mt-2">
            <TableHeader>
              <TableRow>
                <TableHead>Fila</TableHead>
                <TableHead>Campo</TableHead>
                <TableHead>Problema</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {deApi.errores.map((e) => (
                <TableRow key={`${e.fila}-${e.campo}-${e.mensaje}`}>
                  <TableCell>{e.fila}</TableCell>
                  <TableCell className="font-mono">{e.campo}</TableCell>
                  <TableCell>{e.mensaje}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </AlertDescription>
    </Alert>
  )
}

export function Importacion() {
  return (
    <RequiereRol rol="admin">
      <FlujoImportacion />
    </RequiereRol>
  )
}

function FlujoImportacion() {
  const token = useToken()
  const clienteConsultas = useQueryClient()
  const [paso, setPaso] = useState(1)
  const [entidad, setEntidad] = useState<Entidad>("servicios")
  const [archivo, setArchivo] = useState<File | null>(null)
  const [errorArchivo, setErrorArchivo] = useState<string | null>(null)
  const [arrastrando, setArrastrando] = useState(false)

  const importacion = useMutation({
    mutationFn: (datos: { entidad: Entidad; archivo: File }) => {
      const formulario = new FormData()
      formulario.append("archivo", datos.archivo)
      return pedir<ResumenImportacion>(`/proveedores/importaciones/${datos.entidad}`, token, {
        method: "POST",
        body: formulario,
      })
    },
    // "proveedor" es el prefijo de las consultas del detalle (ficha, contratos y desempeño).
    onSuccess: () =>
      Promise.all([
        clienteConsultas.invalidateQueries({ queryKey: ["proveedores"] }),
        clienteConsultas.invalidateQueries({ queryKey: ["proveedor"] }),
      ]),
  })

  const indice = ENTIDADES.findIndex((e) => e.valor === entidad)
  const actual = ENTIDADES[indice]
  const siguiente = ENTIDADES[indice + 1]

  function elegir(nuevo: File | null) {
    setArchivo(nuevo)
    setErrorArchivo(nuevo ? validarArchivo(nuevo) : null)
  }

  function soltar(evento: DragEvent<HTMLLabelElement>) {
    evento.preventDefault()
    setArrastrando(false)
    const archivos = evento.dataTransfer.files
    if (archivos.length > 1) {
      setArchivo(null)
      setErrorArchivo("Suelte un solo archivo a la vez.")
      return
    }
    elegir(archivos[0] ?? null)
  }

  function importar() {
    if (archivo && !errorArchivo) {
      importacion.mutate({ entidad, archivo }, { onSettled: () => setPaso(3) })
    }
  }

  function empezar(nueva: Entidad, nuevoPaso: number) {
    importacion.reset()
    elegir(null)
    setEntidad(nueva)
    setPaso(nuevoPaso)
  }

  return (
    <section className="max-w-3xl space-y-6">
      <EncabezadoPagina
        titulo="Importar datos del ERP"
        descripcion="Cargue los archivos CSV exportados del ERP. Si un archivo tiene errores, no se importa ninguna fila."
      />
      <Pasos actual={paso} />

      {paso === 1 && (
        <Seccion titulo="1. Elija el tipo de archivo">
          <fieldset className="space-y-2">
            <legend className="mb-2 text-sm text-muted-foreground">
              Siga el orden recomendado: contratos y desempeño hacen referencia a proveedores y servicios ya
              importados.
            </legend>
            {ENTIDADES.map((e, i) => (
              <label
                key={e.valor}
                className="flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/50 has-checked:border-accent"
              >
                <input
                  type="radio"
                  name="entidad"
                  value={e.valor}
                  checked={entidad === e.valor}
                  onChange={() => setEntidad(e.valor)}
                  className="mt-1 accent-accent"
                />
                <span>
                  <span className="font-medium">
                    {i + 1}. {e.nombre}
                  </span>
                  <span className="block text-sm text-muted-foreground">{e.descripcion}</span>
                </span>
              </label>
            ))}
          </fieldset>
          <Button className="mt-4" onClick={() => setPaso(2)}>
            Continuar
            <ArrowRight aria-hidden />
          </Button>
        </Seccion>
      )}

      {paso === 2 && (
        <Seccion titulo={`2. Elija el archivo: ${actual.nombre}`}>
          <div className="space-y-4">
            <label
              onDragOver={(evento) => {
                evento.preventDefault()
                setArrastrando(true)
              }}
              onDragLeave={() => setArrastrando(false)}
              onDrop={soltar}
              className={cn(
                "flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed p-8 text-center transition-colors focus-within:ring-2 focus-within:ring-ring",
                arrastrando && "border-accent bg-muted"
              )}
            >
              <Upload aria-hidden className="size-8 text-muted-foreground" />
              <span className="font-medium">Arrastre el archivo CSV aquí o haga clic para elegirlo</span>
              <span className="text-sm text-muted-foreground">
                CSV en UTF-8, separado por coma o punto y coma, de hasta 10 MB.
              </span>
              <input
                type="file"
                accept=".csv,text/csv"
                className="sr-only"
                onChange={(evento) => elegir(evento.target.files?.[0] ?? null)}
              />
            </label>
            {archivo && !errorArchivo && (
              <p className="flex items-center gap-2 text-sm">
                <FileSpreadsheet aria-hidden className="size-4 text-muted-foreground" />
                {archivo.name} · {tamanoLegible(archivo.size)}
              </p>
            )}
            {errorArchivo && (
              <p role="alert" className="text-sm text-destructive">
                {errorArchivo}
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => setPaso(1)}>
                <ArrowLeft aria-hidden />
                Atrás
              </Button>
              <Button onClick={importar} disabled={!archivo || Boolean(errorArchivo) || importacion.isPending}>
                {importacion.isPending ? "Importando…" : "Importar"}
              </Button>
            </div>
          </div>
        </Seccion>
      )}

      {paso === 3 && (
        <Seccion titulo="3. Resultado">
          {importacion.isSuccess && (
            <div className="space-y-4">
              <Alert role="status">
                <CircleCheck aria-hidden className="text-success" />
                <AlertTitle>Importación completada</AlertTitle>
                <AlertDescription>
                  Se importó {archivo?.name} ({actual.nombre}).
                </AlertDescription>
              </Alert>
              <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {(
                  [
                    ["Filas leídas", importacion.data.filas],
                    ["Registros", importacion.data.registros],
                    ["Omitidos", importacion.data.omitidos],
                    ["Eventos", importacion.data.eventos],
                  ] as const
                ).map(([nombre, valor]) => (
                  <div key={nombre} className="rounded-lg border p-3">
                    <dt className="text-sm text-muted-foreground">{nombre}</dt>
                    <dd className="text-2xl font-semibold">{valor.toLocaleString("es-MX")}</dd>
                  </div>
                ))}
              </dl>
              <div className="flex flex-wrap gap-2">
                {siguiente && (
                  <Button onClick={() => empezar(siguiente.valor, 2)}>
                    Importar {siguiente.nombre}
                    <ArrowRight aria-hidden />
                  </Button>
                )}
                <Button variant="outline" onClick={() => empezar(entidad, 1)}>
                  Importar otro archivo
                </Button>
              </div>
            </div>
          )}
          {importacion.isError && (
            <div className="space-y-4">
              <DetalleError error={importacion.error} />
              <Button variant="outline" onClick={() => empezar(entidad, 2)}>
                Elegir otro archivo
              </Button>
            </div>
          )}
        </Seccion>
      )}
    </section>
  )
}
