import {
  BellOff,
  CalendarClock,
  ChartBar,
  ChartLine,
  HandCoins,
  ListOrdered,
  PiggyBank,
  TriangleAlert,
  Wallet,
} from "lucide-react"
import { useAuth } from "react-oidc-context"
import { Link } from "react-router"
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"
import { useRoles } from "@/auth"
import { BarraPuntuacion } from "@/componentes/BarraPuntuacion"
import { ElementoAlerta } from "@/componentes/ElementoAlerta"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { ContenidoConsulta, EstadoVacio } from "@/componentes/Estados"
import { GuiaUso } from "@/componentes/GuiaUso"
import { Seccion } from "@/componentes/Seccion"
import { TarjetaKpi } from "@/componentes/TarjetaKpi"
import { Termino } from "@/componentes/Termino"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  formatoDecimal,
  formatoPorcentaje,
  montoCorto,
  useInteligencia,
  useUmbralRiesgo,
  type Destacado,
  type TableroDatos,
} from "@/inteligencia"
import {
  NOMBRES_FILTRO_ESTADO,
  rutaRenovacion,
  useNegociacion,
  type EstadoEvento,
  type TableroNegociacion,
} from "@/negociacion"
import {
  NOMBRES_CATEGORIA,
  formatoFecha,
  formatoMoneda,
  formatoPeriodo,
} from "@/tipos"

const CONFIG_MES = {
  monto: { label: "Gasto comprometido", color: "var(--chart-1)" },
} satisfies ChartConfig

function enlace(texto: string, ruta: string) {
  return (
    <Link to={ruta} className="text-sm font-medium text-accent hover:underline">
      {texto}
    </Link>
  )
}

function cuando(dias: number): string {
  if (dias === 0) return "hoy"
  return dias === 1 ? "mañana" : `en ${dias} días`
}

export function Tablero() {
  const auth = useAuth()
  const nombre =
    auth.user?.profile.given_name ?? auth.user?.profile.preferred_username
  const tablero = useInteligencia<TableroDatos>("/tablero")
  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Tablero"
        descripcion={`${nombre ? `Hola, ${nombre}. ` : ""}Esto es lo que gasta en servicios de TI y lo que conviene atender.`}
      />
      <GuiaUso />
      <ContenidoConsulta consulta={tablero}>
        {(datos) => <Contenido datos={datos} />}
      </ContenidoConsulta>
    </section>
  )
}

