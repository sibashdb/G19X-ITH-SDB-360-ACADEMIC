import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  ArrowLeft,
  CircleAlert,
  CircleCheck,
  KeyRound,
  LogOut,
  Mail,
  UserCheck,
  UserX,
} from "lucide-react"
import {
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react"
import { Link, useParams } from "react-router"
import { describirActividad } from "@/actividad"
import { enviarJson, erroresPorCampo, ErrorApi, pedir } from "@/api"
import { NOMBRES_ROL, useToken, type Rol } from "@/auth"
import { CamposRoles } from "@/componentes/CamposRoles"
import { ConfirmarAccion } from "@/componentes/ConfirmarAccion"
import { DialogoContrasenaTemporal } from "@/componentes/DialogoContrasenaTemporal"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { EtiquetaEstado } from "@/componentes/EtiquetaEstado"
import { Iniciales } from "@/componentes/Iniciales"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Seccion } from "@/componentes/Seccion"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { formatoFechaHora, haceCuanto } from "@/fechas"
import type {
  PaginaActividad,
  ResultadoContrasena,
  UsuarioAdmin,
} from "@/tipos"
import { nombreCompleto } from "@/usuarios"

type Mensaje = { tipo: "exito" | "error"; texto: string } | null

export function UsuarioDetalle() {
  return (
    <RequiereRol rol="admin">
      <ContenidoDetalle />
    </RequiereRol>
  )
}

function ContenidoDetalle() {
  const { id = "" } = useParams()
  const token = useToken()
  const ruta = `/administracion/usuarios/${encodeURIComponent(id)}`
  const consulta = useQuery({
    queryKey: ["usuario", id],
    queryFn: () => pedir<UsuarioAdmin>(ruta, token),
    enabled: Boolean(token && id),
  })
  // La actividad solo depende del id de la URL: se pide en paralelo y no tras cargar al usuario.
  useActividad(id)

  if (consulta.isPending) return <EstadoCarga />
  if (consulta.isError) {
    if (consulta.error instanceof ErrorApi && consulta.error.estado === 404) {
      return (
        <EstadoVacio
          titulo="Este usuario no existe"
          descripcion="Puede que el enlace sea incorrecto."
          accion={
            <Button asChild variant="outline">
              <Link to="/sistema/usuarios">Volver a Usuarios</Link>
            </Button>
          }
        />
      )
    }
    return (
      <EstadoError
        error={consulta.error}
        alReintentar={() => void consulta.refetch()}
      />
    )
  }
  return <Ficha usuario={consulta.data} ruta={ruta} />
}

