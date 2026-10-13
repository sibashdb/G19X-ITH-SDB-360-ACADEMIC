import { CircleAlert, RefreshCw } from "lucide-react"
import { useEffect } from "react"
import { useRouteError } from "react-router"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

/**
 * Frontera de error de las páginas: si el archivo de una página no se descarga (pestaña vieja
 * después de una actualización, red caída), el menú y la barra superior se quedan y aquí se ofrece
 * recargar. El error técnico solo va a la consola.
 */
export function ErrorDePagina() {
  const error = useRouteError()
  useEffect(() => {
    console.error("No se pudo cargar la página:", error)
  }, [error])

  return (
    <Alert variant="destructive">
      <CircleAlert aria-hidden />
      <AlertTitle>No se pudo cargar esta página</AlertTitle>
      <AlertDescription>
        <p>
          Puede que haya una versión nueva de la plataforma o que se haya
          perdido la conexión.
        </p>
        <Button
          variant="outline"
          size="sm"
          className="mt-2"
          onClick={() => window.location.reload()}
        >
          <RefreshCw aria-hidden />
          Recargar la página
        </Button>
      </AlertDescription>
    </Alert>
  )
}
