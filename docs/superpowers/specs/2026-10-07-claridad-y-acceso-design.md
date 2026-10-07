# Claridad y acceso: especificación de diseño

| Campo | Valor |
|---|---|
| PRD padre | `docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md` |
| Antecede a | Plan B del sub-proyecto 1 (`docs/superpowers/specs/2026-10-01-experiencia-e-inteligencia-design.md`, sección 8) |
| Fecha | 2026-10-07 |
| Estado | Pendiente de revisión del residente |
| Base de código | Plan A terminado (rama `feat/experiencia-inteligencia`, commit `405f86e`) |

---

## 0. Contexto y decisiones

Tras ver el Plan A en marcha, el residente pidió:
- quitar el OTP;
- un login más estético y mejor hecho;
- mejor experiencia de usuario;
- que se entienda a simple vista para qué sirve el programa.

Las decisiones se tomaron con maquetas en el navegador.

| # | Decisión |
|---|---|
| C1 | Se quita el **OTP**: todos los usuarios entran con usuario y contraseña. El PRD ya no lo menciona. |
| C2 | Se trabaja en **dos pasos**. Este documento cubre la claridad, el acceso y el estilo. Después, el Plan B llena de datos reales el Tablero, Precios, Ranking y Alertas. |
| C3 | El login es una **pantalla dividida**: a la izquierda, qué es el producto y qué hace; a la derecha, el formulario. |
| C4 | El login se construye **sobrescribiendo la plantilla base** del tema `plataforma` de Keycloak, con los textos en un archivo de mensajes en español. Keycloak sigue manejando las contraseñas. |
| C5 | En el Tablero, una **guía de pasos** "Cómo usar PluriOne" (opción A) y un **menú que se explica solo** (opción B). Sin recorrido guiado. |
| C6 | Estilo visual **B — refinado**. Iconos con fondo de color suave, acento según el estado, una acción clara por tarjeta. Paleta y temas sin cambios. |
| C7 | Mejoras de experiencia pedidas: **lenguaje y términos**, **aspecto visual** y **ver qué hacer después**. |

---

## 1. Objetivo y criterios de éxito

**Objetivo:** que una persona que llega por primera vez entienda, desde la pantalla de inicio de sesión, qué hace la plataforma y para quién es. Dentro, que sepa por dónde empezar y qué hacer en cada pantalla, sin explicación externa.

| Criterio | Meta |
|---|---|
| Propósito visible | El login muestra el nombre, un lema y 4 capacidades del producto; en móvil, al menos el nombre y el lema |
| Acceso | Ningún usuario sembrado (`admin1`, `comprador1`, `aprobador1`) recibe una solicitud de OTP, ni en un realm nuevo ni en el ya importado tras el procedimiento documentado |
| Por dónde empezar | El Tablero muestra la guía de 4 pasos con su avance; cada paso pendiente enlaza a donde se hace |
| Menú | Cada opción del menú tiene una línea de propósito visible (o en la ayuda emergente si el menú está colapsado) |
| Términos | Todo término técnico visible (P25/P50/P75, sobreprecio, ahorro potencial, puntuación, SLA, desempeño, historial corto, baja confianza) tiene una ayuda accesible con mouse, teclado y toque |
| Siguiente acción | Detalle de proveedor, Precios (con servicio elegido), Ranking y Alertas muestran al menos una acción de "siguiente paso" |
| Accesibilidad | 0 violaciones de axe por página en ambos temas (jsdom y navegador real); los tintes nuevos cumplen ≥ 3:1 contra el icono que los usa (prueba automática) |
| Responsivo | Login y app usables a 375, 768, 1024 y 1440 px sin scroll horizontal de página |

---

## 2. Alcance

**Incluye**
- Retiro del OTP: realm, procedimiento para el realm ya importado, PRD, spec del sub-proyecto 1 y README.
- Login de pantalla dividida en el tema `plataforma`.
- Guía "Cómo usar PluriOne" en el Tablero.
- Menú con descripciones y frases de propósito en cada página.
- Glosario de términos con ayuda emergente y revisión de los textos de la aplicación.
- Estilo visual refinado: tarjetas de indicador, secciones, estados vacíos, iniciales de proveedor.
- Bloques de "siguiente paso" en las pantallas indicadas.

