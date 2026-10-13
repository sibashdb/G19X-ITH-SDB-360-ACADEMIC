import { useQuery } from "@tanstack/react-query"
import { Activity, Mail, ShieldAlert, UsersRound } from "lucide-react"
import { Link } from "react-router"
import { pedir } from "@/api"
import { useToken } from "@/auth"
import { ContenidoConsulta, EstadoError } from "@/componentes/Estados"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { IndicadorEstado } from "@/componentes/IndicadorEstado"
import { ListaActividad } from "@/componentes/ListaActividad"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Seccion } from "@/componentes/Seccion"
import { TarjetaKpi, type Tono } from "@/componentes/TarjetaKpi"
import { formatoFechaHora } from "@/fechas"
import {
  fraccionComoPorcentaje,
  useInteligencia,
  type DatosInteligencia,
} from "@/inteligencia"
import { useEstadoSistema, useRegistros } from "@/sistema"
import type { ResumenAdmin } from "@/tipos"

function numero(valor: number | null | undefined): string | null {
  return valor === null || valor === undefined
    ? null
    : valor.toLocaleString("es-MX")
}

function enlace(texto: string, ruta: string) {
  return (
    <Link to={ruta} className="text-sm font-medium text-accent hover:underline">
      {texto}
    </Link>
  )
}

const ENTIDADES: [string, string][] = [
  ["proveedores", "Proveedores"],
  ["servicios", "Servicios"],
  ["contratos", "Contratos"],
  ["lineas_contrato", "Líneas de contrato"],
  ["desempeno", "Registros de desempeño"],
  ["tipo_cambio", "Tipos de cambio"],
]

function textoModelo(d: DatosInteligencia): string {
  const entrenando = d.entrenando ? " Hay un entrenamiento en curso." : ""
  if (d.modelo && d.en_uso === d.modelo.version)
    return `Modelo de precios: versión ${d.en_uso}, MAPE ${fraccionComoPorcentaje(d.modelo.mape)}.${entrenando}`
  if (d.modelo)
    return `Modelo de precios: la versión ${d.modelo.version} no se pudo cargar y se usa la línea base; reentrénelo en Configuración.${entrenando}`
  return `Modelo de precios: línea base (ningún modelo la ha mejorado todavía).${entrenando}`
}

/** Lo que llegó a la inteligencia y el modelo con que trabaja (spec D2: no va en el Tablero). */
function DatosYModelo() {
  const datos = useInteligencia<DatosInteligencia>("/datos")
  return (
    <Seccion
      titulo="Datos y modelo"
      descripcion="Lo que recibió la inteligencia desde el ERP y el modelo de precios con que trabaja."
      acciones={enlace("Ir a Configuración", "/configuracion")}
    >
      <ContenidoConsulta consulta={datos}>
        {(d) => (
          <div className="space-y-3 text-sm">
            <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1">
              {ENTIDADES.map(([clave, nombre]) => (
                <div key={clave} className="contents">
                  <dt className="text-muted-foreground">{nombre}</dt>
                  <dd className="text-right tabular-nums">
                    {(d.registros[clave] ?? 0).toLocaleString("es-MX")}
                  </dd>
                </div>
              ))}
            </dl>
            <p>
              Último dato recibido:{" "}
              {/* formatoFechaHora ya termina en "a.m." o "p.m." */}
              {d.ultimo_evento
                ? formatoFechaHora(d.ultimo_evento)
                : "ninguno todavía."}
            </p>
            <p>{textoModelo(d)}</p>
          </div>
        )}
      </ContenidoConsulta>
    </Seccion>
  )
}

export function Panel() {
  return (
    <RequiereRol rol="admin">
      <ContenidoPanel />
    </RequiereRol>
  )
}

function ContenidoPanel() {
  const token = useToken()
  const resumen = useQuery({
    queryKey: ["resumen-admin"],
    queryFn: () => pedir<ResumenAdmin>("/administracion/resumen", token),
    enabled: Boolean(token),
  })
  const estado = useEstadoSistema()
  const recientes = useRegistros({ tamano: "10" })
  const importaciones = useRegistros({ tipo: "importaciones", tamano: "5" })

  const fallidos = resumen.data?.intentos_fallidos_24h
  const tonoFallidos: Tono =
    fallidos === undefined
      ? "info"
      : fallidos >= 5
        ? "riesgo"
        : fallidos >= 1
          ? "advertencia"
          : "exito"
  const conProblemas =
    estado.data?.servicios.filter((s) => s.estado !== "sano") ?? []
  const tonoServicios: Tono = !estado.data
    ? "info"
    : conProblemas.some((s) => s.estado === "caido")
      ? "riesgo"
      : conProblemas.length > 0
        ? "advertencia"
        : "exito"

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Panel de administración"
        descripcion="Lo importante de la plataforma de un vistazo: quién entra, qué falla y qué se ha hecho."
      />
      {resumen.isError && (
        <EstadoError
          error={resumen.error}
          alReintentar={() => void resumen.refetch()}
        />
      )}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <TarjetaKpi
          titulo="Usuarios activos"
          valor={numero(resumen.data?.usuarios_activos)}
          detalle={
            resumen.data && resumen.data.usuarios_activos === null
              ? "No se pudo consultar el servicio de identidad."
              : undefined
          }
          icono={UsersRound}
          enlace="/sistema/usuarios"
          textoEnlace="Ver usuarios"
        />
        <TarjetaKpi
          titulo="Intentos fallidos (24 h)"
          valor={numero(fallidos)}
          icono={ShieldAlert}
          enlace="/sistema/actividad?tipo=sesiones"
          textoEnlace="Ver inicios de sesión"
          tono={tonoFallidos}
        />
        <TarjetaKpi
          titulo="Servicios con problemas"
          valor={estado.data ? numero(conProblemas.length) : null}
          detalle={conProblemas.map((s) => s.nombre).join(", ") || undefined}
          icono={Activity}
          enlace="/sistema/estado"
          textoEnlace="Ver estado del sistema"
          tono={tonoServicios}
        />
        <TarjetaKpi
          titulo="Correos (7 días)"
          valor={numero(resumen.data?.correos_7d)}
          icono={Mail}
          enlace="/sistema/correos"
          textoEnlace="Ver correos"
        />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Seccion
          titulo="Actividad reciente"
          acciones={enlace("Ver toda la actividad", "/sistema/actividad")}
        >
          <ContenidoConsulta consulta={recientes}>
            {(datos) =>
              datos.elementos.length > 0 ? (
                <ListaActividad elementos={datos.elementos} />
              ) : (
                <p className="text-sm text-muted-foreground">
                  Aún no hay actividad registrada.
                </p>
              )
            }
          </ContenidoConsulta>
        </Seccion>
        <div className="space-y-4">
          <Seccion
            titulo="Estado del sistema"
            acciones={enlace("Ver detalle", "/sistema/estado")}
          >
            <ContenidoConsulta consulta={estado}>
              {(datos) => (
                <ul className="divide-y">
                  {datos.servicios.map((s) => (
                    <li
                      key={s.clave}
                      className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"
                    >
                      <span>{s.nombre}</span>
                      <IndicadorEstado estado={s.estado} />
                    </li>
                  ))}
                </ul>
              )}
            </ContenidoConsulta>
          </Seccion>
          <Seccion
            titulo="Últimas importaciones"
            acciones={enlace("Ir a Importación", "/importacion")}
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
          <DatosYModelo />
        </div>
      </div>
    </section>
  )
}
