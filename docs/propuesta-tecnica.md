# Propuesta técnica

Entregable 2 del cronograma (PRD §6.5): la estrategia de negociación, las reglas de negocio, el
stack y los costos de la Plataforma de Negociación Automática con Proveedores (proyecto 064,
PluriOne). Actualizada al 15/10/2026. La base es el
[PRD](superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md). La
arquitectura detallada está en [`arquitectura/`](arquitectura/README.md).

## 1. Problema y propuesta

Una empresa mediana que compra servicios de TI (licencias SaaS, nube, consultoría y soporte)
negocia a mano, con la información repartida en correos y hojas de cálculo. Eso trae cuatro
problemas:
- Las renovaciones suben sin que nadie las cuestione.
- El comprador no sabe cuál es un precio justo.
- La elección del proveedor es subjetiva.
- No queda rastro de qué se ofreció, qué se concedió y por qué.

**Propuesta:** una plataforma que junta el historial de compras, calcula un precio de referencia
del mercado y la puntuación de cada proveedor, y negocia por el comprador. Un agente negocia con
cada proveedor dentro de los límites que fija el comprador. El comprador supervisa y puede
intervenir, y ningún cierre es vinculante sin aprobación humana.

| Rol | Qué hace |
|---|---|
| Comprador | Crea negociaciones, fija límites, supervisa al agente e interviene; después, propone la adjudicación |
| Aprobador | Consulta las negociaciones; después, aprobará las adjudicaciones |
| Administrador | Usuarios, catálogo, importación de datos y configuración de la puntuación |
| Proveedor (externo) | Entra con su enlace de invitación, sin cuenta, y negocia en el portal |

**Fuera de alcance (v1):** integración con un ERP o correo reales (se simulan), varias empresas,
firma electrónica, órdenes de compra y pagos, búsqueda en PDFs de contratos, app móvil, Power BI
e idiomas distintos del español.

## 2. Estrategia de negociación

### 2.1 El principio: «el LLM habla, el motor decide»

Toda decisión con dinero la toma código determinista y probado: ofertas, contraofertas,
concesiones, aceptación y adjudicación (ADR-002). Un modelo de lenguaje solo interpretará los
mensajes del proveedor y redactará textos (N2, planeado). Así el agente es medible, explicable y
resistente a manipulación. Hoy el agente es completamente determinista y sus mensajes son
plantillas.

### 2.2 Lo que configura el comprador

Una negociación es una **compra** (servicios del catálogo con su cantidad y de 1 a 10 proveedores)
o una **renovación** (las líneas, la moneda y el plazo salen del contrato vigente, y el único
invitado es el proveedor actual). Para cada término negociado, el comprador fija:

- **Ideal:** lo que le gustaría conseguir.
- **Límite:** lo peor que acepta. El proveedor nunca lo ve.
- **Peso:** cuánto le importa ese término.

El precio por línea siempre se negocia. Además se pueden activar cinco palancas: plazo del
contrato, plazo de pago, disponibilidad garantizada (SLA), tope de aumento anual y cuota de
implementación. También elige el número de rondas, el estilo del agente (firme, balanceado o
flexible) y la fecha límite.

**La plataforma sugiere los límites del precio** con el precio de referencia del servicio de
inteligencia: P25, P50 y P75 de contratos comparables de los últimos 24 meses, ajustados por
inflación.
- **En una compra:** propone el P25 como ideal y el P50 como límite.
- **En una renovación:** propone al menos 5 % menos que el precio vigente como ideal, y nunca un
  límite por encima del precio vigente más el tope de aumento del contrato.

### 2.3 Cómo decide el agente

El motor sigue una estrategia de concesiones dependiente del tiempo (Faratin) con utilidad
multiatributo (ADR-007):

1. **Utilidad.** Cada oferta vale de 0 % a 100 % para el comprador: 100 % es su ideal en todo y
   0 % es quedar exactamente en su límite. Cada término cuenta según su peso.
