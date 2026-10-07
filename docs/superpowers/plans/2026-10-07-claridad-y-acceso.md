# Claridad y acceso: Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que la plataforma se entienda a simple vista y se use sin fricción. Para eso: login de pantalla dividida que explica el producto, acceso sin OTP, guía de pasos y menú que se explica solo, glosario de términos, estilo visual refinado y una "siguiente acción" en cada pantalla.

**Architecture:**
- **Keycloak:** el tema `plataforma` pasa de "solo CSS" a sobrescribir su plantilla base (`template.ftl`) para agregar un panel con el propósito del producto. Los textos van en un archivo de mensajes en español.
- **SPA:** agrega componentes pequeños y enfocados (`Termino`, `GuiaUso`, `SiguientePaso`, `Iniciales`), un almacén de la guía en `localStorage` con `useSyncExternalStore`, y tokens de tinte probados por contraste.
- **API:** no cambia.

**Tech Stack:**
- **Web:** React 19 + TypeScript + Vite 8, Tailwind v4, shadcn 4.21 (`radix-nova`, se agrega `popover`), react-router 8, TanStack Query 5, react-oidc-context, Vitest 5 + Testing Library + axe-core.
- **Identidad:** Keycloak 26.5.7 (FreeMarker, PatternFly 5).

**Spec:** `docs/superpowers/specs/2026-10-07-claridad-y-acceso-design.md`.

## Global Constraints

- Paleta y tipografía sin cambios; los componentes solo usan tokens (el lint prohíbe colores literales en `web/src/paginas` y `web/src/componentes`).
- Tokens de tinte nuevos, claro / oscuro:
  - `info-suave` `#E0F2FE` / `#0C2A44`
  - `exito-suave` `#DCFCE7` / `#0F2E1F`
  - `advertencia-suave` `#FEF3C7` / `#3A2A0B`
  - `riesgo-suave` `#FEE2E2` / `#3B1515`
- Los tintes deben dar ≥ 3:1 contra el icono que los usa (≥ 4.5:1 si es texto), en ambos temas, con prueba automática. Si un valor no cumple, se ajusta el tinte, no la regla.
- "El color nunca es la única señal": los estados llevan texto o icono más texto.
- Interfaz en español (México) y **de usted** de forma consistente: oraciones cortas, sin jerga.
- Lema del producto, exacto: "Pague el precio justo y elija a los mejores proveedores".
- Sin OTP para ningún usuario. Se conservan la protección contra fuerza bruta y la política de contraseñas de Keycloak.
- Los planes y bitácoras anteriores en `docs/superpowers/plans/` y `docs/qa/bitacora-*` no se editan: son registro histórico.
- Dependencias nuevas permitidas: solo `npx shadcn@4.21.0 add popover` (Radix). Ninguna otra.
- La API de `proveedores` no cambia.
- 0 violaciones de axe por página en ambos temas. Usable a 375, 768, 1024 y 1440 px sin scroll horizontal de página.
- Pruebas con Vitest + Testing Library; la salida de las pruebas debe quedar limpia.
- Commits Conventional Commits en español. Formato del mensaje: asunto, una línea en blanco y `Co-Authored-By: <modelo real> <noreply@anthropic.com>`.
- Nunca `git push`. No versionar `infra/.env`, `datos/`, `web/node_modules`, `web/dist`, `.superpowers/` ni archivos PDF. Nunca escribir contraseñas en comandos, archivos versionados ni reportes.

## Review Focus

1. **Almacenamiento del navegador bloqueado o corrupto** (`localStorage` que lanza excepción o guarda `"{"`). La guía debe mostrarse con los pasos 2 y 3 sin marcar y la aplicación no debe romperse. Pruebas en la Tarea 6.
2. **Proveedor sin categorías.** "Compararlo en el ranking" debe llevar a `/ranking`, nunca a `/ranking?categoria=undefined`. Prueba en la Tarea 7.
3. **Realm ya importado, con OTP pendiente o ya configurado.** El script debe dejar a `admin1` y `aprobador1` sin OTP y poder correrse dos veces sin error. Verificación en la Tarea 1.
4. **Ayuda de término usada solo con teclado.** Enter la abre; Escape la cierra y devuelve el foco al término. Prueba en la Tarea 4.
5. **Menú con descripciones y lectores de pantalla.** El nombre accesible de cada enlace sigue siendo solo el título y la descripción llega como descripción accesible. Si no, las pruebas y la navegación por voz se rompen. Pruebas en la Tarea 5.

## Entorno (Windows, Git Bash)

Todo se ejecuta desde la raíz del worktree. Antes de cualquier comando de Docker o uv:

```bash
export PATH="/c/Users/sebas/AppData/Local/Microsoft/WinGet/Links:/c/Program Files/Docker/Docker/resources/bin:$PATH"
export UV_PYTHON="C:/Users/sebas/AppData/Roaming/uv/python/cpython-3.13.15-windows-x86_64-none/python.exe"
export MSYS_NO_PATHCONV=1
```

- **Frontend:** los comandos van en un subshell, p. ej. `(cd web && npx vitest run src/x.test.tsx)`.
- **Stack:** proyecto de Docker Compose `plataforma`, en `infra/docker-compose.yml`; el gateway queda en <http://localhost:8080>. La carpeta `infra/keycloak` se monta en el contenedor `keycloak` como `/opt/keycloak/data/import` (solo lectura). La importación del realm solo lee archivos `.json`.

## Estructura de archivos

```
infra/
  keycloak/realm-plataforma.json        sin requiredActions CONFIGURE_TOTP
  keycloak/quitar-otp.sh                retira el OTP en un realm ya importado (nuevo)
  keycloak/themes/plataforma/login/
    theme.properties                    comentario actualizado
    template.ftl                        plantilla base con el panel (nuevo, parte de keycloak.v2 26.5.7)
    messages/messages_es.properties     textos del panel (nuevo)
    resources/css/plataforma.css        diseño de pantalla dividida (reemplazo)
  smoke_test.py                         token sin OTP para admin1 y aprobador1; lema en el login
README.md                               sin OTP; cómo quitarlo en un realm ya importado; Interfaz
web/src/
  index.css                             tokens de tinte
  tokens.node.test.ts                   pares de los tintes
  glosario.ts                           definiciones de términos (nuevo)
  guia.ts · guia.test.ts                almacén de la guía (nuevo)
  componentes/
    TarjetaKpi.tsx · TarjetaKpi.test.tsx    tono, variación, título ReactNode
    Estados.tsx                         icono de estado vacío en círculo; descripcion ReactNode
    EncabezadoPagina.tsx · Seccion.tsx  descripcion ReactNode
    Termino.tsx · Termino.test.tsx      ayuda de término (nuevo)
    navegacion.ts · navegacion.test.ts  descripcion por elemento
    BarraLateral.tsx                    descripción visible y en ayuda emergente
    BarraSuperior.tsx                   "Mostrar guía de uso" en el menú de usuario
    Layout.tsx · Layout.test.tsx        marca visitas para la guía
    GuiaUso.tsx · GuiaUso.test.tsx      guía "Cómo usar PluriOne" (nuevo)
    SiguientePaso.tsx · SiguientePaso.test.tsx  (nuevo)
    Iniciales.tsx · Iniciales.test.tsx  círculo con iniciales (nuevo)
  components/ui/popover.tsx             shadcn (nuevo)
  paginas/                              Tablero, Proveedores, ProveedorDetalle, Precios, Ranking,
                                        Alertas, Importacion, Configuracion (+ sus pruebas)
docs/qa/revision-claridad-y-acceso.md   revisión en navegador (Tarea 9)
```

---

### Task 1: Acceso sin OTP

**Files:**
- Modify: `infra/keycloak/realm-plataforma.json` (usuarios `admin1` y `aprobador1`)
- Create: `infra/keycloak/quitar-otp.sh`
- Modify: `infra/smoke_test.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: nada.
- Produces:
  - comando de un solo paso, `docker compose -f infra/docker-compose.yml exec -T keycloak bash /opt/keycloak/data/import/quitar-otp.sh`;
  - la prueba de humo exige un token por *password grant* para `admin1` y `aprobador1`.

- [ ] **Step 1: Agregar la verificación sin OTP a la prueba de humo (falla)**

En `infra/smoke_test.py`, dentro de `main()`, justo después de la línea `cabeceras = {"Authorization": f"Bearer {token.json()['access_token']}"}`, agregue:

```python
        # Sin OTP: admin y aprobador obtienen token solo con usuario y contraseña.
        for usuario in ("admin1", "aprobador1"):
            respuesta = cliente.post(
                "/auth/realms/plataforma/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "client_id": "pruebas-humo",
                    "username": usuario,
                    "password": contrasena_de_desarrollo(usuario),
                },
            )
            verificar(
                respuesta.status_code == 200,
                f"{usuario} no obtuvo token solo con contraseña (¿OTP pendiente?): {respuesta.text}",
            )
```

Run: `uv run python infra/smoke_test.py`
Expected: `FALLA: admin1 no obtuvo token solo con contraseña (¿OTP pendiente?): …`. El realm importado todavía tiene la acción "Configure OTP" o una credencial OTP. Si pasara, es que el residente ya quitó el OTP a mano; anótelo en el reporte y siga.

- [ ] **Step 2: Quitar el OTP del realm de desarrollo**

En `infra/keycloak/realm-plataforma.json`, en los usuarios `admin1` y `aprobador1`, borre la línea `"requiredActions": ["CONFIGURE_TOTP"]` y la coma que la precede (en `"realmRoles": ["admin"],` y `"realmRoles": ["aprobador"],`), para que el JSON siga siendo válido.

Run: `"$UV_PYTHON" -c "import json; json.load(open('infra/keycloak/realm-plataforma.json', encoding='utf-8')); print('JSON válido')"` → Expected: `JSON válido`.
Run: `grep -c CONFIGURE_TOTP infra/keycloak/realm-plataforma.json` → Expected: `0`.

- [ ] **Step 3: Crear `infra/keycloak/quitar-otp.sh`**

Keycloak no reimporta un realm existente. Este script retira la acción pendiente y las credenciales OTP del realm ya importado. Se puede correr las veces que se quiera.

```bash
#!/usr/bin/env bash
# Quita el OTP de los usuarios de desarrollo en un realm ya importado (Keycloak no reimporta).
# Uso (desde la raíz del repositorio):
#   docker compose -f infra/docker-compose.yml exec -T keycloak bash /opt/keycloak/data/import/quitar-otp.sh
# La contraseña del administrador se lee del entorno del propio contenedor; no se escribe en ningún lado.
set -euo pipefail

kcadm=/opt/keycloak/bin/kcadm.sh
config=/tmp/kcadm.config

"$kcadm" config credentials --config "$config" --server http://localhost:8080/auth \
  --realm master --user admin --password "$KC_BOOTSTRAP_ADMIN_PASSWORD"

for usuario in admin1 aprobador1; do
  id=$("$kcadm" get users --config "$config" -r plataforma -q exact=true -q "username=$usuario" \
    --fields id --format csv --noquotes)
  if [ -z "$id" ]; then
    echo "No existe $usuario; se omite."
    continue
  fi
  "$kcadm" update "users/$id" --config "$config" -r plataforma -s 'requiredActions=[]'
  "$kcadm" get "users/$id/credentials" --config "$config" -r plataforma --fields id,type \
    --format csv --noquotes | while IFS=, read -r a b; do
      if [ "$b" = "otp" ]; then credencial=$a
      elif [ "$a" = "otp" ]; then credencial=$b
      else continue
      fi
      "$kcadm" delete "users/$id/credentials/$credencial" --config "$config" -r plataforma
    done
  echo "OTP retirado de $usuario."
