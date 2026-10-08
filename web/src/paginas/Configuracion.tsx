import { Database, SlidersHorizontal } from "lucide-react"
import { AvisoInteligencia } from "@/componentes/AvisoInteligencia"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoVacio } from "@/componentes/Estados"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Seccion } from "@/componentes/Seccion"
import { Termino } from "@/componentes/Termino"

export function Configuracion() {
  return (
    <RequiereRol rol="admin">
      <section className="space-y-6">
        <EncabezadoPagina
          titulo="Configuración"
          descripcion={
            <>
              Ajuste cómo se califica a los proveedores y cómo se calcula el{" "}
              <Termino clave="precioReferencia">precio de referencia</Termino>.
            </>
          }
        />
        <AvisoInteligencia />
        <div className="grid gap-4 lg:grid-cols-2">
          <Seccion titulo="Pesos de la puntuación">
            <EstadoVacio
              icono={SlidersHorizontal}
              titulo="Sin configuración todavía"
              descripcion={
                <>
                  Podrá decidir cuánto pesa cada aspecto del{" "}
                  <Termino clave="desempeno">desempeño</Termino> (deben sumar
                  100), desde qué <Termino clave="puntuacion">puntuación</Termino>{" "}
                  un proveedor está en riesgo y la inflación anual.
                </>
              }
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
