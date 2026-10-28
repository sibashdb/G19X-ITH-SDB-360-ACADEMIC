// Capturas del manual de usuario (docs/manuales/manual-de-usuario.md): sigue el recorrido de
// demostración de docs/MVP.md con los usuarios de desarrollo y guarda cada pantalla en
// docs/manuales/img/. Con el stack levantado: cd web && npx playwright test capturas-manual
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test, type Browser, type Locator, type Page } from '@playwright/test'

const IMAGENES = new URL('../../docs/manuales/img/', import.meta.url)
const REALM = new URL('../../infra/keycloak/realm-plataforma.json', import.meta.url)

type Realm = { users: { username: string; credentials?: { value: string }[] }[] }

/** La contraseña de desarrollo del realm; nunca se escribe en el código ni en una captura. */
function contrasena(usuario: string): string {
  const realm = JSON.parse(readFileSync(REALM, 'utf8')) as Realm
  const valor = realm.users.find((u) => u.username === usuario)?.credentials?.[0]?.value
  if (!valor) throw new Error(`El realm no trae la contraseña de ${usuario}`)
  return valor
}

async function capturar(page: Page, nombre: string, ocultar: Locator[] = []): Promise<void> {
  await page.screenshot({
    path: fileURLToPath(new URL(`${nombre}.jpg`, IMAGENES)),
    type: 'jpeg',
    quality: 80,
    mask: ocultar,
  })
}

async function entrar(browser: Browser, usuario: string): Promise<Page> {
  const page = await (await browser.newContext()).newPage()
  await page.goto('/')
  await page.getByLabel('Usuario o correo electrónico').fill(usuario)
  await page.locator('#password').fill(contrasena(usuario))
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()
  await expect(page.getByRole('heading', { name: 'Tablero', level: 1 })).toBeVisible()
  return page
}

/** La fecha límite en el formato del campo datetime-local, en hora de la Ciudad de México. */
function enDias(dias: number): string {
  const fecha = new Date(Date.now() + dias * 86_400_000)
  const partes = new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'America/Mexico_City',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(fecha)
  return `${partes}T18:00`
}

