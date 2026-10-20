import { TriangleAlert } from "lucide-react"
import { useState } from "react"
import { useParams } from "react-router"
import { useRoles } from "@/auth"
import { ResumenAdjudicacion } from "@/componentes/adjudicacion/ResumenAdjudicacion"
import { SeccionAprobacion } from "@/componentes/adjudicacion/SeccionAprobacion"
import { SeccionEvaluacion } from "@/componentes/adjudicacion/SeccionEvaluacion"
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

/** El aviso de la página: un resultado, o un conflicto con el servicio (la negociación ya cambió). */
type Aviso = { texto: string; tono: "exito" | "conflicto" }
const SIN_AVISO: Aviso = { texto: "", tono: "exito" }

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
  const [aviso, setAviso] = useState(SIN_AVISO)
  const avisar = (texto: string) => setAviso({ texto, tono: "exito" })
  const advertir = (texto: string) => setAviso({ texto, tono: "conflicto" })
  // Al abrir un diálogo o empezar una decisión, el conflicto de antes ya no viene al caso.
  const olvidarConflicto = () =>
    setAviso((actual) => (actual.tono === "conflicto" ? SIN_AVISO : actual))
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
                alAvisar={avisar}
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
                      alCancelar={() => avisar("Se canceló la negociación.")}
                    />
                  </div>
                )}
                {evento.estado === "en_evaluacion" && (
                  <SeccionEvaluacion
                    evento={evento}
                    alAvisar={avisar}
                    alConflicto={advertir}
                    alEmpezar={olvidarConflicto}
                  />
                )}
                {evento.estado === "pendiente_aprobacion" && (
                  <SeccionAprobacion
                    evento={evento}
                    alAvisar={avisar}
                    alConflicto={advertir}
                    alEmpezar={olvidarConflicto}
                  />
                )}
                {(evento.estado === "adjudicado" ||
                  evento.estado === "desierto") && (
                  <ResumenAdjudicacion evento={evento} />
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
      <p
        role="status"
        className={
          !aviso.texto
            ? "sr-only"
            : aviso.tono === "conflicto"
              ? "flex items-start gap-2 text-sm text-warning"
              : "text-sm text-success"
        }
      >
        {/* El conflicto lleva un icono además del color. */}
        {aviso.texto && aviso.tono === "conflicto" && (
          <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
        )}
        {aviso.texto}
      </p>
      <DialogoEnlaces
        enlaces={enlaces}
        abridor={abridor}
        alCerrar={() => setEnlaces(null)}
      />
    </div>
  )
}