2. **Objetivo por ronda.** En la ronda *t* de *T*, el agente se conforma con una utilidad de
   `1 − (t/T)^(1/β)`:
   - firme (β = 0.3) cede muy poco hasta las últimas rondas;
   - balanceado (β = 0.6) cede poco al principio y más hacia el final;
   - flexible (β = 1.0) cede de forma pareja.
3. **Aceptación.** Acepta si la oferta respeta todos los límites y vale al menos lo que pediría en
   esa ronda. En la última ronda acepta cualquier oferta dentro de los límites; si cruza alguno,
   cierra sin acuerdo.
4. **Contraoferta.** Si no acepta, propone valores con la utilidad objetivo. Nunca pide algo peor
   para el comprador que lo que el proveedor ya ofreció, no revela el límite antes de la última
   ronda y casi nunca retrocede de una ronda a otra.
5. **Presión competitiva.** Si otro proveedor ya ofreció algo mejor, el mensaje lo dice sin nombrar
   a nadie («Hemos recibido propuestas más competitivas»).
6. **Revisión de cordura.** Un precio menor que la décima parte o mayor que diez veces la
   referencia (o el límite, si no hay referencia) se devuelve para que el proveedor lo confirme, y
   esa ronda no cuenta.

Cada respuesta deja una traza que el comprador ve en «¿Por qué respondió esto?».

### 2.4 Supervisión humana y cierre

- La supervisión se actualiza cada 3 segundos.
- **Tomar el control:** el comprador responde a mano con un mensaje, una contraoferta, la
  aceptación de la última oferta o el cierre sin acuerdo. Lo que sale de sus límites pide
  confirmación y queda marcado para el aprobador. «Devolver al agente» regresa la sesión al agente.
- **El proveedor puede pedir hablar con una persona:** la sesión queda «Escalada» hasta que el
  comprador la atienda.
- **Fecha límite:** al llegar, las sesiones en curso expiran y la negociación pasa a «En
  evaluación».
- **Todo acuerdo es tentativo.** La adjudicación con aprobación es el siguiente incremento (4′, del
  21/10 al 11/11/2026). Hará tres cosas:
  - recomendará entre los acuerdos tentativos con una suma ponderada de costo total, desempeño,
    riesgo y SLA (pesos por defecto: 40, 30, 15 y 15), explicada;
  - el comprador propondrá la adjudicación, con una justificación si se aparta de la
    recomendación;
  - el aprobador decidirá, y los proveedores lo verán en el portal.

### 2.5 Resultado medido

En la simulación contra bots con precio de reserva oculto (74 sesiones):
- 81.1 % de acuerdos (meta ≥ 70 %);
- 16.5 % de ahorro frente a la primera oferta (meta ≥ 8 %);
- 0 acuerdos fuera de los límites del comprador (meta 0).

Detalle en [`qa/simulacion-negociacion.md`](qa/simulacion-negociacion.md).

## 3. Reglas de negocio