test('capturas del manual de usuario', async ({ browser }) => {
  // Comprador: Tablero, proveedores, precios y una negociación nueva.
  const comprador = await entrar(browser, 'comprador1')
  await capturar(comprador, 'comprador-tablero')
  await comprador.goto('/proveedores')
  await expect(comprador.getByRole('heading', { name: 'Proveedores', level: 1 })).toBeVisible()
  await capturar(comprador, 'comprador-proveedores')
  await comprador.goto('/precios')
  await expect(comprador.getByRole('heading', { name: 'Precios', level: 1 })).toBeVisible()
  await capturar(comprador, 'comprador-precios')

  await comprador.goto('/negociaciones/nueva')
  await comprador.getByLabel('Título').fill('Desarrollo del portal de clientes')
  await comprador.getByLabel('Fecha límite').fill(enDias(3))
  await comprador.getByRole('combobox', { name: 'Servicio 1' }).click()
  await comprador.getByRole('option', { name: 'Desarrollador(a) senior (MXN)' }).click()
  await comprador.getByLabel('Cantidad 1').fill('800')
  await comprador.getByRole('checkbox', { name: 'Código del Pacífico S.A. de C.V.' }).click()
  await capturar(comprador, 'comprador-nueva-negociacion')
  await comprador.getByRole('button', { name: 'Crear borrador' }).click()
  await expect(comprador.getByText('Borrador', { exact: true })).toBeVisible()
  await capturar(comprador, 'comprador-limites')
  const negociacion = comprador.url()

  await comprador.getByRole('button', { name: 'Publicar' }).click()
  await comprador.getByRole('alertdialog').getByRole('button', { name: 'Publicar' }).click()
  const enlace = comprador.getByText(/\/portal#t=/)
  await expect(enlace).toBeVisible()
  const url = (await enlace.textContent())?.match(/https?:\/\/\S+\/portal#t=[\w-]+/)?.[0]
  if (!url) throw new Error('El diálogo no mostró el enlace de la invitación')
  await capturar(comprador, 'comprador-enlace', [enlace])
  await comprador.getByRole('button', { name: 'Listo' }).click()

  // Proveedor: el portal, el mensaje al agente, la contraoferta y el acuerdo.
  const proveedor = await (await browser.newContext()).newPage()
  await proveedor.goto(url)
  await expect(proveedor.getByRole('heading', { name: 'Desarrollo del portal de clientes' })).toBeVisible()
  await capturar(proveedor, 'proveedor-portal')
  await proveedor.getByLabel('Mensaje para el agente').fill('Podemos dejar la hora en $1,500.00 MXN.')
  await capturar(proveedor, 'proveedor-escribir')
  await proveedor.getByLabel('Mensaje para el agente').fill('')
  await proveedor.getByLabel('Precio de Desarrollador(a) senior').fill('1500')
  await proveedor.getByRole('button', { name: 'Enviar oferta' }).click()
  await expect(proveedor.getByRole('button', { name: 'Aceptar esta propuesta' })).toBeVisible()
  await capturar(proveedor, 'proveedor-contraoferta')
  await proveedor.getByRole('button', { name: 'Aceptar esta propuesta' }).click()
  await proveedor.getByRole('button', { name: 'Enviar oferta' }).click()
  await expect(proveedor.getByText(/terminó con un acuerdo tentativo/)).toBeVisible()
  await capturar(proveedor, 'proveedor-acuerdo')

  // Comprador: la conversación, la evaluación y la adjudicación, que va a un aprobador.
  await comprador.goto(negociacion)
  await expect(async () => {
    await comprador.reload()
    await expect(comprador.getByText('En evaluación', { exact: true }).first()).toBeVisible()
  }).toPass({ timeout: 30_000 })
  await comprador.getByRole('link', { name: 'Código del Pacífico S.A. de C.V.' }).first().click()
  await expect(comprador.getByText('¿Por qué respondió esto?').first()).toBeVisible()
  await capturar(comprador, 'comprador-sesion')
  await comprador.goto(negociacion)
  await expect(comprador.getByText('Por qué se recomienda')).toBeVisible()
  await capturar(comprador, 'comprador-evaluacion')
  await comprador.getByRole('button', { name: /^Adjudicar/ }).first().click()
  const confirmar = comprador.getByRole('button', { name: 'Confirmar' })
  await expect(confirmar).toBeVisible()
  await capturar(comprador, 'comprador-adjudicar')
  await confirmar.click()
  await expect(comprador.getByText('Pendiente de aprobación', { exact: true }).first()).toBeVisible()

  // Aprobador: lo que espera su aprobación, la propuesta y el resultado.
  const aprobador = await entrar(browser, 'aprobador1')
  await capturar(aprobador, 'aprobador-tablero')
  await aprobador.goto(negociacion)
  await expect(aprobador.getByRole('button', { name: 'Aprobar' })).toBeVisible()
  await capturar(aprobador, 'aprobador-propuesta')
  await aprobador.getByRole('button', { name: 'Aprobar' }).click()
  await expect(aprobador.getByText('Adjudicada', { exact: true }).first()).toBeVisible()
  await capturar(aprobador, 'aprobador-resultado')

  // Administrador: el área Sistema.
  const admin = await entrar(browser, 'admin1')
  const pantallas: [string, string, string][] = [
    ['/sistema', 'Panel de administración', 'admin-panel'],
    ['/sistema/usuarios', 'Usuarios', 'admin-usuarios'],
    ['/sistema/correos', 'Correos', 'admin-correos'],
    ['/sistema/actividad', 'Actividad', 'admin-actividad'],
    ['/sistema/catalogo', 'Catálogo', 'admin-catalogo'],
    ['/importacion', 'Importar datos del ERP', 'admin-importacion'],
    ['/configuracion', 'Configuración', 'admin-configuracion'],
    ['/sistema/estado', 'Estado del sistema', 'admin-estado'],
  ]
  for (const [ruta, titulo, nombre] of pantallas) {
    await admin.goto(ruta)
    await expect(admin.getByRole('heading', { name: titulo, level: 1 })).toBeVisible()
    await admin.waitForLoadState('networkidle')
    await capturar(admin, nombre)
  }
})