**No incluye**
- Datos de inteligencia: es el Plan B.
- Recorrido guiado.
- Cambios de paleta o de tipografía.
- Cambios en la API de `proveedores`.
- La negociación: el paso 4 de la guía queda como "Próximamente".

---

## 3. Acceso sin OTP

- **Realm de desarrollo:** `infra/keycloak/realm-plataforma.json` deja de declarar `requiredActions: ["CONFIGURE_TOTP"]` en `admin1` y `aprobador1`.
- **Realm ya importado:** Keycloak no lo reimporta. El README documenta cómo quitar a `admin1` y `aprobador1` la acción pendiente "Configure OTP" y borrar cualquier credencial OTP ya registrada, de dos formas:
  - comandos `kcadm.sh` para Git Bash y PowerShell, que leen la contraseña de administrador del entorno del contenedor;
  - la consola de administración: Users → usuario → *Required user actions* vacío, y Credentials → borrar "otp".
- **Sin cambios:** se conservan la protección contra fuerza bruta y la política de contraseñas de Keycloak. Los roles y la validación de JWT en los servicios no cambian.
- **Documentos:**
  - El PRD (5.1) dice "Inicio de sesión con usuario y contraseña".
  - El spec del sub-proyecto 1 ya no lista "OTP por rol".
  - El README deja de decir que admin y aprobador configuran OTP, y retira la limitación "OTP por usuario, no por rol".
  - Los planes y bitácoras anteriores no se editan: son registro histórico.

---

## 4. Inicio de sesión de pantalla dividida

**Estructura**
- **Plantilla:** el tema `plataforma` (padre `keycloak.v2`) agrega su propia `login/template.ftl`. Parte de la plantilla de `keycloak.v2` de Keycloak 26.5 y conserva todo lo que hace: mensajes, idioma, formularios, `#kc-page-title`, enlaces e "Intentar otra forma".
- **Panel:** se agrega `<aside class="plataforma-panel">` junto al contenedor del formulario. El encabezado actual con el nombre del realm pasa a formar parte del panel.
- **Textos:** van en `login/messages/messages_es.properties` del tema. Ningún texto de producto queda en CSS ni en imágenes.

**Contenido del panel** (marino en ambos temas; texto ≥ 4.5:1)
- **Marca:** "PluriOne" y debajo "Negociación con proveedores de TI".
- **Lema:** "Pague el precio justo y elija a los mejores proveedores".
- **Cuatro puntos**, cada uno con icono decorativo (SVG en línea, `aria-hidden`) y texto:
  1. **Precio de referencia:** cuánto se paga en el mercado por cada servicio.
  2. **Ranking de proveedores:** quién rinde mejor según su desempeño real.
  3. **Alertas:** contratos por vencer y precios por encima del mercado.
  4. **Negociación asistida por IA:** siempre con aprobación humana.

**Diseño**
- **Escritorio (≥ 1024 px):** dos columnas. Panel de unos 45 % de ancho y formulario centrado en una tarjeta.
- **Tableta (768–1023 px):** dos columnas más compactas, con los cuatro puntos sin descripción.
- **Móvil (< 768 px):** el panel se reduce a un encabezado con la marca y el lema sobre el formulario; los cuatro puntos se ocultan.
- **Común a todos:**
  - fuente Fira Sans;
  - foco visible;
  - botón principal en color de acento con texto ≥ 4.5:1;
  - tema oscuro con la clase `pf-v5-theme-dark` que aplica Keycloak.

**Verificación:** la prueba de humo comprueba que la página de login contiene el lema. La revisión en navegador mide la página en los cuatro anchos y en ambos temas.

---

## 5. Explicar el producto dentro de la aplicación

### 5.1 Guía "Cómo usar PluriOne" (Tablero)