done
```

- [ ] **Step 4: Aplicar el script al realm ya importado**

Run: `docker compose -f infra/docker-compose.yml exec -T keycloak bash /opt/keycloak/data/import/quitar-otp.sh`
Expected: `OTP retirado de admin1.` y `OTP retirado de aprobador1.` (antes, una línea "Logging into …").

Ejecútelo **una segunda vez**: debe terminar igual y sin errores (idempotente).

Si el entorno rechaza el comando, no lo rodee: reporte **BLOCKED** con el comando exacto, y el controlador le pedirá al residente que lo ejecute en su terminal.

- [ ] **Step 5: Verificar con la prueba de humo**

Run: `uv run python infra/smoke_test.py`
Expected: `OK: SPA, Keycloak y proveedores responden (… proveedores).`

- [ ] **Step 6: Actualizar el README**

1. En "Arranque rápido", reemplace:

```markdown
Abrir <http://localhost:8080>. Los usuarios de desarrollo (`admin1`, `comprador1`,
`aprobador1`) y sus contraseñas están en `infra/keycloak/realm-plataforma.json`; admin y
aprobador configuran OTP en su primer inicio de sesión. Verificación automática:
`uv run python infra/smoke_test.py`.
```

por:

```markdown
Abrir <http://localhost:8080>. Los usuarios de desarrollo (`admin1`, `comprador1`,
`aprobador1`) y sus contraseñas están en `infra/keycloak/realm-plataforma.json`; todos entran
con usuario y contraseña. Verificación automática: `uv run python infra/smoke_test.py`.
```

2. Justo antes de `### Notas para Windows (Git Bash)`, agregue esta sección:

````markdown
### Quitar el OTP en un realm ya importado

Las versiones anteriores pedían OTP a `admin1` y `aprobador1`. Si su realm se importó entonces,
quíteselo una sola vez (no borra datos). El comando funciona igual en PowerShell y en Git Bash
(en Git Bash, ejecute antes `export MSYS_NO_PATHCONV=1`):

```bash
docker compose -f infra/docker-compose.yml exec -T keycloak bash /opt/keycloak/data/import/quitar-otp.sh
```

**Sin línea de comandos**: en <http://localhost:8080/auth/admin/>, realm `plataforma` →
*Users* → `admin1` → deje vacío *Required user actions* y, en *Credentials*, borre la de tipo
`otp`; repita con `aprobador1`.
````

3. En "Limitaciones conocidas (Incremento 1)", borre por completo la viñeta que empieza con `- **OTP por usuario, no por rol.**` (sus tres líneas).

Run: `grep -n "OTP" README.md`
Expected: solo las líneas de la sección "Quitar el OTP en un realm ya importado".

- [ ] **Step 7: Commit**

```bash
git add infra/keycloak/realm-plataforma.json infra/keycloak/quitar-otp.sh infra/smoke_test.py README.md
git commit -m "feat(infra): acceso sin OTP y script para quitarlo en un realm ya importado" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 2: Login de pantalla dividida

**Files:**
- Create: `infra/keycloak/themes/plataforma/login/template.ftl`
- Create: `infra/keycloak/themes/plataforma/login/messages/messages_es.properties`
- Modify: `infra/keycloak/themes/plataforma/login/resources/css/plataforma.css` (reemplazo completo)
- Modify: `infra/keycloak/themes/plataforma/login/theme.properties` (comentario)
- Modify: `infra/smoke_test.py`

**Interfaces:**
- Consumes: el tema `plataforma` montado y asignado al realm (Plan A).
- Produces:
  - `<aside class="plataforma-panel">` con la marca, el lema y 4 puntos, junto al formulario de Keycloak;
  - la prueba de humo exige el lema en la página de login.

- [ ] **Step 1: Agregar el lema a la prueba de humo (falla)**

En `infra/smoke_test.py`, reemplace la verificación del tema:

```python
        verificar(
            acceso.status_code == 200 and "login/plataforma/css/plataforma.css" in acceso.text,
            "Keycloak no aplica el tema de inicio de sesión 'plataforma'",
        )
```

por:

```python
        verificar(
            acceso.status_code == 200 and "login/plataforma/css/plataforma.css" in acceso.text,
            "Keycloak no aplica el tema de inicio de sesión 'plataforma'",
        )
        verificar(
            "Pague el precio justo y elija a los mejores proveedores" in acceso.text,
            "el inicio de sesión no muestra el panel con el propósito del producto",
        )
```

Run: `uv run python infra/smoke_test.py` → Expected: `FALLA: el inicio de sesión no muestra el panel con el propósito del producto`.

- [ ] **Step 2: Extraer la plantilla base de Keycloak 26.5.7**

En un directorio temporal **fuera del repositorio** (su scratchpad), copie el jar de temas del contenedor:

Run: `docker cp plataforma-keycloak-1:/opt/keycloak/lib/lib/main/org.keycloak.keycloak-themes-26.5.7.jar <dir-temporal>/themes.jar`

Cree `<dir-temporal>/extraer.py`:

```python
import sys
import zipfile
from pathlib import Path

jar, destino = Path(sys.argv[1]), Path(sys.argv[2])
destino.parent.mkdir(parents=True, exist_ok=True)
destino.write_bytes(zipfile.ZipFile(jar).read("theme/keycloak.v2/login/template.ftl"))
print(destino, destino.stat().st_size)
```

Run: `"$UV_PYTHON" <dir-temporal>/extraer.py <dir-temporal>/themes.jar infra/keycloak/themes/plataforma/login/template.ftl`
Expected: unos 11 152 bytes. No versione el jar.

- [ ] **Step 3: Agregar el panel a `template.ftl`**

En `infra/keycloak/themes/plataforma/login/template.ftl`, haga exactamente dos reemplazos.

Primero, reemplace:

```ftl
<body id="keycloak-bg" class="${properties.kcBodyClass!}" data-page-id="login-${pageId}">
<div class="${properties.kcLogin!}">
  <div class="${properties.kcLoginContainer!}">
    <header id="kc-header" class="pf-v5-c-login__header">
      <div id="kc-header-wrapper"
              class="pf-v5-c-brand">${kcSanitize(msg("loginTitleHtml",(realm.displayNameHtml!'')))?no_esc}</div>
    </header>
    <main class="${properties.kcLoginMain!}">
```

por:

```ftl
<body id="keycloak-bg" class="${properties.kcBodyClass!}" data-page-id="login-${pageId}">
<div class="plataforma-login">
  <aside class="plataforma-panel" aria-labelledby="plataforma-marca">
    <p id="plataforma-marca" class="plataforma-marca">
      <span class="plataforma-logo" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
      </span>
      <span>PluriOne<span class="plataforma-submarca">${msg("plataformaSubmarca")}</span></span>
    </p>
    <p class="plataforma-lema">${msg("plataformaLema")}</p>
    <ul class="plataforma-puntos">
      <#list 1..4 as n>
      <li>
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>
        <span><strong>${msg("plataformaPunto" + n + "Titulo")}</strong> <span class="plataforma-punto-texto">${msg("plataformaPunto" + n + "Texto")}</span></span>
      </li>
      </#list>
    </ul>
  </aside>
<div class="${properties.kcLogin!}">
  <div class="${properties.kcLoginContainer!}">
    <main class="${properties.kcLoginMain!}">
```

Después, al final del archivo, reemplace:

```ftl
    </main>
  </div>
</div>
</body>
```

por:

```ftl
    </main>
  </div>
</div>
</div>
</body>
```

Run: `grep -c "plataforma-panel" infra/keycloak/themes/plataforma/login/template.ftl` → Expected: `1`.
Run: `grep -c "kc-header" infra/keycloak/themes/plataforma/login/template.ftl` → Expected: `0`.

- [ ] **Step 4: Crear los textos `messages/messages_es.properties`**

Use escapes `\uXXXX` para los acentos: funcionan con cualquier codificación de lectura.

```properties
plataformaSubmarca=Negociaci\u00f3n con proveedores de TI
plataformaLema=Pague el precio justo y elija a los mejores proveedores
plataformaPunto1Titulo=Precio de referencia.
plataformaPunto1Texto=Cu\u00e1nto se paga en el mercado por cada servicio.
plataformaPunto2Titulo=Ranking de proveedores.
plataformaPunto2Texto=Qui\u00e9n rinde mejor seg\u00fan su desempe\u00f1o real.
plataformaPunto3Titulo=Alertas.
plataformaPunto3Texto=Contratos por vencer y precios por encima del mercado.
plataformaPunto4Titulo=Negociaci\u00f3n asistida por IA.
plataformaPunto4Texto=Siempre con aprobaci\u00f3n humana.
```

- [ ] **Step 5: Reemplazar `resources/css/plataforma.css`**

```css
/* Tema "plataforma": misma identidad que la SPA (dirección A, corporativa clara).
   Pantalla dividida: panel con el propósito del producto (template.ftl) y el formulario. */

@font-face {
  font-family: "Fira Sans";
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url("../fonts/fira-sans-latin-400-normal.woff2") format("woff2");
}

@font-face {
  font-family: "Fira Sans";
  font-style: normal;
  font-weight: 600;
  font-display: swap;
  src: url("../fonts/fira-sans-latin-600-normal.woff2") format("woff2");
}

/* Mismos valores que los tokens de web/src/index.css. */
:root {
  --plataforma-pagina: #F8FAFC;
  --plataforma-tarjeta: #FFFFFF;
  --plataforma-panel: #0F172A;
  --plataforma-panel-texto: #E2E8F0;
  --plataforma-panel-secundario: #94A3B8;
  --plataforma-panel-icono: #38BDF8;
  --plataforma-logo: #0369A1;
  --plataforma-acento: #0369A1;
  --plataforma-acento-hover: #075985;
  --plataforma-sobre-acento: #FFFFFF;
}

.pf-v5-theme-dark {
  --plataforma-pagina: #0B1220;
  --plataforma-tarjeta: #111A2E;
  --plataforma-acento: #38BDF8;
  --plataforma-acento-hover: #7DD3FC;
  --plataforma-sobre-acento: #0B1220;
}

:root,
.pf-v5-theme-dark {
  --pf-v5-global--FontFamily--text: "Fira Sans", system-ui, sans-serif;
  --pf-v5-global--FontFamily--heading: "Fira Sans", system-ui, sans-serif;
  --pf-v5-global--primary-color--100: var(--plataforma-acento);
  --pf-v5-global--primary-color--200: var(--plataforma-acento-hover);
  --pf-v5-global--link--Color: var(--plataforma-acento);
  --pf-v5-global--link--Color--hover: var(--plataforma-acento-hover);
  --keycloak-card-top-color: var(--plataforma-acento);
}

.login-pf body {
  background: var(--plataforma-pagina);
}

/* Móvil primero: el panel es un encabezado corto sobre el formulario. */
.plataforma-login {
  display: grid;
  min-height: 100vh;
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: auto 1fr;
}

.plataforma-panel {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.75rem;
  padding: 1.5rem;
  background: var(--plataforma-panel);
  color: var(--plataforma-panel-texto);
  font-family: "Fira Sans", system-ui, sans-serif;
}

.pf-v5-theme-dark .plataforma-panel {
  border-bottom: 1px solid #24324A;
}

.plataforma-marca {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1.2;
}

.plataforma-logo {
  display: flex;
  flex: none;
  width: 2.5rem;
  height: 2.5rem;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem;
  background: var(--plataforma-logo);
  color: #FFFFFF;
}

.plataforma-submarca {
  display: block;
  font-size: 0.875rem;
  font-weight: 400;
  color: var(--plataforma-panel-secundario);
}

