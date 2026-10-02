import {
  CalendarClock,
  ChartBar,
  ChartLine,
  Database,
  ListOrdered,
  PiggyBank,
  TriangleAlert,
  Wallet,
} from "lucide-react"
import { useAuth } from "react-oidc-context"
import { useRoles } from "@/auth"
import { AvisoInteligencia } from "@/componentes/AvisoInteligencia"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { TarjetaKpi } from "@/componentes/TarjetaKpi"

const KPIS = [
  { titulo: "Gasto anual contratado", icono: Wallet, enlace: "/proveedores", textoEnlace: "Ver proveedores" },
  { titulo: "Por vencer (90 días)", icono: CalendarClock, enlace: "/alertas?tipo=vencimiento", textoEnlace: "Ver vencimientos" },
  { titulo: "Proveedores en riesgo", icono: TriangleAlert, enlace: "/alertas?tipo=riesgo", textoEnlace: "Ver riesgos" },
  { titulo: "Ahorro potencial", icono: PiggyBank, enlace: "/precios?vista=sobreprecios", textoEnlace: "Ver sobreprecios" },
]

export function Tablero() {
  const auth = useAuth()
  const roles = useRoles()
  const nombre = auth.user?.profile.given_name ?? auth.user?.profile.preferred_username
  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Tablero"
        descripcion={`${nombre ? `Hola, ${nombre}. ` : ""}Resumen de las compras de servicios de TI.`}
      />
      <AvisoInteligencia />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {KPIS.map((kpi) => (
          <TarjetaKpi key={kpi.titulo} {...kpi} valor={null} />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Seccion titulo="Gasto por categoría">
          <EstadoVacio icono={ChartBar} titulo="Sin datos todavía" descripcion="Aquí verá el gasto anual contratado por categoría de servicio." />
        </Seccion>
        <Seccion titulo="Gasto comprometido por mes">
          <EstadoVacio icono={ChartLine} titulo="Sin datos todavía" descripcion="Aquí verá el gasto comprometido de los últimos 24 meses." />
        </Seccion>
        <Seccion titulo="Próximos vencimientos">
          <EstadoVacio icono={CalendarClock} titulo="Sin datos todavía" descripcion="Aquí verá los contratos que vencen en los próximos 90 días." />
        </Seccion>
        <Seccion titulo="Alertas principales">
          <EstadoVacio icono={TriangleAlert} titulo="Sin datos todavía" descripcion="Aquí verá las alertas más severas: vencimientos, sobreprecios y riesgos." />
        </Seccion>
      </div>
      <Seccion titulo="Mejores y peores proveedores">
        <EstadoVacio icono={ListOrdered} titulo="Sin datos todavía" descripcion="Aquí verá los 5 proveedores con mejor y peor puntuación." />
      </Seccion>
      {roles.includes("admin") && (
        <Seccion titulo="Estado de los datos">
          <EstadoVacio icono={Database} titulo="Sin datos todavía" descripcion="Aquí verá la fecha de la última importación, los registros por entidad y el modelo de precios activo." />
        </Seccion>
      )}
    </section>
  )
}