| Paso | Texto | Se marca hecho cuando | Enlace si está pendiente |
|---|---|---|---|
| 1 | Importar contratos y proveedores | Hay al menos un proveedor (`GET /api/proveedores/proveedores?limite=1` con `total > 0`) | Admin: "Ir a Importación". Otros roles: "Administración importa los datos del ERP" (sin enlace) |
| 2 | Conocer a sus proveedores | La persona visitó Proveedores | "Ver proveedores" |
| 3 | Ver el precio justo | La persona visitó Precios | "Ver precios" |
| 4 | Negociar y aprobar | — (insignia "Próximamente") | — |

- **Ubicación:** la guía va arriba del Tablero, debajo del encabezado. Muestra "N de 3 listos": el paso 4 no cuenta mientras está en "Próximamente".
- **Persistencia:** las visitas y la preferencia "Ocultar guía" se guardan en `localStorage` con la clave `plataforma-guia`. Si el almacenamiento está bloqueado o corrupto, la guía se muestra con los pasos 2 y 3 sin marcar.
- **Ocultar:** la guía se oculta con "Ocultar guía" y vuelve desde el menú de usuario con "Mostrar guía de uso".
- **Accesibilidad:** lista ordenada; cada paso tiene un estado textual ("hecho" o "pendiente"), no solo un icono.

### 5.2 Menú que se explica solo

`NAVEGACION` agrega `descripcion` a cada elemento:

| Elemento | Descripción |
|---|---|
| Tablero | Resumen del gasto y lo urgente |
| Proveedores | Quién le vende y cómo rinde |
| Ranking | Los mejores proveedores por categoría |
| Precios | Cuánto debería pagar |
| Alertas | Qué atender hoy |
| Importación | Cargar datos del ERP |
| Configuración | Ajustes de puntuación y precios |

- Con el menú expandido, la descripción se muestra bajo el título, en texto secundario.
- Con el menú colapsado, la ayuda emergente muestra el título y la descripción.
- El nombre accesible del enlace sigue siendo el título.
- El encabezado de cada página usa una frase de propósito en lenguaje llano. Ejemplo: Precios, "Compare lo que paga con lo que se paga en el mercado".

### 5.3 Lenguaje y términos

- **Componente `Termino`:**
  - muestra el término con subrayado punteado;
  - al activarlo abre un `popover` de shadcn con la definición; funciona con clic, toque y teclado (Enter o Espacio), y se cierra con Escape;
  - el disparador es un botón cuyo nombre accesible es el término.
- **Glosario (`web/src/glosario.ts`), única fuente de las definiciones:**

| Término | Definición |
|---|---|
| P25 · P50 · P75 | Precio bajo, típico y alto del mercado: el 25 %, 50 % y 75 % de los contratos comparables cuestan eso o menos. |
| Precio de referencia | Lo que se paga normalmente en el mercado por el servicio, la cantidad y el plazo indicados. |
| Sobreprecio | Paga más que el 75 % de los contratos comparables. |
| Ahorro potencial | Lo que ahorraría al año si pagara el precio típico del mercado (P50). |
| Puntuación | Calificación de 0 a 100 del desempeño del proveedor en los últimos 12 meses, comparada con su categoría. |
| SLA | Nivel de servicio comprometido en el contrato, como el porcentaje de disponibilidad. |
| Desempeño | Cumplimiento del SLA, tiempo de resolución, incidentes críticos, entregas a tiempo y satisfacción. |
| Historial corto | Menos de 6 meses de datos: la puntuación se acerca al promedio de su categoría hasta tener más historia. |
| Baja confianza | Hay pocos contratos comparables (menos de 8): el precio de referencia es una estimación. |

- **Revisión de textos:** se revisan todos los textos visibles de las páginas y componentes para quitar jerga, usar oraciones cortas y hablar de usted de forma consistente. El primer uso visible de cada término del glosario en una página lleva `Termino`.

---

## 6. Estilo visual refinado (B)

**Tokens nuevos de tinte** en `index.css`: fondos suaves para los iconos. Los colores de primer plano siguen siendo `accent`, `success`, `warning` y `destructive`.