.plataforma-lema {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1.3;
}

.plataforma-puntos {
  display: none;
  margin: 0;
  padding: 0;
  list-style: none;
}

.plataforma-puntos li {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
}

.plataforma-puntos svg {
  flex: none;
  width: 1.25rem;
  height: 1.25rem;
  margin-top: 0.1rem;
  color: var(--plataforma-panel-icono);
}

.plataforma-punto-texto {
  display: none;
  color: var(--plataforma-panel-secundario);
}

.plataforma-login .pf-v5-c-login {
  display: flex;
  min-height: auto;
  align-items: center;
  justify-content: center;
  padding: 1.5rem 1rem;
  background: transparent;
}

.plataforma-login .pf-v5-c-login__container {
  width: 100%;
  max-width: 28rem;
  grid-template-columns: minmax(0, 1fr);
}

.plataforma-login .pf-v5-c-login__main {
  --pf-v5-c-login__main--BackgroundColor: var(--plataforma-tarjeta);
  border-radius: 12px;
}

/* Tableta: dos columnas; los puntos muestran solo su título. */
@media (min-width: 768px) {
  .plataforma-login {
    grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
    grid-template-rows: 1fr;
  }

  .plataforma-panel {
    gap: 1.5rem;
    padding: 3rem 2.5rem;
  }

  .pf-v5-theme-dark .plataforma-panel {
    border-bottom: 0;
    border-right: 1px solid #24324A;
  }

  .plataforma-lema {
    font-size: 1.5rem;
  }

  .plataforma-puntos {
    display: grid;
    gap: 1rem;
  }
}

/* Escritorio: panel de 45 % y descripción de cada punto. */
@media (min-width: 1024px) {
  .plataforma-login {
    grid-template-columns: minmax(0, 45%) minmax(0, 55%);
  }

  .plataforma-panel {
    padding: 4rem 3.5rem;
  }

  .plataforma-lema {
    font-size: 2rem;
  }

  .plataforma-punto-texto {
    display: inline;
  }
}

/* Botón principal: el texto sobre el acento cumple 4.5:1 en ambos temas. */
.pf-v5-c-button.pf-m-primary {
  --pf-v5-c-button--m-primary--BackgroundColor: var(--plataforma-acento);
  --pf-v5-c-button--m-primary--hover--BackgroundColor: var(--plataforma-acento-hover);
  --pf-v5-c-button--m-primary--focus--BackgroundColor: var(--plataforma-acento-hover);
  --pf-v5-c-button--m-primary--active--BackgroundColor: var(--plataforma-acento-hover);
  --pf-v5-c-button--m-primary--Color: var(--plataforma-sobre-acento);
  --pf-v5-c-button--m-primary--hover--Color: var(--plataforma-sobre-acento);
  --pf-v5-c-button--m-primary--focus--Color: var(--plataforma-sobre-acento);
  --pf-v5-c-button--m-primary--active--Color: var(--plataforma-sobre-acento);
}

/* Foco siempre visible. */
:focus-visible {
  outline: 2px solid var(--plataforma-acento);
  outline-offset: 2px;
}
```

En `theme.properties` cambie el comentario de la primera línea por:
`# Extiende el inicio de sesión v2 de Keycloak: plantilla base con panel (template.ftl) y estilos propios.`
Las demás líneas no cambian.

- [ ] **Step 6: Verificar**

En modo desarrollo Keycloak no guarda los temas en caché, así que los cambios se ven sin reiniciar. Si no aparecen, reinícielo con `docker compose -f infra/docker-compose.yml restart keycloak` y espere con `docker compose -f infra/docker-compose.yml up -d --wait keycloak`.

Run: `uv run python infra/smoke_test.py` → Expected: `OK: …`.
Run: `docker compose -f infra/docker-compose.yml logs --no-color --tail 40 keycloak` → Expected: sin errores de FreeMarker ni de temas.

Si tiene navegador, abra <http://localhost:8080>. Debe ver el panel marino con "PluriOne", el lema y los 4 puntos, y los acentos bien escritos ("Negociación", "Cuánto"). Si no tiene navegador, anótelo: la Tarea 9 lo revisa.

- [ ] **Step 7: Commit**

```bash
git add infra/keycloak/themes/plataforma infra/smoke_test.py
git commit -m "feat(infra): inicio de sesión de pantalla dividida con el propósito del producto" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 3: Tintes, tarjetas de indicador y estados vacíos

**Files:**
- Modify: `web/src/index.css`, `web/src/tokens.node.test.ts`
- Modify: `web/src/componentes/TarjetaKpi.tsx`, `web/src/componentes/Estados.tsx` (solo `EstadoVacio`), `web/src/paginas/Tablero.tsx`
- Test: `web/src/componentes/TarjetaKpi.test.tsx` (nuevo)

**Interfaces:**
- Consumes: tokens existentes (`accent`, `success`, `warning`, `destructive`).
- Produces:
  - clases de Tailwind `bg-info-suave`, `bg-exito-suave`, `bg-advertencia-suave`, `bg-riesgo-suave`;
  - `type Tono = "info" | "exito" | "advertencia" | "riesgo"` exportado desde `@/componentes/TarjetaKpi`;
  - firma `TarjetaKpi({ titulo: ReactNode, valor: string | null, detalle?: string, icono: LucideIcon, enlace: string, textoEnlace: string, tono?: Tono, variacion?: { texto: string; direccion: "sube" | "baja" } })`.

- [ ] **Step 1: Pares de contraste de los tintes (fallan)**

En `web/src/tokens.node.test.ts`, dentro de `const PARES = [ … ]`, justo antes de `par("ring", "background", GRAFICO),`, agregue:

```ts
  // Tintes del estilo refinado: el icono es gráfico (3:1); las iniciales son texto (4.5:1).
  par("accent", "info-suave", TEXTO),
  par("success", "exito-suave", GRAFICO),
  par("warning", "advertencia-suave", GRAFICO),
  par("destructive", "riesgo-suave", GRAFICO),
```

Run: `(cd web && npx vitest run src/tokens.node.test.ts)` → Expected: FAIL, "El token --info-suave debe ser un color #RRGGBB (es undefined)".

- [ ] **Step 2: Agregar los tokens a `web/src/index.css`**

- **`@theme inline`:** después de la línea `--color-destructive-foreground: var(--destructive-foreground);`, agregue:

```css
    --color-info-suave: var(--info-suave);
    --color-exito-suave: var(--exito-suave);
    --color-advertencia-suave: var(--advertencia-suave);
    --color-riesgo-suave: var(--riesgo-suave);
```

- **`:root`:** después de `--destructive-foreground: #FFFFFF;`, agregue:

```css
    --info-suave: #E0F2FE;
    --exito-suave: #DCFCE7;
    --advertencia-suave: #FEF3C7;
    --riesgo-suave: #FEE2E2;
```

- **`.dark`:** después de `--destructive-foreground: #0B1220;`, agregue:

```css
    --info-suave: #0C2A44;
    --exito-suave: #0F2E1F;
    --advertencia-suave: #3A2A0B;
    --riesgo-suave: #3B1515;
```

Run: `(cd web && npx vitest run src/tokens.node.test.ts)` → Expected: PASS (1 + 2 × 37 pruebas).

- [ ] **Step 3: Pruebas de `TarjetaKpi` (fallan)**

Cree `web/src/componentes/TarjetaKpi.test.tsx`:

```tsx
import { cleanup, screen } from "@testing-library/react"
import { Wallet } from "lucide-react"
import { afterEach, describe, expect, it } from "vitest"
import { TarjetaKpi } from "@/componentes/TarjetaKpi"
import { esperarSinViolaciones, renderizarPagina } from "@/pruebas/utilidades"

afterEach(cleanup)

const base = {
  titulo: "Gasto anual contratado",
  icono: Wallet,
  enlace: "/proveedores",
  textoEnlace: "Ver proveedores",
}

describe("TarjetaKpi", () => {
  it("sin valor muestra un guion y 'Sin datos' para lectores de pantalla", () => {
    renderizarPagina(<TarjetaKpi {...base} valor={null} />)
    expect(screen.getByText("Sin datos")).toHaveClass("sr-only")
    expect(screen.getByRole("link", { name: "Ver proveedores" })).toHaveAttribute(
      "href",
      "/proveedores"
    )
  })

  it("pinta el icono con el tinte de su tono y marca con un acento los estados de atención", () => {
    const { container } = renderizarPagina(
      <TarjetaKpi {...base} valor="12" tono="advertencia" />
    )
    expect(container.querySelector('[data-tono="advertencia"]')).toHaveClass(
      "bg-advertencia-suave",
      "text-warning"
    )
    expect(container.querySelector('[data-slot="card"]')).toHaveClass(
      "border-l-warning"
    )
  })

  it("el tono informativo no lleva acento lateral", () => {
    const { container } = renderizarPagina(<TarjetaKpi {...base} valor="12" />)
    expect(container.querySelector('[data-tono="info"]')).toHaveClass(
      "bg-info-suave",
      "text-accent"
    )
    expect(container.querySelector('[data-slot="card"]')).not.toHaveClass(
      "border-l-3"
    )
  })

  it("muestra la variación con texto, no solo con color", () => {
    renderizarPagina(
      <TarjetaKpi
        {...base}
        valor="$48.2 M"
        variacion={{ texto: "3.1 % más que el año anterior", direccion: "sube" }}
      />
    )
    expect(screen.getByText("3.1 % más que el año anterior")).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    const { container } = renderizarPagina(
      <TarjetaKpi
        {...base}
        valor="12"
        tono="riesgo"
        variacion={{ texto: "2 menos que el mes anterior", direccion: "baja" }}
      />
    )
    await esperarSinViolaciones(container)
  })
})
```

Run: `(cd web && npx vitest run src/componentes/TarjetaKpi.test.tsx)` → Expected: FAIL (no existen `tono` ni `variacion`).

- [ ] **Step 4: Reemplazar `web/src/componentes/TarjetaKpi.tsx`**

```tsx
import { ArrowRight, TrendingDown, TrendingUp, type LucideIcon } from "lucide-react"
import type { ReactNode } from "react"
import { Link } from "react-router"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

export type Tono = "info" | "exito" | "advertencia" | "riesgo"

const ESTILO_TONO: Record<Tono, { icono: string; acento: string }> = {
  info: { icono: "bg-info-suave text-accent", acento: "" },
  exito: { icono: "bg-exito-suave text-success", acento: "" },
  advertencia: {
    icono: "bg-advertencia-suave text-warning",
    acento: "border-l-3 border-l-warning",
  },
  riesgo: {
    icono: "bg-riesgo-suave text-destructive",
    acento: "border-l-3 border-l-destructive",
  },
}

export function TarjetaKpi({
  titulo,
  valor,
  detalle,
  icono: Icono,
  enlace,
  textoEnlace,
  tono = "info",
  variacion,
}: {
  titulo: ReactNode
  valor: string | null
  detalle?: string
  icono: LucideIcon
  enlace: string
  textoEnlace: string
  tono?: Tono
  variacion?: { texto: string; direccion: "sube" | "baja" }
}) {
  const estilo = ESTILO_TONO[tono]
  const Tendencia = variacion?.direccion === "baja" ? TrendingDown : TrendingUp
  return (
    <Card size="sm" className={cn(estilo.acento)}>
      <CardContent className="space-y-2">
        <div className="flex items-start justify-between gap-2 text-sm text-muted-foreground">
          <span>{titulo}</span>
          <span
            data-tono={tono}
            className={cn(
              "flex size-8 shrink-0 items-center justify-center rounded-lg",
              estilo.icono
            )}
          >
            <Icono aria-hidden className="size-4" />
          </span>
        </div>
        <p className="text-2xl font-semibold">
          {valor ?? (
            <>
              <span aria-hidden>—</span>
              <span className="sr-only">Sin datos</span>
            </>
          )}
        </p>
        {variacion && (
          <p className="flex items-center gap-1 text-xs text-muted-foreground">
            <Tendencia aria-hidden className="size-3.5" />
            {variacion.texto}
          </p>
        )}
        {detalle && <p className="text-xs text-muted-foreground">{detalle}</p>}
        <Link
          to={enlace}
          className="inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline"
        >
          {textoEnlace}
          <ArrowRight aria-hidden className="size-3.5" />
        </Link>
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 5: Icono del estado vacío en un círculo**

En `web/src/componentes/Estados.tsx`, dentro de `EstadoVacio`, reemplace la línea:

```tsx
      <Icono aria-hidden className="size-8 text-muted-foreground" />
