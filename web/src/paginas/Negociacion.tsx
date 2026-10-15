import { useState } from "react"
import { useParams } from "react-router"
import { useRoles } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { ContenidoConsulta } from "@/componentes/Estados"
import { DialogoEnlaces } from "@/componentes/negociacion/DialogoEnlaces"
import { EditorBorrador } from "@/componentes/negociacion/EditorBorrador"
import { EtiquetaEstadoEvento } from "@/componentes/negociacion/Etiquetas"
import { ResumenConfiguracion } from "@/componentes/negociacion/ResumenConfiguracion"
import {
  NOMBRES_TIPO,
  useNegociacion,
  type EnlaceInvitacion,
  type Evento,
} from "@/negociacion"

export function Negociacion() {
  const { id = "" } = useParams()
  const esComprador = useRoles().includes("comprador")
  const consulta = useNegociacion<Evento>(`/eventos/${encodeURIComponent(id)}`)
  const [aviso, setAviso] = useState("")
  // Los enlaces viven aquí y no en el editor: al publicar, el editor se desmonta.
  const [enlaces, setEnlaces] = useState<EnlaceInvitacion[] | null>(null)

  return (
    <div className="space-y-6">
      <ContenidoConsulta consulta={consulta}>
        {(evento) => (
          <>
            <EncabezadoPagina
              titulo={evento.titulo}
              descripcion={
                <span className="inline-flex flex-wrap items-center gap-2">
                  <span className="font-mono">{evento.folio}</span>
                  <span>· {NOMBRES_TIPO[evento.tipo]}</span>
                  <EtiquetaEstadoEvento estado={evento.estado} />
                </span>
              }
            />
            {evento.estado === "borrador" && esComprador ? (
              <EditorBorrador
                key={evento.version}
                evento={evento}
                alAvisar={setAviso}
                alPublicar={setEnlaces}
              />
            ) : (
              <ResumenConfiguracion evento={evento} />
            )}
          </>
        )}
      </ContenidoConsulta>
      <p role="status" className={aviso ? "text-sm text-success" : "sr-only"}>
        {aviso}
      </p>
      <DialogoEnlaces enlaces={enlaces} alCerrar={() => setEnlaces(null)} />
    </div>
  )
}
