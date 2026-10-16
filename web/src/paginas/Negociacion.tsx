import { useState } from "react"
import { useParams } from "react-router"
import { useRoles } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { ContenidoVivo } from "@/componentes/negociacion/ContenidoVivo"
import { DialogoCancelar } from "@/componentes/negociacion/DialogoCancelar"
import { DialogoEnlaces } from "@/componentes/negociacion/DialogoEnlaces"
import { EditorBorrador } from "@/componentes/negociacion/EditorBorrador"
import { EtiquetaEstadoEvento } from "@/componentes/negociacion/Etiquetas"
import { ResumenConfiguracion } from "@/componentes/negociacion/ResumenConfiguracion"
import { TablaSesiones } from "@/componentes/negociacion/TablaSesiones"
import {
  NOMBRES_TIPO,
  useNegociacion,
  type EnlaceInvitacion,
  type Evento,
} from "@/negociacion"

export function Negociacion() {
  const { id = "" } = useParams()
  const esComprador = useRoles().includes("comprador")
  const consulta = useNegociacion<Evento>(
    `/eventos/${encodeURIComponent(id)}`,
    {
      // Supervisión en vivo (spec D6): solo mientras la negociación está abierta.
      refetchInterval: (q) =>
        q.state.data?.estado === "abierto" ? 3000 : false,
    }
  )
  const [aviso, setAviso] = useState("")
  // Los enlaces viven aquí y no en el editor: al publicar, el editor se desmonta.
  const [enlaces, setEnlaces] = useState<EnlaceInvitacion[] | null>(null)
  const [abridor, setAbridor] = useState<HTMLElement | null>(null)

  return (
    <div className="space-y-6">
      <ContenidoVivo consulta={consulta}>
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
                alPublicar={(nuevos) => {
                  setAbridor(null)
                  setEnlaces(nuevos)
                }}
              />
            ) : (
              <>
                {esComprador && evento.estado === "abierto" && (
                  <div className="flex justify-end">
                    <DialogoCancelar
                      ruta={`/negociacion/eventos/${encodeURIComponent(evento.id)}`}
                      borrador={false}
                      alCancelar={() => setAviso("Se canceló la negociación.")}
                    />
                  </div>
                )}
                {evento.estado !== "borrador" && (
                  <TablaSesiones
                    evento={evento}
                    esComprador={esComprador}
                    alReenviar={(enlace, boton) => {
                      setAbridor(boton)
                      setEnlaces([enlace])
                    }}
                  />
                )}
                <ResumenConfiguracion evento={evento} />
              </>
            )}
          </>
        )}
      </ContenidoVivo>
      <p role="status" className={aviso ? "text-sm text-success" : "sr-only"}>
        {aviso}
      </p>
      <DialogoEnlaces
        enlaces={enlaces}
        abridor={abridor}
        alCerrar={() => setEnlaces(null)}
      />
    </div>
  )
}