```

por:

```tsx
      <span className="flex size-12 items-center justify-center rounded-full bg-info-suave">
        <Icono aria-hidden className="size-6 text-accent" />
      </span>
```

- [ ] **Step 6: Tonos en el Tablero**

En `web/src/paginas/Tablero.tsx`:
- importe `type Tono` desde `@/componentes/TarjetaKpi`;
- dé a cada objeto de `KPIS` un `clave` único y su `tono`: `gasto` → `info`, `vencer` → `advertencia`, `riesgo` → `riesgo`, `ahorro` → `exito`;
- tipe el arreglo y use `clave` como `key`.

```tsx
const KPIS: {
  clave: string
  titulo: string
  icono: LucideIcon
  enlace: string
  textoEnlace: string
  tono: Tono
}[] = [
  {
    clave: "gasto",
    titulo: "Gasto anual contratado",
    icono: Wallet,
    enlace: "/proveedores",
    textoEnlace: "Ver proveedores",
    tono: "info",
  },
  {
    clave: "vencer",
    titulo: "Por vencer (90 días)",
    icono: CalendarClock,
    enlace: "/alertas?tipo=vencimiento",
    textoEnlace: "Ver vencimientos",
    tono: "advertencia",
  },
  {
    clave: "riesgo",
    titulo: "Proveedores en riesgo",
    icono: TriangleAlert,
    enlace: "/alertas?tipo=riesgo",
    textoEnlace: "Ver riesgos",
    tono: "riesgo",
  },
  {
    clave: "ahorro",
    titulo: "Ahorro potencial",
    icono: PiggyBank,
    enlace: "/precios?vista=sobreprecios",
    textoEnlace: "Ver sobreprecios",
    tono: "exito",
  },
]
```

El render queda así: `{KPIS.map(({ clave, ...kpi }) => <TarjetaKpi key={clave} {...kpi} valor={null} />)}`. Importe `type LucideIcon` desde `lucide-react`.

Agregue la acción "Ver detalle" en el encabezado de las secciones que tienen destino. Use la prop `acciones` de `Seccion` y nombres distintos a los de las tarjetas:

| Sección | Enlace | Destino |
|---|---|---|
| Próximos vencimientos | "Ver alertas de vencimiento" | `/alertas?tipo=vencimiento` |
| Alertas principales | "Ver todas las alertas" | `/alertas` |
| Mejores y peores proveedores | "Ver ranking completo" | `/ranking` |

Cada acción es `<Link to="…" className="text-sm font-medium text-accent hover:underline">…</Link>`; importe `Link` de `react-router`. Agregue esta prueba a `web/src/paginas/Tablero.test.tsx`:

```tsx
  it("las secciones con destino ofrecen ver el detalle", () => {
    renderizarPagina(<Tablero />)
    expect(
      screen.getByRole("link", { name: "Ver alertas de vencimiento" })
    ).toHaveAttribute("href", "/alertas?tipo=vencimiento")
    expect(screen.getByRole("link", { name: "Ver todas las alertas" })).toHaveAttribute(
      "href",
      "/alertas"
    )
    expect(screen.getByRole("link", { name: "Ver ranking completo" })).toHaveAttribute(
      "href",
      "/ranking"
    )
  })
```

- [ ] **Step 7: Verificar y hacer commit**

Run: `(cd web && npx vitest run src/componentes/TarjetaKpi.test.tsx src/tokens.node.test.ts src/paginas/Tablero.test.tsx src/componentes/Base.test.tsx)` → Expected: PASS.
Run: `(cd web && npm run lint && npm run build && npx vitest run)` → Expected: todo en verde y salida limpia.

```bash
git add web/src/index.css web/src/tokens.node.test.ts web/src/componentes/TarjetaKpi.tsx web/src/componentes/TarjetaKpi.test.tsx web/src/componentes/Estados.tsx web/src/paginas/Tablero.tsx web/src/paginas/Tablero.test.tsx
git commit -m "feat(web): tintes de estado, tarjetas de indicador con tono y estados vacíos con icono destacado" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 4: Glosario y ayuda de términos

**Files:**
- Create (shadcn): `web/src/components/ui/popover.tsx`
- Create: `web/src/glosario.ts`, `web/src/componentes/Termino.tsx`, `web/src/componentes/Termino.test.tsx`
- Modify: `web/src/componentes/EncabezadoPagina.tsx`, `web/src/componentes/Seccion.tsx`, `web/src/componentes/Estados.tsx` (tipos de `descripcion`)

**Interfaces:**
- Consumes: nada nuevo.
- Produces:
  - `GLOSARIO: Record<ClaveGlosario, { termino: string; definicion: string }>` y `type ClaveGlosario = "percentiles" | "precioReferencia" | "sobreprecio" | "ahorroPotencial" | "puntuacion" | "sla" | "desempeno" | "historialCorto" | "bajaConfianza"`;
  - `Termino({ clave: ClaveGlosario, children?: ReactNode })`: botón con subrayado punteado que abre la definición; su nombre accesible es el texto visible;
  - `descripcion: ReactNode` en `EncabezadoPagina`, `Seccion` y `EstadoVacio`.

- [ ] **Step 1: Instalar `popover`**

Run: `(cd web && npx shadcn@4.21.0 add popover --yes)`. Después, `git status --short`: restaure con `git checkout -- <archivo>` cualquier archivo existente que el CLI haya modificado, en especial `web/src/index.css`.

Run: `grep -rnE ">Close<|\"Close\"" web/src/components/ui/popover.tsx` → Expected: sin resultados.

- [ ] **Step 2: Pruebas de `Termino` (fallan)**

Cree `web/src/componentes/Termino.test.tsx`:

```tsx
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it } from "vitest"
import { Termino } from "@/componentes/Termino"
import { GLOSARIO } from "@/glosario"
import { esperarSinViolaciones, renderizarPagina } from "@/pruebas/utilidades"

afterEach(cleanup)

describe("Termino", () => {
  it("su nombre accesible es el texto visible y abre la definición con un clic", async () => {
    renderizarPagina(
      <p>
        Pagas <Termino clave="sobreprecio">sobreprecio</Termino> en 2 contratos.
      </p>
    )
    const disparador = screen.getByRole("button", { name: "sobreprecio" })
    await userEvent.click(disparador)

    const ayuda = await screen.findByRole("dialog", { name: "Sobreprecio" })
    expect(ayuda).toHaveTextContent(GLOSARIO.sobreprecio.definicion)
  })

  it("se abre con Enter, se cierra con Escape y devuelve el foco al término", async () => {
    renderizarPagina(<Termino clave="sla" />)
    const disparador = screen.getByRole("button", { name: "SLA" })
    disparador.focus()

    await userEvent.keyboard("{Enter}")
    expect(await screen.findByRole("dialog", { name: "SLA" })).toBeInTheDocument()

    await userEvent.keyboard("{Escape}")
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(disparador).toHaveFocus()
  })

  it("sin texto propio muestra el nombre del término del glosario", () => {
    renderizarPagina(<Termino clave="percentiles" />)
    expect(
      screen.getByRole("button", { name: GLOSARIO.percentiles.termino })
    ).toBeInTheDocument()
  })

  it("todas las definiciones del glosario existen y no están vacías", () => {
    for (const { termino, definicion } of Object.values(GLOSARIO)) {
      expect(termino.length).toBeGreaterThan(0)
      expect(definicion.length).toBeGreaterThan(20)
    }
  })

  it("no tiene violaciones de accesibilidad abierto ni cerrado", async () => {
    const { container } = renderizarPagina(<Termino clave="ahorroPotencial" />)
    await esperarSinViolaciones(container)
    await userEvent.click(screen.getByRole("button", { name: "Ahorro potencial" }))
    await esperarSinViolaciones(document.body)
  })
})
```

Run: `(cd web && npx vitest run src/componentes/Termino.test.tsx)` → Expected: FAIL (no existen `@/componentes/Termino` ni `@/glosario`).

- [ ] **Step 3: Crear `web/src/glosario.ts`**

```ts
/** Definiciones en lenguaje llano de los términos técnicos de la plataforma. */
export const GLOSARIO = {
  percentiles: {
    termino: "P25 · P50 · P75",
    definicion:
      "Precio bajo, típico y alto del mercado: el 25 %, 50 % y 75 % de los contratos comparables cuestan eso o menos.",
  },
  precioReferencia: {
    termino: "Precio de referencia",
    definicion:
      "Lo que se paga normalmente en el mercado por el servicio, la cantidad y el plazo indicados.",
  },
  sobreprecio: {
    termino: "Sobreprecio",
    definicion: "Paga más que el 75 % de los contratos comparables.",
  },
  ahorroPotencial: {
    termino: "Ahorro potencial",
    definicion:
      "Lo que ahorraría al año si pagara el precio típico del mercado (P50).",
  },
  puntuacion: {
    termino: "Puntuación",
    definicion:
      "Calificación de 0 a 100 del desempeño del proveedor en los últimos 12 meses, comparada con su categoría.",
  },
  sla: {
    termino: "SLA",
    definicion:
      "Nivel de servicio comprometido en el contrato, como el porcentaje de disponibilidad.",
  },
  desempeno: {
    termino: "Desempeño",
    definicion:
      "Cumplimiento del SLA, tiempo de resolución, incidentes críticos, entregas a tiempo y satisfacción.",
  },
  historialCorto: {
    termino: "Historial corto",
    definicion:
      "Menos de 6 meses de datos: la puntuación se acerca al promedio de su categoría hasta tener más historia.",
  },
  bajaConfianza: {
    termino: "Baja confianza",
    definicion:
      "Hay pocos contratos comparables (menos de 8): el precio de referencia es una estimación.",
  },
} as const satisfies Record<string, { termino: string; definicion: string }>

export type ClaveGlosario = keyof typeof GLOSARIO
```

- [ ] **Step 4: Crear `web/src/componentes/Termino.tsx`**

```tsx
import { useId, type ReactNode } from "react"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { GLOSARIO, type ClaveGlosario } from "@/glosario"

/** Término técnico con su definición: abre con clic, toque o teclado; Escape la cierra. */
export function Termino({
  clave,
  children,
}: {
  clave: ClaveGlosario
  children?: ReactNode
}) {
  const { termino, definicion } = GLOSARIO[clave]
  const idTitulo = useId()
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="cursor-help rounded-sm underline decoration-dotted underline-offset-4 outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
        >
          {children ?? termino}
        </button>
      </PopoverTrigger>
      <PopoverContent aria-labelledby={idTitulo} className="w-72 space-y-1 text-sm">
        <p id={idTitulo} className="font-medium">
          {termino}
        </p>
        <p className="text-muted-foreground">{definicion}</p>
      </PopoverContent>
    </Popover>
  )
}
```

