import { Info } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

/** Aviso temporal: el Plan B lo elimina al conectar el servicio de inteligencia. */
export function AvisoInteligencia() {
  return (
    <Alert role="note">
      <Info aria-hidden />
      <AlertTitle>Inteligencia en preparación</AlertTitle>
      <AlertDescription>
        Los indicadores, precios de referencia, puntuaciones y alertas se activarán con el servicio de
        inteligencia. Mientras tanto puede consultar proveedores, contratos y desempeño.
      </AlertDescription>
    </Alert>
  )
}
