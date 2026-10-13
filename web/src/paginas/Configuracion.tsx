import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { FormularioPuntuacion } from "@/componentes/FormularioPuntuacion"
import { PanelModeloPrecios } from "@/componentes/PanelModeloPrecios"
import { RequiereRol } from "@/componentes/RequiereRol"
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
        <div className="grid items-start gap-4 lg:grid-cols-2">
          <FormularioPuntuacion />
          <PanelModeloPrecios />
        </div>
      </section>
    </RequiereRol>
  )
}