- [ ] **Step 5: Permitir términos dentro de las descripciones**

Cambie el tipo de la prop `descripcion` de `string` a `ReactNode` en:
- `web/src/componentes/EncabezadoPagina.tsx`: `descripcion?: ReactNode`; importe `type ReactNode` si falta;
- `web/src/componentes/Seccion.tsx`: `descripcion?: ReactNode`;
- `EstadoVacio`, en `web/src/componentes/Estados.tsx`: `descripcion: ReactNode`.

El JSX no cambia: cada uno ya renderiza `{descripcion}` dentro de un `<p>`.

- [ ] **Step 6: Verificar y hacer commit**

Run: `(cd web && npx vitest run src/componentes/Termino.test.tsx)` → Expected: PASS. Si el `PopoverContent` generado no tiene `role="dialog"`, agréguelo en `Termino.tsx` (`role="dialog"`) y anótelo en el reporte.
Run: `(cd web && npm run lint && npm run build && npx vitest run)` → Expected: todo en verde y salida limpia.

```bash
git add web/src/components/ui/popover.tsx web/src/glosario.ts web/src/componentes/Termino.tsx web/src/componentes/Termino.test.tsx web/src/componentes/EncabezadoPagina.tsx web/src/componentes/Seccion.tsx web/src/componentes/Estados.tsx web/package.json web/package-lock.json
git commit -m "feat(web): glosario de términos con ayuda accesible por clic, toque y teclado" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 5: Menú que se explica solo

**Files:**
- Modify: `web/src/componentes/navegacion.ts`, `web/src/componentes/navegacion.test.ts`
- Modify: `web/src/componentes/BarraLateral.tsx`, `web/src/componentes/Layout.test.tsx`

**Interfaces:**
- Consumes: `NAVEGACION`, `navegacionPara`, `estaActiva` (Plan A).
- Produces:
  - `ElementoNavegacion` agrega `descripcion: string`;
  - en el menú, cada enlace tiene como nombre accesible solo el título y la descripción como `aria-describedby`;
  - con el menú colapsado, la ayuda emergente muestra el título y la descripción.

- [ ] **Step 1: Pruebas (fallan)**

En `web/src/componentes/navegacion.test.ts`, agregue al final:

```ts
describe("descripciones del menú", () => {
  it("cada elemento dice para qué sirve", () => {
    const descripciones = Object.fromEntries(
      navegacionPara(["admin"]).flatMap((s) =>
        s.elementos.map((e) => [e.titulo, e.descripcion])
      )
    )
    expect(descripciones).toEqual({
      Tablero: "Resumen del gasto y lo urgente",
      Proveedores: "Quién le vende y cómo rinde",
      Ranking: "Los mejores proveedores por categoría",
      Precios: "Cuánto debería pagar",
      Alertas: "Qué atender hoy",
      Importación: "Cargar datos del ERP",
      Configuración: "Ajustes de puntuación y precios",
    })
  })
})
```

En `web/src/componentes/Layout.test.tsx`, dentro de `describe("Layout con sesión iniciada", …)`, agregue:

```tsx
  it("cada opción del menú lleva su descripción sin cambiar su nombre accesible", () => {
    renderizar()
    const menu = screen.getByRole("navigation", { name: "Principal" })
    const enlace = within(menu).getByRole("link", { name: "Precios" })
    expect(enlace).toHaveAccessibleDescription("Cuánto debería pagar")
    expect(within(menu).getByText("Cuánto debería pagar")).toBeInTheDocument()
  })
```

Run: `(cd web && npx vitest run src/componentes/navegacion.test.ts src/componentes/Layout.test.tsx)` → Expected: FAIL.

- [ ] **Step 2: Agregar `descripcion` a `NAVEGACION`**

En `web/src/componentes/navegacion.ts`:
- agregue `descripcion: string` al tipo `ElementoNavegacion`, justo después de `ruta: string`;
- dé a cada elemento de `NAVEGACION` su `descripcion`, exactamente como en la prueba del Step 1 (Tablero "Resumen del gasto y lo urgente", Proveedores "Quién le vende y cómo rinde", etc.).

- [ ] **Step 3: Mostrar la descripción en `BarraLateral.tsx`**

Extraiga cada opción a un componente `ElementoMenu` dentro del mismo archivo, porque necesita `useId`. Reemplace el bloque `{seccion.elementos.map(({ titulo, ruta, icono: Icono }) => { … })}` por `{seccion.elementos.map((elemento) => (<ElementoMenu key={elemento.ruta} elemento={elemento} activa={estaActiva(elemento.ruta, pathname)} alNavegar={alNavegar} />))}` y agregue, antes de `export function BarraLateral`:

```tsx
function ElementoMenu({
  elemento: { titulo, descripcion, ruta, icono: Icono },
  activa,
  alNavegar,
}: {
  elemento: ElementoNavegacion
  activa: boolean
  alNavegar: () => void
}) {
  const idDescripcion = useId()
  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        asChild
        isActive={activa}
        tooltip={{
          children: (
            <>
              <span className="block font-medium">{titulo}</span>
              <span className="block text-xs">{descripcion}</span>
            </>
          ),
        }}
        className="h-auto items-start py-2 data-[active=true]:bg-sidebar-primary data-[active=true]:text-sidebar-primary-foreground"
      >
        <Link
          to={ruta}
          aria-current={activa ? "page" : undefined}
          aria-describedby={idDescripcion}
          onClick={alNavegar}
        >
          <Icono aria-hidden className="mt-0.5" />
          <span className="grid leading-tight">
            <span>{titulo}</span>
            <span
              id={idDescripcion}
              aria-hidden
              className="text-xs text-sidebar-foreground/70 group-data-[active=true]/menu-button:text-sidebar-primary-foreground/90"
            >
              {descripcion}
            </span>
          </span>
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}
```

Importe `useId` desde `react` y `type ElementoNavegacion` desde `@/componentes/navegacion`. La descripción está oculta para el árbol de accesibilidad (`aria-hidden`), así que no entra al nombre del enlace, y llega como descripción por `aria-describedby`. Con el menú colapsado, el `SidebarMenuButton` generado fuerza `size-8! p-2!`, de modo que `h-auto py-2` no lo agranda.

- [ ] **Step 4: Verificar y hacer commit**

Run: `(cd web && npx vitest run src/componentes/navegacion.test.ts src/componentes/Layout.test.tsx)` → Expected: PASS. Las pruebas existentes que buscan enlaces por nombre ("Proveedores", "Tablero", …) siguen pasando.
Run: `(cd web && npm run lint && npm run build && npx vitest run)` → Expected: todo en verde y salida limpia.

```bash
git add web/src/componentes/navegacion.ts web/src/componentes/navegacion.test.ts web/src/componentes/BarraLateral.tsx web/src/componentes/Layout.test.tsx
git commit -m "feat(web): menú lateral con una línea de propósito en cada opción" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 6: Guía "Cómo usar PluriOne"

**Files:**
- Create: `web/src/guia.ts`, `web/src/guia.test.ts`, `web/src/componentes/GuiaUso.tsx`, `web/src/componentes/GuiaUso.test.tsx`
- Modify: `web/src/componentes/Layout.tsx`, `web/src/componentes/Layout.test.tsx`, `web/src/componentes/BarraSuperior.tsx`
- Modify: `web/src/paginas/Tablero.tsx`, `web/src/paginas/Tablero.test.tsx`

**Interfaces:**
- Consumes: `pedir` (`@/api`), `useToken` y `useRoles` (`@/auth`), `estaActiva` (`@/componentes/navegacion`), `PaginaProveedores` (`@/tipos`).
- Produces:
  - `CLAVE_GUIA = "plataforma-guia"`;
  - `type EstadoGuia = { oculta: boolean; visitas: { proveedores: boolean; precios: boolean } }`;
  - `useGuia(): EstadoGuia`, `marcarVisita(seccion: "proveedores" | "precios"): void`, `ocultarGuia(): void`, `mostrarGuia(): void`;
  - `GuiaUso()`, que no renderiza nada si la guía está oculta.

- [ ] **Step 1: Pruebas del almacén (fallan)**

`web/src/guia.test.ts`:

```ts
import { act, renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { CLAVE_GUIA, marcarVisita, mostrarGuia, ocultarGuia, useGuia } from "@/guia"

afterEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

describe("guía de uso", () => {
  it("empieza visible y sin visitas", () => {
    const { result } = renderHook(() => useGuia())
    expect(result.current).toEqual({
      oculta: false,
      visitas: { proveedores: false, precios: false },
    })
  })

  it("registra visitas y las conserva en localStorage", () => {
    const { result } = renderHook(() => useGuia())
    act(() => marcarVisita("proveedores"))
    expect(result.current.visitas.proveedores).toBe(true)
    expect(JSON.parse(localStorage.getItem(CLAVE_GUIA) ?? "{}").visitas.proveedores).toBe(true)
  })

  it("se oculta y se vuelve a mostrar", () => {
    const { result } = renderHook(() => useGuia())
    act(() => ocultarGuia())
    expect(result.current.oculta).toBe(true)
    act(() => mostrarGuia())
    expect(result.current.oculta).toBe(false)
  })

  it("un valor corrupto cuenta como estado inicial", () => {
    localStorage.setItem(CLAVE_GUIA, "{")
    const { result } = renderHook(() => useGuia())
    expect(result.current).toEqual({
      oculta: false,
      visitas: { proveedores: false, precios: false },
    })
  })

  it("funciona aunque el navegador bloquee localStorage", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    const { result } = renderHook(() => useGuia())
    expect(result.current.oculta).toBe(false)
    expect(() => act(() => marcarVisita("precios"))).not.toThrow()
  })
})
```

Run: `(cd web && npx vitest run src/guia.test.ts)` → Expected: FAIL (no existe `@/guia`).

- [ ] **Step 2: Crear `web/src/guia.ts`**

```ts
import { useSyncExternalStore } from "react"

/** Clave de localStorage con las visitas y la preferencia de la guía de uso. */
export const CLAVE_GUIA = "plataforma-guia"

export type EstadoGuia = {
  oculta: boolean
  visitas: { proveedores: boolean; precios: boolean }
}

const INICIAL: EstadoGuia = {
  oculta: false,
  visitas: { proveedores: false, precios: false },
}

function interpretar(crudo: string | null): EstadoGuia {
  try {
    const valor = JSON.parse(crudo ?? "null")
    return {
      oculta: valor?.oculta === true,
      visitas: {
        proveedores: valor?.visitas?.proveedores === true,
        precios: valor?.visitas?.precios === true,
      },
    }
  } catch {
    return INICIAL
  }
}

// useSyncExternalStore exige devolver el mismo objeto mientras el estado no cambie.
let ultimoCrudo: string | null | undefined
let ultimo: EstadoGuia = INICIAL

function instantanea(): EstadoGuia {
  let crudo: string | null
  try {
    crudo = localStorage.getItem(CLAVE_GUIA)
  } catch {
    return INICIAL
  }
  if (crudo !== ultimoCrudo) {
    ultimoCrudo = crudo
    ultimo = interpretar(crudo)
  }
  return ultimo
}

const oyentes = new Set<() => void>()

function suscribir(oyente: () => void) {
  oyentes.add(oyente)
  window.addEventListener("storage", oyente)
  return () => {
    oyentes.delete(oyente)
    window.removeEventListener("storage", oyente)
  }
}

function guardar(cambiar: (estado: EstadoGuia) => EstadoGuia) {
  try {
    localStorage.setItem(CLAVE_GUIA, JSON.stringify(cambiar(instantanea())))
  } catch {
    // Sin almacenamiento: la guía sigue visible y sin visitas registradas.
  }
  oyentes.forEach((oyente) => oyente())
}

export function marcarVisita(seccion: "proveedores" | "precios"): void {
  if (instantanea().visitas[seccion]) return
  guardar((estado) => ({
    ...estado,
    visitas: { ...estado.visitas, [seccion]: true },
  }))
}

export function ocultarGuia(): void {
  guardar((estado) => ({ ...estado, oculta: true }))
}

export function mostrarGuia(): void {
  guardar((estado) => ({ ...estado, oculta: false }))
}

export function useGuia(): EstadoGuia {
  return useSyncExternalStore(suscribir, instantanea)
}
```

