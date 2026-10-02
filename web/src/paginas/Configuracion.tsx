import { Database, SlidersHorizontal } from "lucide-react"
import { AvisoInteligencia } from "@/componentes/AvisoInteligencia"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoVacio } from "@/componentes/Estados"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Seccion } from "@/componentes/Seccion"

export function Configuracion() {
  return (
    <RequiereRol rol="admin">
      <section className="space-y-6">
        <EncabezadoPagina
          titulo="Configuración"
          descripcion="Parámetros de la puntuación de proveedores y del modelo de precios."
        />
        <AvisoInteligencia />
        <div className="grid gap-4 lg:grid-cols-2">
          <Seccion titulo="Pesos de la puntuación">
            <EstadoVacio
              icono={SlidersHorizontal}
              titulo="Sin configuración todavía"
              descripcion="Podrá ajustar los pesos de SLA, resolución, incidentes, entregas y satisfacción (deben sumar 100), el umbral de riesgo y la inflación anual."
            />
          </Seccion>
          <Seccion titulo="Modelo de precios">
            <EstadoVacio
              icono={Database}
              titulo="Sin modelos entrenados"
              descripcion="Aquí verá la versión activa del modelo, su error (MAPE) y podrá reentrenarlo."
            />
          </Seccion>
        </div>
      </section>
    </RequiereRol>
  )
}
