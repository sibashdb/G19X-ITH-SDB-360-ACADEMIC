import { Link } from "react-router"

export function NoEncontrado() {
  return (
    <section className="space-y-2">
      <h1 className="text-2xl font-semibold">Página no encontrada</h1>
      <Link to="/" className="underline">
        Volver al inicio
      </Link>
    </section>
  )
}
