import { Award, ClipboardCheck, TriangleAlert } from "lucide-react"
import type { ReactNode } from "react"
import {
  NOMBRES_NIVEL_RIESGO,
  type Candidato,
  type Recomendacion,
} from "@/adjudicacion"
import { Termino } from "@/componentes/Termino"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatoDecimal } from "@/inteligencia"
import type { Evento } from "@/negociacion"
import { formatoMoneda } from "@/tipos"

/** Un componente del riesgo (de 0 a 1) como porcentaje entero: "35 %". */
const porcentaje = (valor: number) => `${Math.round(valor * 100)} %`

/** Los acuerdos tentativos en el orden de la recomendación, con lo que decide cada lugar. */
export function TablaCandidatos({
  recomendacion,
  evento,
  destacada,
  accion,
}: {
  recomendacion: Recomendacion
  evento: Evento
  /** Id de la sesión de la propuesta vigente: su fila lleva «Propuesta». */
  destacada?: string
  /** La celda final de cada fila (p. ej. «Adjudicar»). */
  accion?: (candidato: Candidato) => ReactNode
}) {
  const fueraDeLimites = new Set(
    evento.sesiones.filter((s) => s.fuera_de_limites).map((s) => s.id)
  )
  // El término se define solo en la primera fila que lo lleva: las demás repiten el texto.
  const primeraFueraDeLimites = recomendacion.candidatos.find((c) =>
    fueraDeLimites.has(c.id)
  )?.id
  return (
    <Table aria-label="Candidatos de la evaluación">
      <TableHeader>
        <TableRow>
          <TableHead>Proveedor</TableHead>
          <TableHead className="text-right">Costo total</TableHead>
          <TableHead className="text-right">
            <Termino clave="desempeno">Desempeño</Termino>
          </TableHead>
          <TableHead>Riesgo</TableHead>
          <TableHead className="text-right">
            <Termino clave="sla">SLA</Termino>
          </TableHead>
          <TableHead className="text-right">Puntaje</TableHead>
          <TableHead className="text-right">Lugar</TableHead>
          {accion && (
            <TableHead>
              <span className="sr-only">Acción</span>
            </TableHead>
          )}
        </TableRow>
      </TableHeader>
      <TableBody>
        {recomendacion.candidatos.map((c) => (
          <TableRow
            key={c.id}
            className={c.id === destacada ? "bg-info-suave" : undefined}
          >
            <TableCell className="whitespace-normal">
              <p className="font-medium">{c.nombre}</p>
              {/* bg-card: sobre la fila de la propuesta (bg-info-suave) el verde y el ámbar del
                  texto pequeño bajan de 4.5:1; sobre el fondo de la tarjeta tienen 5.02:1 (claro). */}
              <div className="mt-1 flex flex-wrap gap-1 empty:hidden">
                {c.id === recomendacion.recomendado && (
                  <Badge variant="success" className="bg-card">
                    <Award aria-hidden />
                    Recomendado
                  </Badge>
                )}
                {c.id === destacada && (
                  <Badge variant="secondary">
                    <ClipboardCheck aria-hidden />
                    Propuesta
                  </Badge>
                )}
                {fueraDeLimites.has(c.id) && (
                  <Badge variant="warning" className="bg-card">
                    <TriangleAlert aria-hidden />
                    {c.id === primeraFueraDeLimites ? (
                      <Termino clave="fuera_de_limites" />
                    ) : (
                      "Fuera de límites"
                    )}
                  </Badge>
                )}
              </div>
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatoMoneda(c.costo_total, evento.moneda)}
              {evento.moneda === "USD" && (
                <span className="block text-xs text-muted-foreground">
                  ≈ {formatoMoneda(c.costo_total_mxn, "MXN")}
                </span>
              )}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatoDecimal(c.desempeno, 1)}
            </TableCell>
            <TableCell className="whitespace-normal">
              <details>
                <summary className="w-fit cursor-pointer rounded-sm outline-hidden focus-visible:ring-2 focus-visible:ring-ring">
                  <span className="sr-only">Riesgo</span>{" "}
                  {NOMBRES_NIVEL_RIESGO[c.riesgo.nivel]}
                </summary>
                <ul className="mt-1 text-xs text-muted-foreground">
                  <li>Concentración: {porcentaje(c.riesgo.concentracion)}</li>
                  <li>
                    Tendencia de incidentes: {porcentaje(c.riesgo.tendencia)}
                  </li>
                  <li>Sin historial: {c.riesgo.sin_historial ? "sí" : "no"}</li>
                </ul>
              </details>
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {c.sla === null ? "—" : `${formatoDecimal(Number(c.sla), 2)} %`}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatoDecimal(c.puntaje, 1)}
            </TableCell>
            <TableCell className="text-right tabular-nums">{c.lugar}</TableCell>
            {accion && <TableCell>{accion(c)}</TableCell>}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