| # | Regla | Dónde se aplica |
|---|---|---|
| RN-01 | Toda decisión con dinero la toma el motor determinista; ningún modelo de lenguaje fija montos. | `negociacion/dominio/motor.py` |
| RN-02 | El agente nunca acuerda algo que cruce un límite del comprador. Una persona puede aceptar o proponer algo fuera de límites solo si lo confirma, y queda marcado para el aprobador. | Motor y respuesta manual |
| RN-03 | Un acuerdo es tentativo: no es vinculante hasta que se adjudique y se apruebe. | Sesión «Acuerdo tentativo» (aprobación: incremento 4′) |
| RN-04 | El proveedor nunca ve los límites, los pesos ni las ofertas de otros proveedores. | API del portal |
| RN-05 | La fecha límite debe quedar entre 1 hora y 60 días después de publicar. | Validación al publicar |
| RN-06 | Una negociación tiene de 1 a 20 líneas, de 1 a 10 proveedores activos, de 2 a 12 rondas (6 por defecto) y un plazo de 1 a 60 meses (12 por defecto). | API de negociación |
| RN-07 | Los pesos de los términos activos suman 100, y cada palanca activa pesa al menos 1. | Validación al publicar |
| RN-08 | El ideal y el límite son distintos. En el precio, la cuota de implementación y el tope de aumento, el ideal es menor que el límite (pagar menos siempre es mejor); las demás palancas deducen su dirección del par. | Validación al publicar |
| RN-09 | En una renovación, el límite del precio no puede superar el precio vigente más el tope de aumento del contrato; un contrato sin tope no admite aumento. | Validación al publicar |
| RN-10 | Un límite por encima del P75 del mercado muestra un aviso, pero permite publicar. | Editor del borrador |
| RN-11 | Los montos son decimales exactos (nunca punto flotante), de hasta 10,000,000; los precios se negocian a centavos. | Esquemas y motor |
| RN-12 | Un precio fuera de 0.1× a 10× de la referencia se devuelve para confirmarlo; esa ronda no cuenta. | Motor |
| RN-13 | Cada enlace de invitación es personal y se muestra una sola vez; solo se guarda su hash. Deja de servir al llegar la fecha límite, al reenviarse o al cancelar la negociación, con la misma respuesta (401) en todos los casos. | `negociacion/tokens.py` y portal |
| RN-14 | Las ofertas y las respuestas manuales llevan una clave de idempotencia: reintentar el mismo envío no lo duplica. | API de sesiones y portal |
| RN-15 | La bitácora, los mensajes y las ofertas de una negociación no se cambian ni se borran; la Actividad de la administración tampoco. | Permisos de la base (ADR-006) |
| RN-16 | Solo el rol de compras crea, publica, reenvía, cancela y atiende a mano las negociaciones; aprobación y administración las consultan. | API y SPA |
| RN-17 | Un servicio del catálogo que ya tiene contratos no cambia de categoría, unidad ni moneda, porque el precio de referencia compara precios unitarios. | `proveedores` (catálogo e importación) |
| RN-18 | El precio de referencia usa los contratos de los últimos 24 meses del mismo rango de cantidad, ajustados por inflación. Con menos de 8 observaciones se marca de baja confianza. | `inteligencia/dominio/precios.py` |
| RN-19 | Alertas: sobreprecio si una línea vigente cuesta más que el P75; vencimiento a 30, 60 y 90 días (severidad alta, media e informativa); riesgo si la puntuación baja del umbral (40 por defecto) o cae más de 10 puntos en 3 meses. | `inteligencia/dominio/alertas.py` |
| RN-20 | La puntuación del proveedor va de 0 a 100 y se calcula con 12 meses de desempeño, con una vida media de 6 meses. Los pesos por defecto son: SLA 30, resolución 20, incidentes 20, entregas 15 y satisfacción 15. El administrador los puede cambiar. | `inteligencia/dominio/puntuacion.py` |
| RN-21 | Un modelo de precios nuevo solo se usa si su MAPE mejora el de la línea base. | `inteligencia/modelo.py` |

## 4. Stack

Se eligió por mérito y con costo cero (decisiones D2 y D6 del PRD).

