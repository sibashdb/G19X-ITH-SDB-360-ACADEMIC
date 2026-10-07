import {
  CalendarClock,
  ChartBar,
  ChartLine,
  Database,
  ListOrdered,
  PiggyBank,
  TriangleAlert,
  type LucideIcon,
  Wallet,
} from "lucide-react"
import { useAuth } from "react-oidc-context"
import { Link } from "react-router"
import { useRoles } from "@/auth"
import { AvisoInteligencia } from "@/componentes/AvisoInteligencia"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { TarjetaKpi, type Tono } from "@/componentes/TarjetaKpi"

const KPIS: {
  clave: string
  titulo: string
  icono: LucideIcon
  enlace: string
  textoEnlace: string
  tono: Tono
}[] = [
  {
    clave: "gasto",
    titulo: "Gasto anual contratado",
    icono: Wallet,
    enlace: "/proveedores",
    textoEnlace: "Ver proveedores",
    tono: "info",
  },
  {
    clave: "vencer",
    titulo: "Por vencer (90 días)",
    icono: CalendarClock,
    enlace: "/alertas?tipo=vencimiento",
    textoEnlace: "Ver vencimientos",
    tono: "advertencia",
  },
  {
    clave: "riesgo",
    titulo: "Proveedores en riesgo",
    icono: TriangleAlert,
    enlace: "/alertas?tipo=riesgo",
    textoEnlace: "Ver riesgos",
    tono: "riesgo",
  },
  {
    clave: "ahorro",
    titulo: "Ahorro potencial",
    icono: PiggyBank,
    enlace: "/precios?vista=sobreprecios",
    textoEnlace: "Ver sobreprecios",
    tono: "exito",
  },
]

export function Tablero() {
  const auth = useAuth()
  const roles = useRoles()
  const nombre =
    auth.user?.profile.given_name ?? auth.user?.profile.preferred_username
  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Tablero"
        descripcion={`${nombre ? `Hola, ${nombre}. ` : ""}Resumen de las compras de servicios de TI.`}
      />
      <AvisoInteligencia />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {KPIS.map(({ clave, ...kpi }) => (
          <TarjetaKpi key={clave} {...kpi} valor={null} />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Seccion titulo="Gasto por categoría">
          <EstadoVacio
            icono={ChartBar}
            titulo="Sin datos todavía"
            descripcion="Aquí verá el gasto anual contratado por categoría de servicio."
          />
        </Seccion>
        <Seccion titulo="Gasto comprometido por mes">
          <EstadoVacio
            icono={ChartLine}
            titulo="Sin datos todavía"
            descripcion="Aquí verá el gasto comprometido de los últimos 24 meses."
          />
        </Seccion>
        <Seccion
          titulo="Próximos vencimientos"
          acciones={
            <Link
              to="/alertas?tipo=vencimiento"
              className="text-sm font-medium text-accent hover:underline"
            >
              Ver alertas de vencimiento
            </Link>
          }
        >
          <EstadoVacio
            icono={CalendarClock}
            titulo="Sin datos todavía"
            descripcion="Aquí verá los contratos que vencen en los próximos 90 días."
          />
        </Seccion>
        <Seccion
          titulo="Alertas principales"
          acciones={
            <Link
              to="/alertas"
              className="text-sm font-medium text-accent hover:underline"
            >
              Ver todas las alertas
            </Link>
          }
        >
          <EstadoVacio
            icono={TriangleAlert}
            titulo="Sin datos todavía"
            descripcion="Aquí verá las alertas más severas: vencimientos, sobreprecios y riesgos."
          />
        </Seccion>
      </div>
      <Seccion
        titulo="Mejores y peores proveedores"
        acciones={
          <Link
            to="/ranking"
            className="text-sm font-medium text-accent hover:underline"
          >
            Ver ranking completo
          </Link>
        }
      >
        <EstadoVacio
          icono={ListOrdered}
          titulo="Sin datos todavía"
          descripcion="Aquí verá los 5 proveedores con mejor y peor puntuación."
        />
      </Seccion>
      {roles.includes("admin") && (
        <Seccion titulo="Estado de los datos">
          <EstadoVacio
            icono={Database}
            titulo="Sin datos todavía"
            descripcion="Aquí verá la fecha de la última importación, los registros por entidad y el modelo de precios activo."
          />
        </Seccion>
      )}
    </section>
  )
}
