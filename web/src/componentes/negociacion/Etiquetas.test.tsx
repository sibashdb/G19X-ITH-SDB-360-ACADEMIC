import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import { EtiquetaEstadoEvento } from "@/componentes/negociacion/Etiquetas"
import { NOMBRES_ESTADO_EVENTO, type EstadoEvento } from "@/negociacion"

afterEach(cleanup)

// Los que el servidor puede enviar: services/negociacion/src/negociacion/modelos.py::ESTADOS_EVENTO.
// Si se agrega un estado allá, agréguelo aquí y en negociacion.ts y Etiquetas.tsx.
const DEL_SERVIDOR: [EstadoEvento, string][] = [
  ["borrador", "Borrador"],
  ["abierto", "Abierta"],
  ["en_evaluacion", "En evaluación"],
  ["pendiente_aprobacion", "Pendiente de aprobación"],
  ["adjudicado", "Adjudicada"],
  ["desierto", "Desierta"],
  ["cancelado", "Cancelada"],
]

describe("EtiquetaEstadoEvento", () => {
  it("conoce exactamente los estados que envía el servidor", () => {
    expect(Object.keys(NOMBRES_ESTADO_EVENTO).sort()).toEqual(
      DEL_SERVIDOR.map(([estado]) => estado).sort()
    )
  })

  it.each(DEL_SERVIDOR)("muestra el estado %s como «%s»", (estado, nombre) => {
    render(<EtiquetaEstadoEvento estado={estado} />)
    expect(screen.getByText(nombre)).toBeInTheDocument()
  })
})