| Token | Claro | Oscuro | Uso (icono encima) |
|---|---|---|---|
| `info-suave` | `#E0F2FE` | `#0C2A44` | `accent` |
| `exito-suave` | `#DCFCE7` | `#0F2E1F` | `success` |
| `advertencia-suave` | `#FEF3C7` | `#3A2A0B` | `warning` |
| `riesgo-suave` | `#FEE2E2` | `#3B1515` | `destructive` |

`tokens.node.test.ts` agrega los pares (icono, tinte) con mínimo 3:1 en ambos temas. Si un valor no lo cumple, se ajusta el tinte, no la regla.

**Tarjeta de indicador (`TarjetaKpi`)**
- Agrega `tono: "info" | "exito" | "advertencia" | "riesgo"` (por defecto `info`). El tono pinta el icono sobre su tinte. Con `advertencia` o `riesgo`, la tarjeta lleva además un acento lateral de 3 px.
- Agrega `variacion?: { texto: string; direccion: "sube" | "baja" }`. Se muestra con flecha y texto; el color nunca es la única señal.
- La acción es un enlace visible con texto específico, por ejemplo "Revisar vencimientos".
- Con `valor = null`, la tarjeta sigue mostrando "—" y "Sin datos" para lectores de pantalla. El Plan B le pasa cifras.

**Tablero en este paso:**

| Tarjeta | Tono |
|---|---|
| Gasto anual | info |
| Por vencer | advertencia |
| Proveedores en riesgo | riesgo |
| Ahorro potencial | éxito |

**Secciones:** `Seccion` acepta una acción de encabezado (`acciones`, ya existe) que se usa para "Ver detalle" donde hay destino.

**Estados vacíos:** el icono va dentro de un círculo con `info-suave`.

**Proveedores:** un círculo con las iniciales del proveedor (`info-suave` y `accent`) en la lista y en el encabezado del detalle. Es decorativo (`aria-hidden`); el nombre sigue siendo el texto.

---

## 7. Siguiente acción en cada pantalla

**Componente `SiguientePaso`:** una sección "Siguiente paso" con 1 a 3 enlaces. Cada enlace lleva icono, título y una línea de descripción.

| Pantalla | Enlaces |
|---|---|
| Detalle de proveedor | "Ver precios de sus servicios" → `/precios`. "Compararlo en el ranking" → `/ranking?categoria=<primera categoría del proveedor>` |
| Precios con servicio elegido | "Ver proveedores de esta categoría" → `/proveedores?categoria=<categoría del servicio>` |
| Ranking | "Ver proveedores" → `/proveedores`. "Revisar precios" → `/precios` |
| Alertas | "Revisar precios" → `/precios`. "Ver proveedores" → `/proveedores` |
| Importación | Ya existe ("Importar \<siguiente\>"). Se agrega "Ir al tablero" en el resultado |

---

## 8. Calidad

- **Pruebas de Vitest y Testing Library:**
  - guía: avance según los datos y las visitas, ocultar y mostrar, almacenamiento bloqueado, enlaces por rol;
  - descripciones del menú;
  - `Termino`: abre con teclado y toque, cierra con Escape, y su nombre accesible es el término;
  - `TarjetaKpi` por tono y variación;
  - `SiguientePaso` en cada pantalla, con sus destinos.
- **axe** por página en ambos temas, y prueba de contraste de los tintes.
- **Prueba de humo:**
  - el login contiene el lema;
  - un usuario con rol de admin obtiene un token por *password grant* con el cliente `pruebas-humo` sin pasos adicionales (sin OTP).
- **Revisión en navegador:** login y aplicación a 375, 768, 1024 y 1440 px en ambos temas; axe con contraste. Los resultados se agregan a `docs/qa/`.

## 9. Entrega

- **Plan:** "Claridad y acceso", en una rama nueva creada desde `main`. Requiere fusionar antes el Plan A, que sigue sin fusionar.
- **Orden de las tareas:**
  1. Acceso sin OTP.
  2. Login dividido.
  3. Tokens de tinte y `TarjetaKpi`.
  4. Glosario y `Termino`.
  5. Menú con descripciones.
  6. Guía del Tablero.
  7. Siguiente paso.
  8. Revisión de textos e iniciales.
  9. Revisión en navegador y documentación.
- **Después:** el Plan B.