function Contenido({ datos }: { datos: TableroDatos }) {
  const umbral = useUmbralRiesgo()
  const variacion = datos.variacion_pct
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <TarjetaKpi
          titulo="Gasto anual contratado"
          valor={montoCorto(datos.gasto_anual)}
          detalle="Contratos vigentes, al tipo de cambio más reciente."
          variacion={
            variacion === null
              ? undefined
              : {
                  texto: `${variacion > 0 ? "+" : ""}${formatoPorcentaje(variacion)} contra hace 12 meses`,
                  direccion: variacion < 0 ? "baja" : "sube",
                }
          }
          icono={Wallet}
          enlace="/proveedores?orden=gasto_anual&direccion=desc"
          textoEnlace="Ver proveedores"
        />
        <TarjetaKpi
          titulo="Por vencer (90 días)"
          valor={datos.por_vencer.toLocaleString("es-MX")}
          detalle="Contratos vigentes que terminan en los próximos 90 días."
          icono={CalendarClock}
          enlace="/alertas?tipo=vencimiento"
          textoEnlace="Ver vencimientos"
          tono={datos.por_vencer > 0 ? "advertencia" : "exito"}
        />
        <TarjetaKpi
          titulo="Proveedores en riesgo"
          valor={`${datos.en_riesgo.toLocaleString("es-MX")} de ${datos.total_proveedores.toLocaleString("es-MX")}`}
          detalle={`Puntuación menor que ${umbral} o en caída de más de 10 puntos.`}
          icono={TriangleAlert}
          enlace="/proveedores?en_riesgo=true"
          textoEnlace="Ver proveedores en riesgo"
          tono={datos.en_riesgo > 0 ? "riesgo" : "exito"}
        />
        <TarjetaKpi
          titulo={<Termino clave="ahorroPotencial">Ahorro potencial</Termino>}
          valor={montoCorto(datos.ahorro_potencial)}
          detalle="Si pagara el precio típico en los contratos con sobreprecio."
          icono={PiggyBank}
          enlace="/precios?vista=sobreprecios"
          textoEnlace="Ver sobreprecios"
          tono="exito"
        />
      </div>
      <FilaNegociaciones />
      <div className="grid gap-4 lg:grid-cols-2">
        <Seccion
          titulo="Gasto por categoría"
          descripcion="Gasto anual de los contratos vigentes, en MXN."
        >
          <GastoPorCategoria filas={datos.gasto_por_categoria} />
        </Seccion>
        <Seccion
          titulo="Gasto comprometido por mes"
          descripcion="Valor mensual de los contratos vigentes en cada mes, en MXN."
        >
          <GastoPorMes meses={datos.gasto_por_mes} />
        </Seccion>
        <Seccion
          titulo="Próximos vencimientos"
          acciones={enlace(
            "Ver alertas de vencimiento",
            "/alertas?tipo=vencimiento"
          )}
        >
          <Vencimientos filas={datos.proximos_vencimientos} />
        </Seccion>
        <Seccion
          titulo="Alertas principales"
          acciones={enlace("Ver todas las alertas", "/alertas")}
        >
          {datos.alertas_principales.length === 0 ? (
            <EstadoVacio
              icono={BellOff}
              titulo="No hay alertas activas"
              descripcion={
                <>
                  Aquí verá lo más urgente: vencimientos,{" "}
                  <Termino clave="sobreprecio">sobreprecios</Termino> y
                  proveedores en riesgo.
                </>
              }
            />
          ) : (
            <div className="divide-y">
              {datos.alertas_principales.map((alerta) => (
                <ElementoAlerta key={alerta.id} alerta={alerta} />
              ))}
            </div>
          )}
        </Seccion>
      </div>
      <Seccion
        titulo="Mejores y peores proveedores"
        descripcion={
          <>
            Según su <Termino clave="puntuacion">puntuación</Termino> de 0 a
            100.
          </>
        }
        acciones={enlace("Ver ranking completo", "/ranking")}
      >
        {datos.mejores.length === 0 ? (
          <EstadoVacio
            icono={ListOrdered}
            titulo="Aún no hay puntuaciones"
            descripcion="La puntuación se calcula con el desempeño mensual de cada proveedor; aparecerá cuando se importe."
          />
        ) : (
          <div className="grid gap-6 md:grid-cols-3">
            <ListaDestacados
              titulo="Los 5 mejores"
              filas={datos.mejores}
              umbral={umbral}
            />
            <ListaDestacados
              titulo="Los 5 más bajos"
              filas={datos.peores}
              umbral={umbral}
            />
            <Distribucion filas={datos.distribucion} />
          </div>
        )}
      </Seccion>
    </>
  )
}

const ESTADOS = Object.keys(NOMBRES_FILTRO_ESTADO) as EstadoEvento[]

