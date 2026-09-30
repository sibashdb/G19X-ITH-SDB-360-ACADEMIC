import { useState, type FormEvent } from "react"
import { Link } from "react-router"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { pedir } from "@/api"
import { useToken } from "@/auth"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { NOMBRES_CATEGORIA, NOMBRES_TAMANO, type Categoria, type PaginaProveedores } from "@/tipos"

const POR_PAGINA = 25

export function Proveedores() {
  const token = useToken()
  const [texto, setTexto] = useState("")
  const [q, setQ] = useState("")
  const [categoria, setCategoria] = useState<Categoria | "">("")
  const [pagina, setPagina] = useState(0)

  const consulta = useQuery({
    queryKey: ["proveedores", { q, categoria, pagina }],
    queryFn: () => {
      const parametros = new URLSearchParams({
        limite: String(POR_PAGINA),
        desplazamiento: String(pagina * POR_PAGINA),
      })
      if (q) parametros.set("q", q)
      if (categoria) parametros.set("categoria", categoria)
      return pedir<PaginaProveedores>(`/proveedores/proveedores?${parametros}`, token)
    },
    enabled: Boolean(token),
    placeholderData: keepPreviousData,
  })

  function buscar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    setPagina(0)
    setQ(texto.trim())
  }

  const total = consulta.data?.total ?? 0
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA))

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Proveedores</h1>
      <form role="search" onSubmit={buscar} className="flex flex-wrap items-center gap-2">
        <label htmlFor="busqueda" className="sr-only">
          Buscar por nombre o RFC
        </label>
        <Input
          id="busqueda"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="Nombre o RFC"
          maxLength={100}
          className="max-w-xs"
        />
        <label htmlFor="categoria" className="sr-only">
          Categoría
        </label>
        <select
          id="categoria"
          value={categoria}
          onChange={(e) => {
            setPagina(0)
            setCategoria(e.target.value as Categoria | "")
          }}
          className="h-9 rounded-md border bg-background px-2 text-sm"
        >
          <option value="">Todas las categorías</option>
          {(Object.keys(NOMBRES_CATEGORIA) as Categoria[]).map((c) => (
            <option key={c} value={c}>
              {NOMBRES_CATEGORIA[c]}
            </option>
          ))}
        </select>
        <Button type="submit">Buscar</Button>
      </form>

      {consulta.isError && (
        <p role="alert" className="text-destructive">
          {consulta.error.message}
        </p>
      )}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Nombre</TableHead>
            <TableHead>RFC</TableHead>
            <TableHead>Tamaño</TableHead>
            <TableHead>Categorías</TableHead>
            <TableHead>Estado</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {consulta.data?.elementos.map((p) => (
            <TableRow key={p.id}>
              <TableCell>
                <Link to={`/proveedores/${p.id}`} className="font-medium hover:underline">
                  {p.nombre}
                </Link>
              </TableCell>
              <TableCell className="font-mono text-sm">{p.rfc}</TableCell>
              <TableCell>{NOMBRES_TAMANO[p.tamano] ?? p.tamano}</TableCell>
              <TableCell className="space-x-1">
                {p.categorias.map((c) => (
                  <Badge key={c} variant="secondary">
                    {NOMBRES_CATEGORIA[c]}
                  </Badge>
                ))}
              </TableCell>
              <TableCell>{p.activo ? "Activo" : "Inactivo"}</TableCell>
            </TableRow>
          ))}
          {consulta.data?.elementos.length === 0 && (
            <TableRow>
              <TableCell colSpan={5} className="text-center text-muted-foreground">
                Sin resultados
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      <div className="flex items-center justify-between text-sm">
        <span>
          {total} proveedores · página {pagina + 1} de {paginas}
        </span>
        <div className="space-x-2">
          <Button
            variant="outline"
            size="sm"
            disabled={pagina === 0}
            onClick={() => setPagina((n) => n - 1)}
          >
            Anterior
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={pagina + 1 >= paginas}
            onClick={() => setPagina((n) => n + 1)}
          >
            Siguiente
          </Button>
        </div>
      </div>
    </section>
  )
}
