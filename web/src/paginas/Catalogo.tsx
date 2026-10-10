import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Package, Plus, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { Link } from "react-router"
import { enviarJson, pedir } from "@/api"
import { useToken } from "@/auth"
import { ConfirmarAccion } from "@/componentes/ConfirmarAccion"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { EtiquetaEstado } from "@/componentes/EtiquetaEstado"
import { Filtro } from "@/componentes/Filtro"
import { FormularioServicio } from "@/componentes/FormularioServicio"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { unoDe, useParametros } from "@/parametros"
import {
  CATEGORIAS,
  NOMBRES_CATEGORIA,
  NOMBRES_UNIDAD,
  type Servicio,
  type Unidad,
} from "@/tipos"

const ESTADOS = ["activos", "inactivos"] as const

export function Catalogo() {
  return (
    <RequiereRol rol="admin">
      <ContenidoCatalogo />
    </RequiereRol>
  )
}

function ContenidoCatalogo() {
  const token = useToken()
  const cliente = useQueryClient()
  const [parametros, actualizar] = useParametros()
  const categoria = unoDe(parametros.get("categoria"), CATEGORIAS)
  const estado = unoDe(parametros.get("estado"), ESTADOS)
  const [abierto, setAbierto] = useState(false)
  const [editando, setEditando] = useState<Servicio | null>(null)
  // Cada apertura monta un formulario nuevo: no arrastra lo escrito ni un servicio ya desactualizado.
  const [apertura, setApertura] = useState(0)
  const [aviso, setAviso] = useState<string | null>(null)
  // Código del servicio cuyo botón de estado debe recibir el foco cuando lleguen los datos nuevos.
  const enfocar = useRef<string | null>(null)
  const botonNuevo = useRef<HTMLButtonElement>(null)
  // El panel se abre por estado: recuerda qué botón lo abrió para devolverle el foco.
  const origen = useRef<HTMLElement | null>(null)

  const consulta = useQuery({
    queryKey: ["servicios", "con-inactivos"],
    queryFn: () =>
      pedir<Servicio[]>("/proveedores/servicios?incluir_inactivos=true", token),
    enabled: Boolean(token),
  })

  const cambioEstado = useMutation({
    mutationFn: (s: Servicio) =>
      pedir<Servicio>(
        `/proveedores/servicios/${encodeURIComponent(s.codigo)}`,
        token,
        enviarJson("PATCH", { activo: !s.activo })
      ),
    onSuccess: async (s) => {
      enfocar.current = s.codigo
      await cliente.invalidateQueries({ queryKey: ["servicios"] })
      setAviso(
        s.activo
          ? `Se activó el servicio ${s.codigo}.`
          : `Se desactivó el servicio ${s.codigo}.`
      )
    },
    onError: (error) => setAviso(error.message),
  })

  // "Desactivar" y "Activar" se reemplazan entre sí: el foco pasa al botón nuevo de la fila o,
  // si la fila ya no se ve con el filtro actual, a "Nuevo servicio".
  useEffect(() => {
    const codigo = enfocar.current
    if (!codigo) return
    enfocar.current = null
    const boton = document.querySelector<HTMLElement>(
      `[data-estado-servicio="${codigo}"]`
    )
    ;(boton ?? botonNuevo.current)?.focus()
  }, [consulta.data])

  function abrir(servicio: Servicio | null, desde: HTMLElement) {
    origen.current = desde
    setEditando(servicio)
    setApertura((n) => n + 1)
    setAbierto(true)
  }

  function alternar(servicio: Servicio) {
    if (!cambioEstado.isPending) cambioEstado.mutate(servicio)
  }

  const limpiar = () => actualizar({ categoria: null, estado: null })

  function contenido() {
    if (consulta.isPending) return <EstadoCarga />
    if (consulta.isError)
      return (
        <EstadoError
          error={consulta.error}
          alReintentar={() => void consulta.refetch()}
        />
      )
    if (consulta.data.length === 0)
      return (
        <EstadoVacio
          icono={Package}
          titulo="Aún no hay servicios en el catálogo"
          descripcion="Impórtelos desde el ERP o dé de alta el primero."
          accion={
            <Button asChild variant="outline">
              <Link to="/importacion">Ir a Importación</Link>
            </Button>
          }
        />
      )
    const visibles = consulta.data.filter(
      (s) =>
        (!categoria || s.categoria === categoria) &&
        (!estado || s.activo === (estado === "activos"))
    )
    if (visibles.length === 0)
      return (
        <EstadoVacio
          titulo="Sin resultados"
          descripcion="Ningún servicio coincide con los filtros."
          accion={
            <Button type="button" variant="ghost" onClick={limpiar}>
              <X aria-hidden />
              Limpiar filtros
            </Button>
          }
        />
      )
    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Código</TableHead>
            <TableHead>Nombre</TableHead>
            <TableHead>Categoría</TableHead>
            <TableHead>Unidad</TableHead>
            <TableHead>Moneda</TableHead>
            <TableHead>Estado</TableHead>
            <TableHead>
              <span className="sr-only">Acciones</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibles.map((s) => (
            <TableRow key={s.id}>
              <TableCell className="font-mono text-xs">{s.codigo}</TableCell>
              <TableCell className="whitespace-normal">{s.nombre}</TableCell>
              <TableCell>
                {NOMBRES_CATEGORIA[s.categoria] ?? s.categoria}
              </TableCell>
              <TableCell>
                {NOMBRES_UNIDAD[s.unidad as Unidad] ?? s.unidad}
              </TableCell>
              <TableCell>{s.moneda}</TableCell>
              <TableCell>
                <EtiquetaEstado activo={s.activo} />
              </TableCell>
              <TableCell>
                <div className="flex justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    aria-label={`Editar ${s.codigo}`}
                    onClick={(e) => abrir(s, e.currentTarget)}
                  >
                    Editar
                  </Button>
                  {s.activo ? (
                    <ConfirmarAccion
                      titulo={`¿Desactivar ${s.codigo}?`}
                      descripcion="Dejará de aparecer en Precios y en las listas para elegir servicios. Sus contratos y su historial se conservan; puede activarlo cuando quiera."
                      textoConfirmar="Desactivar"
                      alConfirmar={() => alternar(s)}
                    >
                      <Button
                        variant="outline"
                        size="sm"
                        aria-label={`Desactivar ${s.codigo}`}
                        data-estado-servicio={s.codigo}
                        aria-disabled={cambioEstado.isPending}
                      >
                        Desactivar
                      </Button>
                    </ConfirmarAccion>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      aria-label={`Activar ${s.codigo}`}
                      data-estado-servicio={s.codigo}
                      aria-disabled={cambioEstado.isPending}
                      onClick={() => alternar(s)}
                    >
                      Activar
                    </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    )
  }

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Catálogo de servicios"
        descripcion="Los servicios de TI que se compran. Se desactivan, no se borran: sus contratos y su historial se conservan."
        acciones={
          <Button
            ref={botonNuevo}
            onClick={(e) => abrir(null, e.currentTarget)}
          >
            <Plus aria-hidden />
            Nuevo servicio
          </Button>
        }
      />
      <div aria-live="polite">
        {aviso && <p className="text-sm">{aviso}</p>}
      </div>
      <Card>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <div
              role="group"
              aria-label="Filtrar por categoría"
              className="flex flex-wrap gap-2"
            >
              <Filtro
                activo={!categoria}
                onClick={() => actualizar({ categoria: null })}
              >
                Todas
              </Filtro>
              {CATEGORIAS.map((c) => (
                <Filtro
                  key={c}
                  activo={categoria === c}
                  onClick={() => actualizar({ categoria: c })}
                >
                  {NOMBRES_CATEGORIA[c]}
                </Filtro>
              ))}
            </div>
            <div
              role="group"
              aria-label="Filtrar por estado"
              className="flex flex-wrap gap-2 md:ml-auto"
            >
              <Filtro
                activo={!estado}
                onClick={() => actualizar({ estado: null })}
              >
                Todos
              </Filtro>
              <Filtro
                activo={estado === "activos"}
                onClick={() => actualizar({ estado: "activos" })}
              >
                Activos
              </Filtro>
              <Filtro
                activo={estado === "inactivos"}
                onClick={() => actualizar({ estado: "inactivos" })}
              >
                Inactivos
              </Filtro>
            </div>
          </div>
          {contenido()}
        </CardContent>
      </Card>
      <FormularioServicio
        key={apertura}
        abierto={abierto}
        alCambiarAbierto={setAbierto}
        servicio={editando}
        devolverFoco={origen}
        alGuardar={(guardado, esAlta) => {
          void cliente.invalidateQueries({ queryKey: ["servicios"] })
          setAviso(
            esAlta
              ? `Se dio de alta el servicio ${guardado.codigo}.`
              : `Se guardaron los cambios de ${guardado.codigo}.`
          )
        }}
      />
    </section>
  )
}