/** Las negociaciones por estado y el ahorro logrado; carga y falla por su cuenta (spec del Tablero, §4). */
function FilaNegociaciones() {
  const consulta = useNegociacion<TableroNegociacion>("/tablero")
  if (!consulta.isSuccess)
    return (
      <Seccion titulo="Estado de las negociaciones">
        <ContenidoConsulta consulta={consulta}>{() => null}</ContenidoConsulta>
      </Seccion>
    )
  const { por_estado, ahorro } = consulta.data
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <TarjetaKpi
        titulo={<Termino clave="ahorroLogrado">Ahorro logrado</Termino>}
        valor={ahorro.adjudicadas === 0 ? null : montoCorto(ahorro.ahorro_mxn)}
        detalle={detalleAhorro(ahorro)}
        icono={HandCoins}
        enlace="/negociaciones?estado=adjudicado"
        textoEnlace="Ver adjudicadas"
        tono={Number(ahorro.ahorro_mxn) < 0 ? "advertencia" : "exito"}
      />
      <Seccion titulo="Estado de las negociaciones" className="lg:col-span-2">
        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {ESTADOS.map((estado) => (
            <li key={estado}>
              <Link
                to={`/negociaciones?estado=${estado}`}
                className="flex items-baseline justify-between gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted"
              >
                <span>{NOMBRES_FILTRO_ESTADO[estado]}</span>{" "}
                <span className="text-lg font-semibold tabular-nums">
                  {por_estado[estado].toLocaleString("es-MX")}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </Seccion>
    </div>
  )
}

function detalleAhorro({
  adjudicadas,
  ahorro_pct,
}: TableroNegociacion["ahorro"]): string {
  if (adjudicadas === 0) return "Todavía no hay negociaciones adjudicadas."
  const cuantas = `${adjudicadas.toLocaleString("es-MX")} ${adjudicadas === 1 ? "negociación adjudicada" : "negociaciones adjudicadas"}`
  return ahorro_pct === null
    ? `En ${cuantas}.`
    : `${formatoPorcentaje(ahorro_pct)} frente a la primera oferta, en ${cuantas}.`
}

function GastoPorCategoria({
  filas,
}: {
  filas: TableroDatos["gasto_por_categoria"]
}) {
  if (filas.length === 0) {
    return (
      <EstadoVacio
        icono={ChartBar}
        titulo="Sin contratos vigentes"
        descripcion="Cuando haya contratos vigentes verá aquí cuánto gasta al año en cada categoría."
      />
    )
  }
  // Solo para el ancho de cada barra; la cifra que se lee es el texto de la API.
  const mayor = Math.max(...filas.map((f) => Number(f.monto)))
  return (
    <ul className="space-y-3">
      {filas.map((f) => (
        <li key={f.categoria} className="space-y-1">
          <div className="flex justify-between gap-2 text-sm">
            <span>{NOMBRES_CATEGORIA[f.categoria] ?? f.categoria}</span>
            <span className="font-medium tabular-nums">
              {montoCorto(f.monto)}
            </span>
          </div>
          <div aria-hidden className="h-2 rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-chart-1"
              style={{
                width: `${mayor > 0 ? (Number(f.monto) / mayor) * 100 : 0}%`,
              }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}

function GastoPorMes({ meses }: { meses: TableroDatos["gasto_por_mes"] }) {
  if (meses.every((m) => Number(m.monto) === 0)) {
    return (
      <EstadoVacio
        icono={ChartLine}
        titulo="Sin gasto comprometido"
        descripcion="Aquí verá el valor mensual de los contratos de los últimos 24 meses."
      />
    )
  }
  const serie = meses.map((m) => ({
    mes: m.mes,
    monto: Number(m.monto),
    texto: m.monto,
  }))
  return (
    <div className="space-y-3">
      <figure
        aria-label={`Gasto comprometido por mes, de ${formatoPeriodo(meses[0].mes)} a ${formatoPeriodo(meses[meses.length - 1].mes)}`}
      >
        <ChartContainer config={CONFIG_MES} className="aspect-auto h-56 w-full">
          <LineChart
            accessibilityLayer
            data={serie}
            margin={{ left: 8, right: 8, top: 8 }}
          >
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="mes"
              tickFormatter={formatoPeriodo}
              tickLine={false}
              axisLine={false}
              minTickGap={24}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={56}
              tickFormatter={(valor: number) =>
                `${formatoDecimal(valor / 1e6, 1)} M`
              }
            />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  labelFormatter={(valor) => formatoPeriodo(String(valor))}
                  formatter={(_valor, _nombre, item) => (
                    <div className="flex flex-1 items-center justify-between gap-2 leading-none">
                      <span className="text-muted-foreground">Gasto</span>
                      <span className="font-mono font-medium text-foreground tabular-nums">
                        {formatoMoneda(String(item.payload?.texto), "MXN")}
                      </span>
                    </div>
                  )}
                />
              }
            />
            <Line
              dataKey="monto"
              type="monotone"
              stroke="var(--color-monto)"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ChartContainer>
      </figure>
      <details className="text-sm">
        <summary className="cursor-pointer font-medium text-accent">
          Ver los datos
        </summary>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Mes</TableHead>
              <TableHead className="text-right">Monto (MXN)</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {meses.map((m) => (
              <TableRow key={m.mes}>
                <TableCell>{formatoPeriodo(m.mes)}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatoMoneda(m.monto, "MXN")}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </details>
    </div>
  )
}

function Vencimientos({
  filas,
}: {
  filas: TableroDatos["proximos_vencimientos"]
}) {
  const puedeRenovar = useRoles().includes("comprador")
  if (filas.length === 0) {
    return (
      <EstadoVacio
        icono={CalendarClock}
        titulo="Nada vence pronto"
        descripcion="Ningún contrato vigente termina en los próximos 90 días."
      />
    )
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Contrato</TableHead>
          <TableHead>Proveedor</TableHead>
          <TableHead>Vence</TableHead>
          <TableHead className="text-right">Monto mensual (MXN)</TableHead>
          {puedeRenovar && (
            <TableHead>
              <span className="sr-only">Acción</span>
            </TableHead>
          )}
        </TableRow>
      </TableHeader>
      <TableBody>
        {filas.map((v) => (
          <TableRow key={v.contrato_id}>
            <TableCell className="whitespace-normal">
              <div className="font-mono">{v.folio}</div>
              <div className="min-w-40 text-xs text-muted-foreground">
                {v.servicios.join(", ")}
              </div>
            </TableCell>
            <TableCell className="whitespace-normal">
              <Link
                to={`/proveedores/${encodeURIComponent(v.proveedor_id)}?pestana=contratos`}
                className="text-accent hover:underline"
              >
                {v.proveedor}
              </Link>
            </TableCell>
            <TableCell>
              <div>{formatoFecha(v.fecha_fin)}</div>
              <div className="text-xs text-muted-foreground">
                {cuando(v.dias)}
              </div>
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatoMoneda(v.monto_mensual, "MXN")}
            </TableCell>
            {puedeRenovar && (
              <TableCell>
                <Link
                  to={rutaRenovacion(v.proveedor_id, v.contrato_id)}
                  aria-label={`Renovar el contrato ${v.folio}`}
                  className="text-sm font-medium text-accent hover:underline"
                >
                  Renovar
                </Link>
              </TableCell>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function ListaDestacados({
  titulo,
  filas,
  umbral,
}: {
  titulo: string
  filas: Destacado[]
  umbral: number
}) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">{titulo}</h3>
      <ol className="space-y-3">
        {filas.map((d) => (
          <li key={d.proveedor_id} className="space-y-1">
            <Link
              to={`/proveedores/${encodeURIComponent(d.proveedor_id)}`}
              className="text-sm text-accent hover:underline"
            >
              {d.nombre}
            </Link>
            <BarraPuntuacion
              puntuacion={d.puntuacion}
              confianza={null}
              umbral={umbral}
            />
          </li>
        ))}
      </ol>
    </div>
  )
}

function Distribucion({ filas }: { filas: TableroDatos["distribucion"] }) {
  const mayor = Math.max(1, ...filas.map((f) => f.proveedores))
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">
        Proveedores por rango de puntuación
      </h3>
      <ul className="space-y-2">
        {filas.map((f) => (
          <li key={f.rango} className="space-y-1">
            <div className="flex justify-between gap-2 text-sm">
              <span>{f.rango.replace("-", "–")}</span>
              <span className="tabular-nums">
                {f.proveedores.toLocaleString("es-MX")}{" "}
                {f.proveedores === 1 ? "proveedor" : "proveedores"}
              </span>
            </div>
            <div aria-hidden className="h-1.5 rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-chart-1"
                style={{ width: `${(f.proveedores / mayor) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