Run: `(cd web && npx vitest run src/guia.test.ts)` → Expected: PASS.

- [ ] **Step 3: Pruebas de `GuiaUso` (fallan)**

`web/src/componentes/GuiaUso.test.tsx`:

```tsx
import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { GuiaUso } from "@/componentes/GuiaUso"
import { CLAVE_GUIA } from "@/guia"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

function conProveedores(total: number) {
  simularApi((url) =>
    url.startsWith("/api/proveedores/proveedores?")
      ? respuestaJson({ total, elementos: [] })
      : new Response("", { status: 404 })
  )
}

const paso = (numero: number) =>
  screen.getAllByRole("listitem")[numero - 1]

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  localStorage.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("GuiaUso", () => {
  it("con datos importados marca el paso 1 y cuenta el avance", async () => {
    conProveedores(60)
    renderizarPagina(<GuiaUso />)

    expect(
      screen.getByRole("heading", { name: "Cómo usar PluriOne" })
    ).toBeInTheDocument()
    expect(await screen.findByText("1 de 3 listos")).toBeInTheDocument()
    expect(paso(1)).toHaveTextContent("Hecho")
    expect(paso(2)).toHaveTextContent("Pendiente")
    expect(within(paso(2)).getByRole("link", { name: "Ver proveedores" })).toHaveAttribute(
      "href",
      "/proveedores"
    )
    expect(paso(4)).toHaveTextContent("Próximamente")
  })

  it("las visitas registradas marcan los pasos 2 y 3", async () => {
    conProveedores(60)
    localStorage.setItem(
      CLAVE_GUIA,
      JSON.stringify({ oculta: false, visitas: { proveedores: true, precios: true } })
    )
    renderizarPagina(<GuiaUso />)
    expect(await screen.findByText("3 de 3 listos")).toBeInTheDocument()
  })

  it("sin datos, el admin ve el enlace a Importación", async () => {
    conProveedores(0)
    renderizarPagina(<GuiaUso />)
    expect(
      await within(paso(1)).findByRole("link", { name: "Ir a Importación" })
    ).toHaveAttribute("href", "/importacion")
  })

  it("sin datos, otros roles leen que Administración importa los datos", async () => {
    sesionDePrueba.roles = ["comprador"]
    conProveedores(0)
    renderizarPagina(<GuiaUso />)
    expect(
      await within(paso(1)).findByText("Administración importa los datos del ERP.")
    ).toBeInTheDocument()
    expect(
      within(paso(1)).queryByRole("link", { name: "Ir a Importación" })
    ).not.toBeInTheDocument()
  })

  it("se oculta con 'Ocultar guía'", async () => {
    conProveedores(60)
    renderizarPagina(<GuiaUso />)
    await userEvent.click(screen.getByRole("button", { name: "Ocultar guía" }))
    expect(
      screen.queryByRole("heading", { name: "Cómo usar PluriOne" })
    ).not.toBeInTheDocument()
    expect(JSON.parse(localStorage.getItem(CLAVE_GUIA) ?? "{}").oculta).toBe(true)
  })

  it("con el almacenamiento bloqueado se muestra con los pasos 2 y 3 pendientes", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    conProveedores(60)
    renderizarPagina(<GuiaUso />)
    expect(await screen.findByText("1 de 3 listos")).toBeInTheDocument()
    expect(paso(2)).toHaveTextContent("Pendiente")
    expect(paso(3)).toHaveTextContent("Pendiente")
  })

  it("no tiene violaciones de accesibilidad", async () => {
    conProveedores(60)
    const { container } = renderizarPagina(<GuiaUso />)
    await screen.findByText("1 de 3 listos")
    await esperarSinViolaciones(container)
  })
})
```

Run: `(cd web && npx vitest run src/componentes/GuiaUso.test.tsx)` → Expected: FAIL.

- [ ] **Step 4: Crear `web/src/componentes/GuiaUso.tsx`**

```tsx
import { useQuery } from "@tanstack/react-query"
import { Check } from "lucide-react"
import { useId, type ReactNode } from "react"
import { Link } from "react-router"
import { pedir } from "@/api"
import { useRoles, useToken } from "@/auth"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ocultarGuia, useGuia } from "@/guia"
import { cn } from "@/lib/utils"
import type { PaginaProveedores } from "@/tipos"

type Paso = {
  titulo: string
  descripcion: string
  estado: "hecho" | "pendiente" | "proximamente"
  accion?: ReactNode
}

const NOMBRE_ESTADO = {
  hecho: "Hecho",
  pendiente: "Pendiente",
  proximamente: "Próximamente",
} as const

function enlace(texto: string, ruta: string) {
  return (
    <Link to={ruta} className="text-sm font-medium text-accent hover:underline">
      {texto}
    </Link>
  )
}

/** Los 4 pasos del flujo de trabajo, con su avance; se puede ocultar. */
export function GuiaUso() {
  const token = useToken()
  const roles = useRoles()
  const guia = useGuia()
  const idTitulo = useId()
  const datos = useQuery({
    queryKey: ["proveedores", "existencia"],
    queryFn: () =>
      pedir<PaginaProveedores>(
        "/proveedores/proveedores?limite=1&desplazamiento=0",
        token
      ),
    enabled: Boolean(token),
  })

  if (guia.oculta) return null

  const hayDatos = (datos.data?.total ?? 0) > 0
  const pasos: Paso[] = [
    {
      titulo: "Importar contratos y proveedores",
      descripcion: "Cargue los datos del ERP: catálogo, proveedores, contratos y desempeño.",
      estado: hayDatos ? "hecho" : "pendiente",
      accion: hayDatos
        ? undefined
        : roles.includes("admin")
          ? enlace("Ir a Importación", "/importacion")
          : <span className="text-sm text-muted-foreground">Administración importa los datos del ERP.</span>,
    },
    {
      titulo: "Conocer a sus proveedores",
      descripcion: "Revise quién le vende, sus contratos y cómo rinde.",
      estado: guia.visitas.proveedores ? "hecho" : "pendiente",
      accion: guia.visitas.proveedores ? undefined : enlace("Ver proveedores", "/proveedores"),
    },
    {
      titulo: "Ver el precio justo",
      descripcion: "Compare lo que paga con el precio de referencia del mercado.",
      estado: guia.visitas.precios ? "hecho" : "pendiente",
      accion: guia.visitas.precios ? undefined : enlace("Ver precios", "/precios"),
    },
    {
      titulo: "Negociar y aprobar",
      descripcion: "La IA negocia dentro de sus límites y usted aprueba el cierre.",
      estado: "proximamente",
    },
  ]
  const listos = pasos.filter((p) => p.estado === "hecho").length

  return (
    <section aria-labelledby={idTitulo} className="space-y-4 rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1">
          <h2 id={idTitulo} className="text-base font-semibold">
            Cómo usar PluriOne
          </h2>
          <p className="text-sm text-muted-foreground">{listos} de 3 listos</p>
        </div>
        <Button variant="ghost" size="sm" onClick={ocultarGuia}>
          Ocultar guía
        </Button>
      </div>
      <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {pasos.map((paso, i) => (
          <li key={paso.titulo} className="space-y-2 rounded-lg border p-3">
            <div className="flex items-center gap-2">
              <span
                aria-hidden
                className={cn(
                  "flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                  paso.estado === "hecho"
                    ? "bg-exito-suave text-success"
                    : "bg-info-suave text-accent"
                )}
              >
                {paso.estado === "hecho" ? <Check className="size-3.5" /> : i + 1}
              </span>
              <span className="font-medium">{paso.titulo}</span>
            </div>
            <p className="text-sm text-muted-foreground">{paso.descripcion}</p>
            <div className="flex flex-wrap items-center gap-2">
              <Badge
                variant={
                  paso.estado === "hecho"
                    ? "success"
                    : paso.estado === "proximamente"
                      ? "outline"
                      : "secondary"
                }
              >
                {NOMBRE_ESTADO[paso.estado]}
              </Badge>
              {paso.accion}
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
```

Run: `(cd web && npx vitest run src/componentes/GuiaUso.test.tsx)` → Expected: PASS.

- [ ] **Step 5: Registrar visitas, mostrar la guía desde el menú de usuario y agregarla al Tablero**

**Registrar visitas.** En `web/src/componentes/Layout.tsx`, después del efecto que fija `document.title`, agregue el siguiente efecto. Importe `marcarVisita` desde `@/guia` y `estaActiva` desde `@/componentes/navegacion`.

```tsx
  // La guía del Tablero marca como vistos Proveedores y Precios cuando se visitan.
  useEffect(() => {
    if (estaActiva("/proveedores", pathname)) marcarVisita("proveedores")
    if (estaActiva("/precios", pathname)) marcarVisita("precios")
  }, [pathname])
```

**Mostrar la guía desde el menú de usuario.** En `web/src/componentes/BarraSuperior.tsx`, dentro de `MenuUsuario`:
- agregue `const guia = useGuia()` y `const navegar = useNavigate()`. Importe `useNavigate` de `react-router`, `useGuia` y `mostrarGuia` de `@/guia`, y `CircleHelp` de `lucide-react`;
- antes del `DropdownMenuItem` de "Cerrar sesión", agregue:

```tsx
        {guia.oculta && (
          <DropdownMenuItem
            onSelect={() => {
              mostrarGuia()
              void navegar("/")
            }}
          >
            <CircleHelp aria-hidden />
            Mostrar guía de uso
          </DropdownMenuItem>
        )}
```

**Agregar la guía al Tablero.** En `web/src/paginas/Tablero.tsx`, importe `GuiaUso` y colóquelo justo después de `<EncabezadoPagina … />`, antes de `<AvisoInteligencia />`.

- [ ] **Step 6: Pruebas de integración**

En `web/src/componentes/Layout.test.tsx`, dentro de `describe("Layout con sesión iniciada", …)`, agregue. Importe `CLAVE_GUIA` desde `@/guia`.

```tsx
  it("visitar Proveedores lo marca como visto en la guía", () => {
    renderizar("/proveedores")
    expect(
      JSON.parse(localStorage.getItem(CLAVE_GUIA) ?? "{}").visitas.proveedores
    ).toBe(true)
  })

  it("si la guía está oculta, el menú de usuario permite mostrarla y lleva al tablero", async () => {
    localStorage.setItem(
      CLAVE_GUIA,
      JSON.stringify({ oculta: true, visitas: { proveedores: false, precios: false } })
    )
    renderizar("/ranking")
    await userEvent.click(screen.getByRole("button", { name: "Cuenta de Ana López" }))
    await userEvent.click(await screen.findByRole("menuitem", { name: "Mostrar guía de uso" }))

    expect(JSON.parse(localStorage.getItem(CLAVE_GUIA) ?? "{}").oculta).toBe(false)
    expect(document.title).toBe("Tablero · PluriOne")
  })
```

