import { useAuth } from "react-oidc-context"
import { NOMBRES_ROL, useRoles } from "@/auth"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function Inicio() {
  const auth = useAuth()
  const roles = useRoles()
  const nombre = auth.user?.profile.given_name ?? auth.user?.profile.preferred_username
  return (
    <Card>
      <CardHeader>
        <CardTitle>Hola, {nombre}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted-foreground">Tus roles:</span>
        {roles.map((rol) => (
          <Badge key={rol}>{NOMBRES_ROL[rol]}</Badge>
        ))}
      </CardContent>
    </Card>
  )
}
