import { BellOff, Building2, Tags } from "lucide-react"
import { useId } from "react"
import { AvisoInteligencia } from "@/componentes/AvisoInteligencia"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { SiguientePaso } from "@/componentes/SiguientePaso"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { unoDe, useParametros } from "@/parametros"
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

function Filtro({
  etiqueta,
  valor,
  opciones,
  alCambiar,
}: {
  etiqueta: string
  valor: string
  opciones: [string, string][]
  alCambiar: (valor: string) => void
}) {
  const id = useId()
  return (
    <div className="flex items-center gap-2">
      <span id={id} className="text-sm font-medium">
        {etiqueta}
      </span>
      <Select value={valor} onValueChange={alCambiar}>
        <SelectTrigger aria-labelledby={id} className="w-56">
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
  const hayFiltros = Boolean(tipo || severidad)
  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Alertas"
        descripcion="Contratos por vencer, sobreprecios y proveedores en riesgo."
      />
      <AvisoInteligencia />
      <div className="flex flex-wrap gap-4">
        <Filtro
          etiqueta="Tipo"
          valor={tipo ?? TODAS}
          opciones={[
            [TODAS, "Todos los tipos"],
            ...TIPOS.map((t): [string, string] => [t, NOMBRES_TIPO_ALERTA[t]]),
          ]}
          alCambiar={(v) => actualizar({ tipo: v === TODAS ? null : v })}
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
          alCambiar={(v) => actualizar({ severidad: v === TODAS ? null : v })}
        />
      </div>
      <Seccion titulo="Alertas activas">
        <EstadoVacio
          icono={BellOff}
          titulo="No hay alertas activas"
          descripcion="Aquí aparecerán los contratos por vencer en 90, 60 y 30 días, los precios sobre P75 y los proveedores con puntuación baja o en caída."
          accion={
            hayFiltros && (
              <Button
                variant="outline"
                onClick={() => actualizar({ tipo: null, severidad: null })}
              >
                Quitar filtros
              </Button>
            )
          }
        />
      </Seccion>
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