| Capa | En uso | Por qué |
|---|---|---|
| Servicios | Python 3.13, FastAPI, Pydantic 2, SQLAlchemy 2 (asíncrono), Alembic, httpx | Tipado, validación en la frontera y migraciones versionadas |
| Inteligencia | scikit-learn, numpy y scipy | Un modelo por cuantiles basta para este volumen de datos |
| Mensajería | RabbitMQ 4.1 con aio-pika, outbox transaccional y consumidores idempotentes | Entrega fiable sin compartir bases (ADR-005) |
| Datos | PostgreSQL 17: una instancia, una base por servicio | Aislamiento con poca memoria (ADR-006) |
| Identidad | Keycloak 26 (OIDC, JWT RS256) | Protocolo estándar, migrable a Entra ID (ADR-004) |
| Interfaz | React 19, TypeScript, Vite, React Router, TanStack Query, Tailwind con shadcn/ui y Radix, Recharts | SPA accesible (revisada con axe, WCAG 2.2 AA) y modo claro/oscuro |
| Infraestructura | Docker Compose y Nginx como gateway | Un comando levanta todo (`uv run python infra/arrancar.py`) |
| Calidad | pytest, Hypothesis, Testcontainers, Vitest, Testing Library, axe-core, ruff, mypy (estricto), ESLint, Prettier y gitleaks | Pruebas de propiedades en el motor y de integración con bases reales |
| CI | GitHub Actions: lint, tipos, pruebas, construcción y prueba de humo del stack completo | Cada cambio se valida de punta a punta |

**Planeado, todavía sin usar:**
- el LLM local con Ollama (N2, ADR-003);
- observabilidad con OpenTelemetry y Grafana;
- pruebas E2E con Playwright, de carga con Locust y de seguridad con OWASP ZAP y Trivy;
- la publicación de imágenes en GitHub Container Registry.

**Frente al stack del documento base:**

| Documento base | Decisión | Motivo |
|---|---|---|
| Python, FastAPI, React, PostgreSQL, Docker, GitHub Actions, Scrum | Se conservan | Adecuados y sin costo |
| Azure OpenAI | Ollama local con API compatible con OpenAI | Costo cero; migrar es cambiar la URL y el modelo |
| Azure Machine Learning | scikit-learn con registro de modelos propio | El volumen de datos no justifica una plataforma de ML |
| Azure AI Search | Fuera de v1 | Solo serviría para buscar en los PDFs de contratos |
| Microsoft Entra ID | Keycloak (OIDC) | Mismo protocolo; migrable |
| Power BI | Fuera de v1 | Los datos quedan disponibles por API para conectarlo después |

## 5. Costos

- **Licencias:** $0. Todo el stack es de código abierto.
- **Infraestructura:** $0. Todo corre en un solo equipo con Docker. El de desarrollo es un Ryzen 5
  5600H con 14 GB de RAM; el stack completo usa unos 3 a 3.5 GB (PRD §2.4).
- **Datos:** simulados con un generador reproducible (semilla 42: 60 proveedores, 1,601 contratos
  y 2,980 registros de desempeño). No hay costo ni riesgo con datos reales.
- **Desarrollo:** 500 horas de residencia (4 periodos de 125 horas), de un desarrollador.
- **Despliegue:** en el host destino, `docker compose up -d` con las imágenes del proyecto. Una
  máquina virtual gratuita en la nube es opcional.
- **Migración a servicios administrados:** si PluriOne quisiera Azure, la ruta es cambiar
  configuración, no código:
  - Azure OpenAI en lugar de Ollama;
  - Entra ID en lugar de Keycloak;
  - Azure Database for PostgreSQL en lugar de la instancia local.

  Su costo depende del plan que contrate PluriOne y no se estima aquí.

## 6. Riesgos principales

| Riesgo | Mitigación |
|---|---|
| El tiempo restante no alcanza para todo el PRD | Replanificación del 15/10/2026 (PRD §6.6.1, ADR-010): primero el flujo de punta a punta, y la IA solo si sobra tiempo |
| Complejidad de los microservicios para un solo desarrollador | `libs/comun`, arranque en un comando y CI con el stack completo |
| Datos sintéticos que inflan las métricas | Variables ocultas con ruido, validación temporal y una «verdad oculta» que la plataforma nunca ve |
| Que el LLM interprete mal las ofertas (cuando llegue N2) | Formulario estructurado, confirmación obligatoria y evals para elegir el modelo (ADR-009) |
