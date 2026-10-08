import { Building2, Tags, Trophy } from "lucide-react"
import { AvisoInteligencia } from "@/componentes/AvisoInteligencia"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { SiguientePaso } from "@/componentes/SiguientePaso"
import { Termino } from "@/componentes/Termino"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { unoDe, useParametros } from "@/parametros"
import { CATEGORIAS, NOMBRES_CATEGORIA } from "@/tipos"

const TODAS = "todas"
const OPCIONES: [string, string][] = [
  [TODAS, "Todas"],
  ...CATEGORIAS.map((c): [string, string] => [c, NOMBRES_CATEGORIA[c]]),
]

export function Ranking() {
  const [parametros, actualizar] = useParametros()
  const activa = unoDe(parametros.get("categoria"), CATEGORIAS) ?? TODAS
  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Ranking de proveedores"
        descripcion={
          <>
            Los proveedores mejor calificados de cada categoría según su{" "}
            <Termino clave="puntuacion">puntuación</Termino>.
          </>
        }
      />
      <AvisoInteligencia />
      <Tabs
        value={activa}
        onValueChange={(valor) =>
          actualizar({ categoria: valor === TODAS ? null : valor })
        }
      >
        <TabsList className="h-auto flex-wrap">
          {OPCIONES.map(([valor, nombre]) => (
            <TabsTrigger key={valor} value={valor}>
              {nombre}
            </TabsTrigger>
          ))}
        </TabsList>
        {OPCIONES.map(([valor, nombre]) => (
          <TabsContent key={valor} value={valor} className="mt-4">
            <Seccion
              titulo={`Ranking · ${valor === TODAS ? "Todas las categorías" : nombre}`}
            >
              <EstadoVacio
                icono={Trophy}
                titulo="Sin puntuaciones todavía"
                descripcion={
                  <>
                    El ranking ordenará a los proveedores por su{" "}
                    <Termino clave="desempeno">desempeño</Termino>. Los que
                    tengan menos de 6 meses de datos llevarán la etiqueta{" "}
                    <Termino clave="historialCorto">Historial corto</Termino>.
                  </>
                }
              />
            </Seccion>
          </TabsContent>
        ))}
      </Tabs>
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
