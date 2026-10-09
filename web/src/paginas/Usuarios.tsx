import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { CircleAlert, MailCheck, Search, UserPlus, X } from "lucide-react"
import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react"
import { Link } from "react-router"
import { pedir } from "@/api"
import { NOMBRES_ROL, ROLES, useToken } from "@/auth"
import { DialogoContrasenaTemporal } from "@/componentes/DialogoContrasenaTemporal"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { EtiquetaEstado } from "@/componentes/EtiquetaEstado"
import { Filtro } from "@/componentes/Filtro"
import { FormularioAltaUsuario } from "@/componentes/FormularioAltaUsuario"
import { Iniciales } from "@/componentes/Iniciales"
import { Paginacion } from "@/componentes/Paginacion"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatoFechaHora, haceCuanto } from "@/fechas"
import { enteroPositivo, unoDe, useParametros } from "@/parametros"
import type { PaginaUsuarios, ResultadoAlta } from "@/tipos"
import { nombreCompleto } from "@/usuarios"

const POR_PAGINA = 25
const ESTADOS = ["activos", "inactivos"] as const

export function Usuarios() {
  return (
    <RequiereRol rol="admin">
      <ContenidoUsuarios />
    </RequiereRol>
  )
}

function ContenidoUsuarios() {
  const token = useToken()
  const cliente = useQueryClient()
  const [parametros, actualizar] = useParametros()
  const q = (parametros.get("q") ?? "").trim().slice(0, 100)
  const rol = unoDe(parametros.get("rol"), ROLES)
  const estado = unoDe(parametros.get("estado"), ESTADOS)
  const pagina = enteroPositivo(parametros.get("pagina"), 1, 1000)
  const hayFiltros = Boolean(q || rol || estado)
  const [altaAbierta, setAltaAbierta] = useState(false)
  const [aviso, setAviso] = useState<ReactNode>(null)
  const [temporal, setTemporal] = useState<{
    nombre: string
    contrasena: string
  } | null>(null)

  const botonAlta = useRef<HTMLButtonElement>(null)
  const campoBusqueda = useRef<HTMLInputElement>(null)
  useEffect(() => {
    const campo = campoBusqueda.current
    if (campo && campo.value.trim() !== q) campo.value = q
  }, [q])

  const consulta = useQuery({
    queryKey: ["usuarios", { q, rol, estado, pagina }],
    queryFn: () => {
      const busqueda = new URLSearchParams({
        pagina: String(pagina),
        tamano: String(POR_PAGINA),
      })
      if (q) busqueda.set("busqueda", q)
      if (rol) busqueda.set("rol", rol)
      if (estado) busqueda.set("estado", estado)
      return pedir<PaginaUsuarios>(
        `/administracion/usuarios?${busqueda}`,
        token
      )
    },
    enabled: Boolean(token),
    placeholderData: keepPreviousData,
  })

  function alTerminarAlta(resultado: ResultadoAlta) {
    void cliente.invalidateQueries({ queryKey: ["usuarios"] })
    const nombre = nombreCompleto(resultado.usuario)
    if (resultado.contrasena_temporal) {
      setAviso(null)
      setTemporal({ nombre, contrasena: resultado.contrasena_temporal })
    } else if (resultado.correo_enviado) {
      setAviso(
        <Alert>
          <MailCheck aria-hidden />
          <AlertTitle>Usuario dado de alta</AlertTitle>
          <AlertDescription>
            Se envió la invitación a {resultado.usuario.correo}. La persona
            definirá su contraseña con el enlace, que vence en 72 horas.
          </AlertDescription>
        </Alert>
      )
    } else {
      setAviso(
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertTitle>
            Se creó la cuenta, pero no se pudo enviar la invitación.
          </AlertTitle>
          <AlertDescription>
            <p>
              Desde su ficha puede reintentar el envío o asignar una contraseña
              temporal.
            </p>
            <Link
              to={`/sistema/usuarios/${encodeURIComponent(resultado.usuario.id)}`}
              className="font-medium underline"
            >
              Abrir la ficha de {nombre}
            </Link>
          </AlertDescription>
        </Alert>
      )
    }
  }

  function buscar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const texto = String(
      new FormData(evento.currentTarget).get("q") ?? ""
    ).trim()
    actualizar({ q: texto || null, pagina: null })
  }
  const limpiar = () =>
    actualizar({ q: null, rol: null, estado: null, pagina: null })

  function contenido() {
    if (consulta.isPending) return <EstadoCarga />
    if (consulta.isError)
      return (
        <EstadoError
          error={consulta.error}
          alReintentar={() => void consulta.refetch()}
        />
      )
    const { total, elementos } = consulta.data
    if (elementos.length === 0) {
      return (
        <EstadoVacio
          titulo="Sin resultados"
          descripcion={
            hayFiltros
              ? "Ningún usuario coincide con la búsqueda o los filtros."
              : "Aún no hay usuarios."
          }
          accion={
            hayFiltros && (
              <Button variant="ghost" onClick={limpiar}>
                <X aria-hidden />
                Limpiar filtros
              </Button>
            )
          }
        />
      )
    }
    return (
      <div className="space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Persona</TableHead>
              <TableHead>Usuario</TableHead>
              <TableHead>Roles</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Último acceso</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {elementos.map((u) => (
              <TableRow key={u.id}>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <Iniciales nombre={nombreCompleto(u)} />
                    <div>
                      <Link
                        to={`/sistema/usuarios/${encodeURIComponent(u.id)}`}
                        className="font-medium text-accent hover:underline"
                      >
                        {nombreCompleto(u)}
                      </Link>
                      <div className="text-xs text-muted-foreground">
                        {u.correo}
                      </div>
                    </div>
                  </div>
                </TableCell>
                <TableCell className="font-mono text-xs">{u.usuario}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {u.roles.map((r) => (
                      <Badge key={r} variant="secondary">
                        {NOMBRES_ROL[r]}
                      </Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell>
                  <EtiquetaEstado activo={u.activo} />
                </TableCell>
                <TableCell>
                  {u.ultimo_acceso ? (
                    <time
                      dateTime={u.ultimo_acceso}
                      title={formatoFechaHora(u.ultimo_acceso)}
                    >
                      {haceCuanto(u.ultimo_acceso)}
                    </time>
                  ) : (
                    <span className="text-muted-foreground">Nunca</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Paginacion
          pagina={pagina}
          total={total}
          porPagina={POR_PAGINA}
          nombre="usuarios"
          alCambiar={(p) => actualizar({ pagina: String(p) })}
        />
      </div>
    )
  }

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Usuarios"
        descripcion="Quién puede entrar a la plataforma y con qué rol. Las cuentas se desactivan, no se borran: su historial se conserva."
        acciones={
          <Button ref={botonAlta} onClick={() => setAltaAbierta(true)}>
            <UserPlus aria-hidden />
            Nuevo usuario
          </Button>
        }
      />
      <div aria-live="polite">{aviso}</div>
      <Card>
        <CardContent className="space-y-4">
          <form
            role="search"
            onSubmit={buscar}
            className="flex flex-wrap items-center gap-2"
          >
            <label htmlFor="busqueda-usuarios" className="sr-only">
              Buscar por nombre, usuario o correo
            </label>
            <div className="relative w-full max-w-sm">
              <Search
                aria-hidden
                className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                id="busqueda-usuarios"
                name="q"
                ref={campoBusqueda}
                defaultValue={q}
                placeholder="Nombre, usuario o correo"
                maxLength={100}
                className="pl-8"
              />
            </div>
            <Button type="submit">Buscar</Button>
          </form>
          <div className="flex flex-wrap items-center gap-2">
            <div
              role="group"
              aria-label="Filtrar por rol"
              className="flex flex-wrap gap-2"
            >
              <Filtro
                activo={!rol}
                onClick={() => actualizar({ rol: null, pagina: null })}
              >
                Todos los roles
              </Filtro>
              {ROLES.map((r) => (
                <Filtro
                  key={r}
                  activo={rol === r}
                  onClick={() => actualizar({ rol: r, pagina: null })}
                >
                  {NOMBRES_ROL[r]}
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
                onClick={() => actualizar({ estado: null, pagina: null })}
              >
                Todos
              </Filtro>
              <Filtro
                activo={estado === "activos"}
                onClick={() => actualizar({ estado: "activos", pagina: null })}
              >
                Activos
              </Filtro>
              <Filtro
                activo={estado === "inactivos"}
                onClick={() =>
                  actualizar({ estado: "inactivos", pagina: null })
                }
              >
                Inactivos
              </Filtro>
            </div>
          </div>
          {contenido()}
        </CardContent>
      </Card>
      <FormularioAltaUsuario
        abierto={altaAbierta}
        alCambiarAbierto={setAltaAbierta}
        alTerminar={alTerminarAlta}
        devolverFoco={botonAlta}
      />
      <DialogoContrasenaTemporal
        datos={temporal}
        alCerrar={() => setTemporal(null)}
        devolverFoco={botonAlta}
      />
    </section>
  )
}