function Ficha({ usuario, ruta }: { usuario: UsuarioAdmin; ruta: string }) {
  const token = useToken()
  const cliente = useQueryClient()
  const id = useId()
  const nombre = nombreCompleto(usuario)
  const [datos, setDatos] = useState({
    nombre: usuario.nombre,
    apellidos: usuario.apellidos,
    correo: usuario.correo,
  })
  const [roles, setRoles] = useState<Rol[]>(usuario.roles)
  const [mensaje, setMensaje] = useState<Mensaje>(null)
  const [temporal, setTemporal] = useState<string | null>(null)
  const botonTemporal = useRef<HTMLButtonElement>(null)
  // Activar y Desactivar se reemplazan entre sí: el botón pulsado se desmonta y el foco pasa al nuevo.
  const botonEstado = useRef<HTMLButtonElement>(null)
  const enfocarEstado = useRef(false)
  useEffect(() => {
    if (!enfocarEstado.current) return
    enfocarEstado.current = false
    botonEstado.current?.focus()
  }, [usuario.activo])
  // El formulario parte de los datos cargados; tras guardar ya coincide con lo que guardó el servidor.

  function actualizarCache(siguiente: UsuarioAdmin) {
    cliente.setQueryData(["usuario", usuario.id], siguiente)
    void cliente.invalidateQueries({ queryKey: ["usuarios"] })
    void cliente.invalidateQueries({ queryKey: ["actividad", usuario.id] })
  }
  function falla(error: Error) {
    setMensaje({ tipo: "error", texto: error.message })
  }

  const guardar = useMutation({
    mutationFn: (cambios: object) =>
      pedir<UsuarioAdmin>(ruta, token, enviarJson("PATCH", cambios)),
    onSuccess: (siguiente) => {
      actualizarCache(siguiente)
      setMensaje({ tipo: "exito", texto: "Cambios guardados." })
    },
    onError: (error) => {
      if (Object.keys(erroresPorCampo(error)).length === 0) falla(error)
    },
  })
  const errores = erroresPorCampo(guardar.error)

  const accion = useMutation({
    mutationFn: ({ sufijo, cuerpo }: { sufijo: string; cuerpo?: object }) =>
      pedir<UsuarioAdmin | ResultadoContrasena | undefined>(
        `${ruta}/${sufijo}`,
        token,
        enviarJson("POST", cuerpo)
      ),
    onError: falla,
  })

  function enviarCambios(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    setMensaje(null)
    const cambios: Record<string, unknown> = {}
    for (const campo of ["nombre", "apellidos", "correo"] as const) {
      if (datos[campo].trim() !== usuario[campo])
        cambios[campo] = datos[campo].trim()
    }
    if (roles.join() !== usuario.roles.join()) cambios.roles = roles
    if (Object.keys(cambios).length === 0) {
      setMensaje({ tipo: "exito", texto: "No hay cambios que guardar." })
      return
    }
    guardar.mutate(cambios)
  }

  function ejecutar(sufijo: string, exito: string, cuerpo?: object) {
    setMensaje(null)
    accion.mutate(
      { sufijo, cuerpo },
      {
        onSuccess: (resultado) => {
          if (resultado && "contrasena_temporal" in resultado) {
            if (resultado.contrasena_temporal)
              setTemporal(resultado.contrasena_temporal)
            else setMensaje({ tipo: "exito", texto: exito })
          } else {
            if (resultado) {
              if (resultado.activo !== usuario.activo)
                enfocarEstado.current = true
              actualizarCache(resultado)
            }
            setMensaje({ tipo: "exito", texto: exito })
          }
          void cliente.invalidateQueries({
            queryKey: ["actividad", usuario.id],
          })
        },
      }
    )
  }

  return (
    <section className="space-y-6">
      <Link
        to="/sistema/usuarios"
        className="inline-flex items-center gap-1 text-sm text-accent hover:underline"
      >
        <ArrowLeft aria-hidden className="size-4" />
        Usuarios
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <Iniciales nombre={nombre} tamano="lg" />
        <div className="min-w-0 space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">{nombre}</h1>
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span className="font-mono">{usuario.usuario}</span>
            <EtiquetaEstado activo={usuario.activo} />
            {usuario.roles.map((r) => (
              <Badge key={r} variant="secondary">
                {NOMBRES_ROL[r]}
              </Badge>
            ))}
            <span>
              Último acceso:{" "}
              {usuario.ultimo_acceso ? (
                <time
                  dateTime={usuario.ultimo_acceso}
                  title={formatoFechaHora(usuario.ultimo_acceso)}
                >
                  {haceCuanto(usuario.ultimo_acceso)}
                </time>
              ) : (
                "nunca"
              )}
            </span>
          </div>
        </div>
      </div>

      <div aria-live="polite">
        {mensaje && (
          <Alert variant={mensaje.tipo === "error" ? "destructive" : "default"}>
            {mensaje.tipo === "error" ? (
              <CircleAlert aria-hidden />
            ) : (
              <CircleCheck aria-hidden />
            )}
            <AlertTitle>
              {mensaje.tipo === "error" ? "No se aplicó el cambio" : "Listo"}
            </AlertTitle>
            <AlertDescription>{mensaje.texto}</AlertDescription>
          </Alert>
        )}
      </div>

      <Seccion titulo="Datos y roles">
        <form
          noValidate
          onSubmit={enviarCambios}
          className="max-w-lg space-y-4"
        >
          {(["nombre", "apellidos", "correo"] as const).map((campo) => (
            <div key={campo} className="grid gap-1.5">
              <Label htmlFor={`${id}-${campo}`}>
                {
                  {
                    nombre: "Nombre",
                    apellidos: "Apellidos",
                    correo: "Correo",
                  }[campo]
                }
              </Label>
              <Input
                id={`${id}-${campo}`}
                type={campo === "correo" ? "email" : "text"}
                value={datos[campo]}
                onChange={(e) =>
                  setDatos((d) => ({ ...d, [campo]: e.target.value }))
                }
                aria-invalid={errores[campo] ? true : undefined}
                aria-describedby={
                  errores[campo] ? `${id}-${campo}-error` : undefined
                }
              />
              {errores[campo] && (
                <p
                  id={`${id}-${campo}-error`}
                  className="text-sm text-destructive"
                >
                  {errores[campo]}
                </p>
              )}
            </div>
          ))}
          <CamposRoles
            valor={roles}
            alCambiar={setRoles}
            error={errores.roles}
          />
          <Button type="submit" disabled={guardar.isPending}>
            {guardar.isPending ? "Guardando…" : "Guardar cambios"}
          </Button>
        </form>
      </Seccion>

      <Seccion
        titulo="Acceso"
        descripcion="Contraseña, sesiones abiertas y estado de la cuenta."
      >
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            disabled={accion.isPending}
            onClick={() =>
              ejecutar(
                "contrasena",
                `Se envió el correo a ${usuario.correo}.`,
                {
                  metodo: "correo",
                }
              )
            }
          >
            <Mail aria-hidden />
            Enviar correo para definir contraseña
          </Button>
          <ConfirmarAccion
            titulo="¿Asignar una contraseña temporal?"
            descripcion="La contraseña actual dejará de funcionar. Verá la nueva una sola vez y la persona deberá cambiarla al entrar."
            textoConfirmar="Asignar"
            alConfirmar={() =>
              ejecutar("contrasena", "", { metodo: "temporal" })
            }
          >
            <Button
              ref={botonTemporal}
              variant="outline"
              disabled={accion.isPending}
            >
              <KeyRound aria-hidden />
              Asignar contraseña temporal
            </Button>
          </ConfirmarAccion>
          <ConfirmarAccion
            titulo="¿Cerrar sus sesiones?"
            descripcion="Se cerrarán todas sus sesiones abiertas; tendrá que volver a iniciar sesión."
            textoConfirmar="Cerrar sesiones"
            alConfirmar={() =>
              ejecutar("cerrar-sesiones", "Se cerraron sus sesiones.")
            }
          >
            <Button variant="outline" disabled={accion.isPending}>
              <LogOut aria-hidden />
              Cerrar sesiones
            </Button>
          </ConfirmarAccion>
          {usuario.activo ? (
            <ConfirmarAccion
              titulo="¿Desactivar la cuenta?"
              descripcion="No podrá iniciar sesión y se cerrarán sus sesiones abiertas. Su historial se conserva y puede reactivarla cuando quiera."
              textoConfirmar="Desactivar la cuenta"
              alConfirmar={() =>
                ejecutar("desactivar", "La cuenta quedó desactivada.")
              }
            >
              <Button
                ref={botonEstado}
                variant="outline"
                disabled={accion.isPending}
              >
                <UserX aria-hidden />
                Desactivar
              </Button>
            </ConfirmarAccion>
          ) : (
            <Button
              ref={botonEstado}
              variant="outline"
              disabled={accion.isPending}
              onClick={() => ejecutar("activar", "La cuenta quedó activa.")}
            >
              <UserCheck aria-hidden />
              Activar
            </Button>
          )}
        </div>
      </Seccion>

      <ActividadReciente usuarioId={usuario.id} />
      <DialogoContrasenaTemporal
        datos={temporal ? { nombre, contrasena: temporal } : null}
        alCerrar={() => setTemporal(null)}
        devolverFoco={botonTemporal}
      />
    </section>
  )
}