En `web/src/paginas/Tablero.test.tsx`:
- importe `respuestaJson` y `simularApi` desde `@/pruebas/utilidades`, y `vi` ya está importado;
- agregue un `beforeEach` que simule la API:

```tsx
beforeEach(() => {
  simularApi((url) =>
    url.startsWith("/api/proveedores/proveedores?")
      ? respuestaJson({ total: 60, elementos: [] })
      : new Response("", { status: 404 })
  )
})
```

- agregue `vi.unstubAllGlobals()` y `localStorage.clear()` al `afterEach` existente;
- agregue la prueba:

```tsx
  it("muestra la guía de uso arriba del tablero", async () => {
    renderizarPagina(<Tablero />)
    expect(
      await screen.findByRole("heading", { name: "Cómo usar PluriOne" })
    ).toBeInTheDocument()
  })
```

- [ ] **Step 7: Verificar y hacer commit**

Run: `(cd web && npx vitest run src/guia.test.ts src/componentes/GuiaUso.test.tsx src/componentes/Layout.test.tsx src/paginas/Tablero.test.tsx)` → Expected: PASS.
Run: `(cd web && npm run lint && npm run build && npx vitest run)` → Expected: todo en verde y salida limpia.

```bash
git add web/src/guia.ts web/src/guia.test.ts web/src/componentes/GuiaUso.tsx web/src/componentes/GuiaUso.test.tsx web/src/componentes/Layout.tsx web/src/componentes/Layout.test.tsx web/src/componentes/BarraSuperior.tsx web/src/paginas/Tablero.tsx web/src/paginas/Tablero.test.tsx
git commit -m "feat(web): guía 'Cómo usar PluriOne' con avance en el tablero" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 7: Siguiente paso en cada pantalla

**Files:**
- Create: `web/src/componentes/SiguientePaso.tsx`, `web/src/componentes/SiguientePaso.test.tsx`
- Modify: `web/src/paginas/ProveedorDetalle.tsx`, `web/src/paginas/Precios.tsx`, `web/src/paginas/Ranking.tsx`, `web/src/paginas/Alertas.tsx`, `web/src/paginas/Importacion.tsx`
- Modify (pruebas): `web/src/paginas/ProveedorDetalle.test.tsx`, `Precios.test.tsx`, `Ranking.test.tsx`, `Alertas.test.tsx`, `Importacion.test.tsx`

**Interfaces:**
- Consumes: tintes (`bg-info-suave`, Tarea 3), `NOMBRES_CATEGORIA` (`@/tipos`).
- Produces:
  - `type EnlaceSiguiente = { titulo: string; descripcion: string; ruta: string; icono: LucideIcon }`;
  - `SiguientePaso({ enlaces: EnlaceSiguiente[] })`, con encabezado h2 "Siguiente paso".

- [ ] **Step 1: Prueba del componente (falla)**

`web/src/componentes/SiguientePaso.test.tsx`:

```tsx
import { cleanup, screen } from "@testing-library/react"
import { Tags } from "lucide-react"
import { afterEach, describe, expect, it } from "vitest"
import { SiguientePaso } from "@/componentes/SiguientePaso"
import { esperarSinViolaciones, renderizarPagina } from "@/pruebas/utilidades"

afterEach(cleanup)

describe("SiguientePaso", () => {
  it("muestra cada enlace con su descripción y destino", async () => {
    const { container } = renderizarPagina(
      <SiguientePaso
        enlaces={[
          {
            titulo: "Revisar precios",
            descripcion: "Compare lo que paga con el mercado.",
            ruta: "/precios",
            icono: Tags,
          },
        ]}
      />
    )
    expect(
      screen.getByRole("heading", { level: 2, name: "Siguiente paso" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: /Revisar precios/ })
    ).toHaveAttribute("href", "/precios")
    expect(
      screen.getByText("Compare lo que paga con el mercado.")
    ).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })
})
```

Run: `(cd web && npx vitest run src/componentes/SiguientePaso.test.tsx)` → Expected: FAIL.

- [ ] **Step 2: Crear `web/src/componentes/SiguientePaso.tsx`**

```tsx
import { ArrowRight, type LucideIcon } from "lucide-react"
import { useId } from "react"
import { Link } from "react-router"

export type EnlaceSiguiente = {
  titulo: string
  descripcion: string
  ruta: string
  icono: LucideIcon
}

