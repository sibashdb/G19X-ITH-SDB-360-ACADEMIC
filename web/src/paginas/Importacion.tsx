import { useState, type FormEvent } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { ErrorApi, pedir } from "@/api"
import { useRoles, useToken } from "@/auth"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { ResumenImportacion } from "@/tipos"

const ENTIDADES = [
  ["servicios", "1. Catálogo de servicios"],
  ["proveedores", "2. Proveedores"],
  ["tipo_cambio", "3. Tipo de cambio"],
  ["contratos", "4. Contratos"],
  ["desempeno", "5. Desempeño"],
] as const

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
  const token = useToken()
  const roles = useRoles()
  const clienteConsultas = useQueryClient()
  const [entidad, setEntidad] = useState<string>("servicios")
  const [archivo, setArchivo] = useState<File | null>(null)

  const importacion = useMutation({
    mutationFn: (datos: { entidad: string; archivo: File }) => {
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

  if (!roles.includes("admin")) {
    return <p role="alert">Solo los administradores pueden importar datos.</p>
  }

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (archivo) importacion.mutate({ entidad, archivo })
  }

  const resumen = importacion.data
  return (
    <section className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-semibold">Importar datos del ERP</h1>
      <p className="text-sm text-muted-foreground">
        Cargue los archivos en el orden indicado: contratos y desempeño hacen referencia a
        proveedores y servicios ya importados. Si un archivo tiene errores, no se importa ninguna
        fila. Se aceptan CSV en UTF-8 separados por coma o punto y coma (máximo 10 MB).
      </p>
      <form onSubmit={enviar} className="space-y-3">
        <div className="space-y-1">
          <label htmlFor="entidad" className="text-sm font-medium">
            Tipo de archivo
          </label>
          <select
            id="entidad"
            value={entidad}
            onChange={(e) => setEntidad(e.target.value)}
            className="block h-9 w-full rounded-md border bg-background px-2 text-sm"
          >
            {ENTIDADES.map(([valor, nombre]) => (
              <option key={valor} value={valor}>
                {nombre}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label htmlFor="archivo" className="text-sm font-medium">
            Archivo CSV
          </label>
          <Input
            id="archivo"
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
          />
        </div>
        <Button type="submit" disabled={!archivo || importacion.isPending}>
          {importacion.isPending ? "Importando…" : "Importar"}
        </Button>
      </form>

      {resumen && (
        <Alert>
          <AlertTitle>Importación completada</AlertTitle>
          <AlertDescription>
            {resumen.filas} filas leídas · {resumen.registros} registros · {resumen.omitidos}{" "}
            omitidos · {resumen.eventos} eventos
          </AlertDescription>
        </Alert>
      )}
      {importacion.error && <DetalleError error={importacion.error} />}
    </section>
  )
}