/** Últimos 20 registros de la persona; consulta compartida por clave entre la ficha y su sección. */
function useActividad(usuarioId: string) {
  const token = useToken()
  return useQuery({
    queryKey: ["actividad", usuarioId],
    queryFn: () =>
      pedir<PaginaActividad>(
        `/administracion/actividad?${new URLSearchParams({ persona: usuarioId, tamano: "20" })}`,
        token
      ),
    enabled: Boolean(token && usuarioId),
  })
}

function ActividadReciente({ usuarioId }: { usuarioId: string }) {
  const consulta = useActividad(usuarioId)
  let contenido: ReactNode
  if (consulta.isPending) contenido = <EstadoCarga filas={3} />
  else if (consulta.isError)
    contenido = (
      <EstadoError
        error={consulta.error}
        alReintentar={() => void consulta.refetch()}
      />
    )
  else if (consulta.data.elementos.length === 0)
    contenido = (
      <p className="text-sm text-muted-foreground">
        Aún no hay actividad registrada.
      </p>
    )
  else
    contenido = (
      <ul className="divide-y">
        {consulta.data.elementos.map((a) => (
          <li
            key={a.id}
            className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2 text-sm"
          >
            <time
              dateTime={a.fecha}
              className="w-44 shrink-0 text-muted-foreground"
            >
              {formatoFechaHora(a.fecha)}
            </time>
            <span className="min-w-0 flex-1">
              {a.actor_id !== usuarioId && (
                <span className="font-medium">{a.actor_nombre}: </span>
              )}
              {describirActividad(a)}
            </span>
            {a.resultado === "fallo" && (
              <Badge variant="destructive">Falló</Badge>
            )}
          </li>
        ))}
      </ul>
    )
  return (
    <Seccion
      titulo="Actividad reciente"
      descripcion="Lo que hizo esta persona y lo que se hizo con su cuenta (últimos 20 registros)."
    >
      {contenido}
    </Seccion>
  )
}