/** Sugiere a dónde ir después de la pantalla actual. */
export function SiguientePaso({ enlaces }: { enlaces: EnlaceSiguiente[] }) {
  const idTitulo = useId()
  return (
    <section aria-labelledby={idTitulo} className="space-y-3">
      <h2 id={idTitulo} className="text-base font-semibold">
        Siguiente paso
      </h2>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {enlaces.map(({ titulo, descripcion, ruta, icono: Icono }) => (
          <li key={ruta}>
            <Link
              to={ruta}
              className="flex h-full items-start gap-3 rounded-xl border bg-card p-4 outline-hidden transition-colors hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-info-suave">
                <Icono aria-hidden className="size-4 text-accent" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-medium">{titulo}</span>
                <span className="block text-sm text-muted-foreground">
                  {descripcion}
                </span>
              </span>
              <ArrowRight
                aria-hidden
                className="size-4 shrink-0 self-center text-muted-foreground"
              />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
```

Run: `(cd web && npx vitest run src/componentes/SiguientePaso.test.tsx)` → Expected: PASS.

- [ ] **Step 3: Pruebas por pantalla (fallan)**

**Detalle de proveedor.** En `web/src/paginas/ProveedorDetalle.test.tsx` agregue:

```tsx
  it("sugiere ver precios y compararlo en el ranking de su categoría", async () => {
    api()
    renderizar()
    await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })
    expect(
      screen.getByRole("link", { name: /Ver precios de sus servicios/ })
    ).toHaveAttribute("href", "/precios")
    expect(
      screen.getByRole("link", { name: /Compararlo en el ranking/ })
    ).toHaveAttribute("href", "/ranking?categoria=nube")
  })

  it("un proveedor sin categorías lleva al ranking general", async () => {
    api({ [RUTA]: () => respuestaJson({ ...PROVEEDOR, categorias: [] }) })
    renderizar()
    await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })
    expect(
      screen.getByRole("link", { name: /Compararlo en el ranking/ })
    ).toHaveAttribute("href", "/ranking")
  })
```

**Precios.** En `web/src/paginas/Precios.test.tsx`, dentro del `it` "elegir un servicio lo refleja en la URL y muestra su detalle", agregue al final:

```tsx
    expect(
      screen.getByRole("link", { name: /Ver proveedores de esta categoría/ })
    ).toHaveAttribute("href", "/proveedores?categoria=nube")
```

**Ranking y Alertas.** En `web/src/paginas/Ranking.test.tsx` y en `web/src/paginas/Alertas.test.tsx`, agregue en cada uno, cambiando `<Ranking />` por `<Alertas />` y la ruta según el archivo:

```tsx
  it("sugiere ver proveedores y revisar precios", () => {
    renderizarPagina(<Ranking />, { ruta: "/ranking" })
    expect(screen.getByRole("link", { name: /Ver proveedores/ })).toHaveAttribute(
      "href",
      "/proveedores"
    )
    expect(screen.getByRole("link", { name: /Revisar precios/ })).toHaveAttribute(
      "href",
      "/precios"
    )
  })
```

**Importación.** En `web/src/paginas/Importacion.test.tsx`, dentro del `it` "guía la importación en tres pasos y muestra el resumen", agregue al final:

```tsx
    expect(screen.getByRole("link", { name: "Ir al tablero" })).toHaveAttribute(
      "href",
      "/"
    )
```

Run: `(cd web && npx vitest run src/paginas)` → Expected: FAIL en las pruebas nuevas.

- [ ] **Step 4: Agregar `SiguientePaso` a cada pantalla**

**Detalle de proveedor** (`ProveedorDetalle.tsx`). Al final de la `<section>`, después de `</Tabs>`, con `p = detalle.data`. Importe `Tags` y `Trophy` de `lucide-react`.

```tsx
      <SiguientePaso
        enlaces={[
          {
            titulo: "Ver precios de sus servicios",
            descripcion: "Compare lo que paga con el precio de referencia del mercado.",
            ruta: "/precios",
            icono: Tags,
          },
          {
            titulo: "Compararlo en el ranking",
            descripcion: "Vea cómo se ubica frente a otros proveedores de su categoría.",
            ruta: detalle.data.categorias[0]
              ? `/ranking?categoria=${detalle.data.categorias[0]}`
              : "/ranking",
            icono: Trophy,
          },
        ]}
      />
```

**Precios** (`Precios.tsx`). Al final de `DetalleServicio`, después de la última `</Seccion>`. Importe `Building2` de `lucide-react`.

```tsx
      <SiguientePaso
        enlaces={[
          {
            titulo: "Ver proveedores de esta categoría",
            descripcion: `Proveedores de ${NOMBRES_CATEGORIA[servicio.categoria] ?? servicio.categoria} y sus contratos.`,
            ruta: `/proveedores?categoria=${servicio.categoria}`,
            icono: Building2,
          },
        ]}
      />
```

**Ranking y Alertas.** Al final de la `<section>` de cada página. Importe `Building2` y `Tags` de `lucide-react`.

```tsx
      <SiguientePaso
        enlaces={[
          {
            titulo: "Ver proveedores",
            descripcion: "Revise quién le vende y sus contratos.",
            ruta: "/proveedores",
            icono: Building2,
          },
          {
            titulo: "Revisar precios",
            descripcion: "Compare lo que paga con el mercado.",
            ruta: "/precios",
            icono: Tags,
          },
        ]}
      />
```

**Importación** (`Importacion.tsx`). En el paso 3, rama de éxito, después del botón "Importar otro archivo" y dentro del mismo `div` de botones, agregue:

```tsx
                <Button asChild variant="ghost">
                  <Link to="/">Ir al tablero</Link>
                </Button>
```

Importe `Link` de `react-router` si falta.

- [ ] **Step 5: Verificar y hacer commit**

Run: `(cd web && npx vitest run src/componentes/SiguientePaso.test.tsx src/paginas)` → Expected: PASS.
Run: `(cd web && npm run lint && npm run build && npx vitest run)` → Expected: todo en verde y salida limpia.

```bash
git add web/src/componentes/SiguientePaso.tsx web/src/componentes/SiguientePaso.test.tsx web/src/paginas
git commit -m "feat(web): sugerir el siguiente paso en detalle de proveedor, precios, ranking, alertas e importación" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 8: Textos en lenguaje llano, términos e iniciales

**Files:**
- Create: `web/src/componentes/Iniciales.tsx`, `web/src/componentes/Iniciales.test.tsx`
- Modify: `web/src/paginas/Tablero.tsx`, `Proveedores.tsx`, `ProveedorDetalle.tsx`, `Precios.tsx`, `Ranking.tsx`, `Alertas.tsx`, `Configuracion.tsx`, `Importacion.tsx`
- Modify: las pruebas de esas páginas solo donde citan un texto que cambia

**Interfaces:**
- Consumes: `Termino` (Tarea 4), `TarjetaKpi` con `titulo: ReactNode` (Tarea 3).
- Produces: `iniciales(nombre: string): string` e `Iniciales({ nombre: string, tamano?: "sm" | "lg" })`, decorativo (`aria-hidden`).

- [ ] **Step 1: Pruebas de las iniciales (fallan)**

`web/src/componentes/Iniciales.test.tsx`:

```tsx
import { describe, expect, it } from "vitest"
import { iniciales } from "@/componentes/Iniciales"

describe("iniciales", () => {
  it.each([
    ["Código Azteca S.A. de C.V.", "CA"],
    ["Nube Andina", "NA"],
    ["Consultores", "C"],
    ["Ñandú Digital S. de R.L.", "ÑD"],
    ["", "?"],
  ])("%s → %s", (nombre, esperado) => {
    expect(iniciales(nombre)).toBe(esperado)
  })
})
```

Run: `(cd web && npx vitest run src/componentes/Iniciales.test.tsx)` → Expected: FAIL.

- [ ] **Step 2: Crear `web/src/componentes/Iniciales.tsx`**

```tsx
import { cn } from "@/lib/utils"

/** Iniciales de las dos primeras palabras con mayúscula (ignora "S.A.", "de", "C.V."). */
export function iniciales(nombre: string): string {
  const letras = nombre
    .split(/\s+/)
    .filter((palabra) => /^\p{Lu}/u.test(palabra) && !palabra.includes("."))
    .slice(0, 2)
    .map((palabra) => palabra[0])
    .join("")
  return letras || "?"
}

export function Iniciales({
  nombre,
  tamano = "sm",
}: {
  nombre: string
  tamano?: "sm" | "lg"
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full bg-info-suave font-semibold text-accent",
        tamano === "lg" ? "size-12 text-base" : "size-8 text-xs"
      )}
    >
      {iniciales(nombre)}
    </span>
  )
}
```

Run: `(cd web && npx vitest run src/componentes/Iniciales.test.tsx)` → Expected: PASS.

- [ ] **Step 3: Iniciales en la lista y en el detalle de proveedor**

**Lista.** En `web/src/paginas/Proveedores.tsx`, en la celda del nombre, reemplace:

```tsx
                <TableCell>
                  <Link
                    to={`/proveedores/${encodeURIComponent(p.id)}`}
                    className="font-medium text-accent hover:underline"
                  >
                    {p.nombre}
                  </Link>
                  <div className="font-mono text-xs text-muted-foreground">
                    {p.rfc}
                  </div>
                </TableCell>
```

por:

```tsx
                <TableCell>
                  <div className="flex items-center gap-3">
                    <Iniciales nombre={p.nombre} />
                    <div>
                      <Link
                        to={`/proveedores/${encodeURIComponent(p.id)}`}
                        className="font-medium text-accent hover:underline"
                      >
                        {p.nombre}
                      </Link>
                      <div className="font-mono text-xs text-muted-foreground">
                        {p.rfc}
                      </div>
                    </div>
                  </div>
                </TableCell>
```

**Detalle.** En `web/src/paginas/ProveedorDetalle.tsx`, dentro de `Encabezado`, envuelva el `<h1>` así: `<div className="flex items-center gap-3"><Iniciales nombre={p.nombre} tamano="lg" /><h1 …>{p.nombre}</h1></div>`.

- [ ] **Step 4: Textos nuevos y términos**

Reemplace estos textos exactamente. Use usted. Las celdas con `<Termino>` son JSX: importe `Termino` desde `@/componentes/Termino` en cada archivo que lo use.

| Archivo y lugar | Texto nuevo |
|---|---|
| `Tablero.tsx` · descripción del encabezado | `` `${nombre ? `Hola, ${nombre}. ` : ""}Esto es lo que gasta en servicios de TI y lo que conviene atender.` `` |
| `Tablero.tsx` · título del KPI con `clave: "ahorro"` | `<Termino clave="ahorroPotencial">Ahorro potencial</Termino>`. En el tipo de `KPIS`, cambie `titulo: string` por `titulo: ReactNode` |
| `Proveedores.tsx` · descripción del encabezado | `"Quién le vende servicios de TI, en qué categorías y si sigue activo."` |
| `ProveedorDetalle.tsx` · `Resumen`, `Seccion` `descripcion` | `<>Último mes registrado del <Termino clave="desempeno">desempeño</Termino> del proveedor, incluido el cumplimiento del <Termino clave="sla">SLA</Termino>.</>` |
| `ProveedorDetalle.tsx` · pestaña Desempeño, `Seccion` de "Desempeño de los últimos 24 meses": agregue `descripcion` | `<>Cómo ha cumplido mes a mes, incluido el <Termino clave="sla">SLA</Termino>.</>` |
| `Precios.tsx` · descripción del encabezado | `<>Compare lo que paga con lo que se paga en el mercado: el <Termino clave="precioReferencia">precio de referencia</Termino> de cada servicio y los contratos con <Termino clave="sobreprecio">sobreprecio</Termino>.</>` |
| `Precios.tsx` · `DetalleServicio`, estado vacío "Sin precio de referencia todavía" | `<>Aquí verá el precio bajo, típico y alto del mercado (<Termino clave="percentiles">P25, P50 y P75</Termino>) para la cantidad y el plazo que indique, con cuántos contratos se calculó.</>` |
| `Precios.tsx` · estado vacío "Sin historial todavía" | `"Aquí verá cómo han cambiado los precios de este servicio en el tiempo, junto al rango típico del mercado."` |
| `Precios.tsx` · título de la `Seccion` "Contratos sobre P75" | `"Contratos con sobreprecio"` |
| `Precios.tsx` · estado vacío de esa sección | `<>Aquí verá los contratos vigentes de este servicio que pagan de más y su <Termino clave="ahorroPotencial">ahorro potencial</Termino> al año.</>` |
| `Precios.tsx` · vista "Todos los sobreprecios", estado vacío | `"Aquí verá todos los contratos vigentes que pagan de más, ordenados por cuánto podría ahorrar."` |
| `Ranking.tsx` · descripción del encabezado | `<>Los proveedores mejor calificados de cada categoría según su <Termino clave="puntuacion">puntuación</Termino>.</>` |
| `Ranking.tsx` · estado vacío "Sin puntuaciones todavía" | `<>El ranking ordenará a los proveedores por su <Termino clave="desempeno">desempeño</Termino>. Los que tengan menos de 6 meses de datos llevarán la etiqueta <Termino clave="historialCorto">Historial corto</Termino>.</>` |
| `Alertas.tsx` · descripción del encabezado | `"Lo que conviene atender hoy: contratos por vencer, precios altos y proveedores que bajan su desempeño."` |
| `Alertas.tsx` · estado vacío "No hay alertas activas" | `<>Aquí aparecerán los contratos que vencen en 90, 60 y 30 días, los precios con <Termino clave="sobreprecio">sobreprecio</Termino> y los proveedores con puntuación baja o en caída.</>` |
| `Configuracion.tsx` · descripción del encabezado | `"Ajuste cómo se califica a los proveedores y cómo se calcula el precio de referencia."` |
| `Configuracion.tsx` · estado vacío "Sin configuración todavía" | `<>Podrá decidir cuánto pesa cada aspecto del <Termino clave="desempeno">desempeño</Termino> (deben sumar 100), desde qué puntuación un proveedor está en riesgo y la inflación anual.</>` |
| `Importacion.tsx` · descripción del encabezado | `"Cargue los archivos CSV que exporta el ERP, en el orden indicado. Si un archivo tiene errores, no se guarda ninguna fila y verá cuáles corregir."` |

En `Ranking.tsx`, `Alertas.tsx` y `Configuracion.tsx`, la `descripcion` del estado vacío pasa de cadena a JSX. Escríbala entre llaves: `descripcion={<>…</>}`.

- [ ] **Step 5: Ajustar pruebas que citan textos cambiados**

Run: `grep -rn "Contratos sobre P75\|Resumen de las compras\|sus categorías y su estado\|puntuación ajustada\|Parámetros de la puntuación" web/src --include=*.test.tsx`

Por cada coincidencia, cambie el texto esperado por el nuevo de la tabla del Step 4. No cambie ninguna prueba para que acepte un texto distinto al de la tabla.

Run: `(cd web && npx vitest run src/paginas src/componentes)` → Expected: PASS.

- [ ] **Step 6: Verificar y hacer commit**

Run: `(cd web && npm run lint && npm run build && npx vitest run)` → Expected: todo en verde y salida limpia.

```bash
git add web/src/componentes/Iniciales.tsx web/src/componentes/Iniciales.test.tsx web/src/paginas
git commit -m "feat(web): textos en lenguaje llano con ayuda de términos e iniciales de proveedor" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 9: Revisión en navegador y documentación

La revisión en navegador la hace el controlador, porque necesita el panel de navegador. Las correcciones y la documentación se despachan a un implementador con el archivo de hallazgos y pasan por revisión.

**Files:**
- Create: `docs/qa/revision-claridad-y-acceso.md`
- Modify: `README.md` (sección "Interfaz")
- Modify: los archivos que requieran correcciones, cada una con su prueba cuando sea comprobable en jsdom

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: evidencia de la revisión: login y app a 375, 768, 1024 y 1440 px, en claro y oscuro, con axe con contraste.

- [ ] **Step 1: Suite completa y prueba de humo**

Run: `(cd web && npm run lint && npm run build && npx vitest run)` → Expected: todo en verde.
Run: `docker compose -f infra/docker-compose.yml up -d --build --wait gateway` y luego `uv run python infra/smoke_test.py` → Expected: `OK: …`.

- [ ] **Step 2: Login en navegador (controlador)**

Abra <http://localhost:8080> sin sesión y revise el login a 375, 768, 1024 y 1440 px, en claro y oscuro (`resize_window` con `colorScheme`). Verifique:
- **Contenido:** el panel con la marca y el lema en todos los anchos; los 4 puntos desde 768 px y sus descripciones desde 1024 px; los acentos bien escritos.
- **Layout:** sin scroll horizontal; el formulario usable.
- **Foco:** visible al tabular.

Corra axe en la página de Keycloak con `javascript_tool`. La CSP de Keycloak no bloquea las evaluaciones del panel; inyecte el texto de axe solo si `fetch` lo permite. Si no se puede, revise el contraste a mano con los valores del CSS.

Inicie sesión como `admin1` (contraseña en `infra/keycloak/realm-plataforma.json`; no la repita en el chat). Confirme que no se pide OTP.

- [ ] **Step 3: App en navegador (controlador)**

Con el servidor de Vite, corra axe con contraste, en claro y oscuro y en los 4 anchos, sobre: Tablero (con la guía), Proveedores, Detalle (3 pestañas), Precios con un servicio, Ranking, Alertas, Importación (como admin1) y Configuración. Revise además:
- abrir y cerrar un término con el teclado;
- la descripción del menú con el menú colapsado (ayuda emergente);
- ocultar la guía y volver a mostrarla desde el menú de usuario.

Anote los hallazgos en un archivo de trabajo.

- [ ] **Step 4: Corregir, documentar y hacer commit (implementador)**

Corrija cada hallazgo con su prueba cuando aplique, en un commit `fix(web): …` por hallazgo.

Escriba `docs/qa/revision-claridad-y-acceso.md` con:
- la fecha y el commit revisado;
- la tabla página × ancho × tema con los resultados de axe y de scroll;
- el login por ancho y tema;
- la verificación sin OTP;
- los hallazgos y su corrección;
- lo que no se pudo revisar, con su motivo.

En `README.md`, dentro de "## Interfaz", agregue estas dos viñetas al final de la lista:

```markdown
- Guía "Cómo usar PluriOne" en el Tablero (se oculta y vuelve desde el menú de usuario) y menú
  con una línea de propósito en cada opción.
- Los términos técnicos (P25/P50/P75, sobreprecio, puntuación, SLA…) tienen una ayuda que se
  abre con clic, toque o teclado; las definiciones viven en `web/src/glosario.ts`.
```

```bash
git add docs/qa/revision-claridad-y-acceso.md README.md
git commit -m "docs(qa): revisión en navegador de claridad y acceso" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```
