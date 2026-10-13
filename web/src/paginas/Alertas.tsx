import { keepPreviousData } from "@tanstack/react-query"
import { BellOff, Building2, Tags, X } from "lucide-react"
import { useId, useRef, type Ref } from "react"
import { ElementoAlerta } from "@/componentes/ElementoAlerta"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Paginacion } from "@/componentes/Paginacion"
import { Seccion } from "@/componentes/Seccion"
import { SiguientePaso } from "@/componentes/SiguientePaso"
import { Termino } from "@/componentes/Termino"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useInteligencia, type PaginaAlertas } from "@/inteligencia"
import { enteroPositivo, unoDe, useParametros } from "@/parametros"
import {
  NOMBRES_SEVERIDAD,
  NOMBRES_TIPO_ALERTA,
  type Severidad,
  type TipoAlerta,
} from "@/tipos"

// Radix Select no admite el valor vacío: "todas" representa "sin filtro".
const TODAS = "todas"
const TIPOS = Object.keys(NOMBRES_TIPO_ALERTA) as TipoAlerta[]
const SEVERIDADES = Object.keys(NOMBRES_SEVERIDAD) as Severidad[]
const POR_PAGINA = 25
const PAGINA_MAXIMA = 10_000 // la que acepta la API
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function Filtro({
  etiqueta,
  valor,
  opciones,
  alCambiar,
  refDisparador,
}: {
  etiqueta: string
  valor: string
  opciones: [string, string][]
  alCambiar: (valor: string) => void
  refDisparador?: Ref<HTMLButtonElement>
}) {
  const id = useId()
  return (
    <div className="flex items-center gap-2">
      <span id={id} className="text-sm font-medium">
        {etiqueta}
      </span>
      <Select value={valor} onValueChange={alCambiar}>
        <SelectTrigger
          ref={refDisparador}
          aria-labelledby={id}
          className="w-56"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {opciones.map(([v, nombre]) => (
            <SelectItem key={v} value={v}>
              {nombre}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

export function Alertas() {
  const [parametros, actualizar] = useParametros()
  const tipo = unoDe(parametros.get("tipo"), TIPOS)
  const severidad = unoDe(parametros.get("severidad"), SEVERIDADES)
  const crudo = parametros.get("proveedor")
  const proveedor = crudo && UUID.test(crudo) ? crudo : null
  const pagina = enteroPositivo(parametros.get("pagina"), 1, PAGINA_MAXIMA)
  const hayFiltros = Boolean(tipo || severidad || proveedor)
  const refTipo = useRef<HTMLButtonElement>(null)

  const busqueda = new URLSearchParams({
    pagina: String(pagina),
    limite: String(POR_PAGINA),
  })
  if (tipo) busqueda.set("tipo", tipo)
  if (severidad) busqueda.set("severidad", severidad)
  if (proveedor) busqueda.set("proveedor", proveedor)
  const consulta = useInteligencia<PaginaAlertas>(`/alertas?${busqueda}`, {
    placeholderData: keepPreviousData,
  })
  const nombreProveedor = consulta.data?.elementos[0]?.proveedor_nombre

  // El botón usado desaparece: el foco pasa al filtro de tipo, que sigue en pantalla.
  function quitarFiltros() {
    actualizar({ tipo: null, severidad: null, proveedor: null, pagina: null })
    refTipo.current?.focus()
  }
  function irALaPrimera() {
    actualizar({ pagina: null })
    refTipo.current?.focus()
  }

  function contenido() {
    if (consulta.isPending) return <EstadoCarga />
    if (consulta.isError) {
      return (
        <EstadoError
          error={consulta.error}
          alReintentar={() => void consulta.refetch()}
        />
      )
    }
    const { total, elementos } = consulta.data
    if (elementos.length === 0) {
      if (pagina > 1 && total > 0) {
        return (
          <EstadoVacio
            titulo="Esta página no tiene resultados"
            descripcion={`Hay ${total.toLocaleString("es-MX")} alertas ${
              hayFiltros ? "que coinciden con los filtros" : "activas"
            }.`}
            accion={
              <Button variant="outline" onClick={irALaPrimera}>
                Ir a la primera página
              </Button>
            }
          />
        )
      }
      if (hayFiltros) {
        return (
          <EstadoVacio
            icono={BellOff}
            titulo="Ninguna alerta coincide con los filtros"
            descripcion="Pruebe con otros filtros o use «Quitar filtros»."
          />
        )
      }
      return (
        <EstadoVacio
          icono={BellOff}
          titulo="No hay alertas activas"
          descripcion={
            <>
              Aquí aparecerán los contratos que vencen en 90, 60 y 30 días, los
              precios con <Termino clave="sobreprecio">sobreprecio</Termino> y
              los proveedores con{" "}
              <Termino clave="puntuacion">puntuación</Termino> baja o en caída.
            </>
          }
        />
      )
    }
    return (
      <div className="space-y-4">
        <div className="divide-y">
          {elementos.map((alerta) => (
            <ElementoAlerta key={alerta.id} alerta={alerta} />
          ))}
        </div>
        <Paginacion
          pagina={pagina}
          total={total}
          porPagina={POR_PAGINA}
          nombre="alertas"
          alCambiar={(p) => actualizar({ pagina: String(p) })}
        />
      </div>
    )
  }

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Alertas"
        descripcion={
          <>
            Lo que conviene atender hoy: contratos por vencer, precios altos y
            proveedores que bajan su{" "}
            <Termino clave="desempeno">desempeño</Termino>.
          </>
        }
      />
      <div className="flex flex-wrap items-center gap-4">
        <Filtro
          etiqueta="Tipo"
          valor={tipo ?? TODAS}
          refDisparador={refTipo}
          opciones={[
            [TODAS, "Todos los tipos"],
            ...TIPOS.map((t): [string, string] => [t, NOMBRES_TIPO_ALERTA[t]]),
          ]}
          alCambiar={(v) =>
            actualizar({ tipo: v === TODAS ? null : v, pagina: null })
          }
        />
        <Filtro
          etiqueta="Severidad"
          valor={severidad ?? TODAS}
          opciones={[
            [TODAS, "Todas las severidades"],
            ...SEVERIDADES.map((s): [string, string] => [
              s,
              NOMBRES_SEVERIDAD[s],
            ]),
          ]}
          alCambiar={(v) =>
            actualizar({ severidad: v === TODAS ? null : v, pagina: null })
          }
        />
        {proveedor && (
          <Badge variant="outline">
            Proveedor: {nombreProveedor ?? "el elegido"}
          </Badge>
        )}
        {hayFiltros && (
          <Button variant="outline" onClick={quitarFiltros}>
            <X aria-hidden />
            Quitar filtros
          </Button>
        )}
      </div>
      <Seccion titulo="Alertas activas">{contenido()}</Seccion>
      <SiguientePaso
        enlaces={[
          {
            titulo: "Ver proveedores",
            descripcion: "Revise quién le vende y sus contratos.",
            ruta: "/proveedores",
            icono: Building2,
          },
          {
            titulo: "Revisar precios",
            descripcion: "Compare lo que paga con el mercado.",
            ruta: "/precios",
            icono: Tags,
          },
        ]}
      />
    </section>
  )
}
