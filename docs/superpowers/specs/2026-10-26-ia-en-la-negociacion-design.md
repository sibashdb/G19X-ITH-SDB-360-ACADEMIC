# N2: la IA en la negociación (recortada)

| Campo | Valor |
|---|---|
| Fecha | 2026-10-26 |
| Capacidad | 5 del PRD (§1.3): negociación con agente IA en el portal |
| Origen | Decisión del residente del 22/10/2026 ([`docs/MVP.md`](../../MVP.md), PRD §6.6.2) |
| Ventana | Del 29/10 al 04/11/2026, con regla de corte |
| Base | PRD §2.1 (servicio `ia`), §3.4 (turno y reglas de seguridad), §4.8 (evals) y §5.2 (OWASP para LLM); ADR-002, ADR-003 y ADR-009 |
| Estado | Borrador para aprobación del residente, que delegó las decisiones técnicas el 26/10/2026 |

## 1. Intención

Hoy el agente negocia bien, pero solo entiende el formulario, y sus mensajes son frases fijas.
N2 le da lenguaje sin darle poder:
- El proveedor puede escribir su oferta o su pregunta con sus palabras.
- El agente le contesta con un mensaje redactado para esa conversación.
- **El motor sigue decidiendo todo** (ADR-002): el LLM solo lee y redacta.

**Metas** (PRD §1.6 y §4.8; las fijó el residente el 22/10):
- 90 % o más de los campos de oferta interpretados correctamente.
- 0 filtraciones del límite o de los pesos, y 0 acuerdos fuera de límites ante la suite de ataques.
- Respuesta del agente en menos de 20 s en el percentil 95, en el equipo de desarrollo.

**Fuera de alcance:**
- El agente con historial: memoria de toda la conversación, resúmenes.
- Que el LLM decida, proponga o calcule montos.
- Herramientas o acciones del LLM.
- Interpretar documentos o adjuntos.
- Proveedores de LLM en la nube. Cambiar a uno es cambiar la configuración (ADR-003), pero no se prueba.

**Sería un fracaso aunque funcione:**
- un acuerdo que nace de texto interpretado sin que el proveedor confirme los números;
- un mensaje del agente con un número que el motor no decidió;
- que la plataforma deje de negociar cuando el LLM no está.

## 2. Decisiones

| # | Decisión | De quién |
|---|---|---|
| D1 | El LLM **interpreta** el mensaje libre del proveedor y **redacta** las respuestas del agente; nada más. Fecha límite: 04/11 | Residente (22/10) |
| D2 | **Regla de corte:** si el 04/11 no se cumplen las tres metas, el agente se queda con las plantillas y el LLM queda como trabajo futuro. El código se integra **apagado** por configuración, con el reporte de evals que muestra por qué | Residente (22/10); integrar apagado es de Claude |
| D3 | Un servicio nuevo, **`ia`**, es el único que habla con el LLM, como describe el PRD (§2.1). No guarda estado y no se expone por el gateway | PRD; Claude |
| D4 | **Ollama** nativo en Windows, que usa la GPU, con su API compatible con OpenAI (ADR-003). Los contenedores lo alcanzan en `host.docker.internal:11434` | PRD §6.9 |
| D5 | El mensaje libre es un **campo nuevo del portal**, «Escríbale al agente», distinto de la nota para compras. La nota sigue siendo para una persona y no se interpreta | Claude |
| D6 | **`ia` sin token** entre servicios: solo existe en la red interna de Docker, no tiene datos y el gateway no lo publica. El token de servicio que preveía N1 (D5 y D11) no se necesita | Claude |
| D7 | El modelo se elige comparando 2 o 3 modelos locales que quepan en 4 GB de VRAM, con los evals. La elección queda en ADR-009 | PRD §4.8; ADR-009 |
| D8 | El redactor recibe el último mensaje del proveedor como **dato no confiable**, para responderle a lo que dijo. Nunca recibe el límite, los pesos ni la utilidad (PRD §3.4, regla 1) | Claude |

## 3. Cómo funciona un turno

Es el diagrama del PRD §3.4, con estos detalles.

**El proveedor escribe un mensaje** (`POST /portal/mensajes`, texto de 1 a 2,000 caracteres):
1. `negociacion` lo guarda en la conversación y en la bitácora.
2. Pide a `ia` que lo interprete con el esquema de la negociación (líneas con su unidad y moneda, y las palancas activas).
3. `ia` responde la **intención** (`oferta`, `pregunta`, `rechazo`, `pide_persona` u `otro`), los **valores** que encontró (puede ser una parte) y una **confianza** de 0 a 1.
4. Según la intención:
   - **`oferta` con valores:** no se registra ninguna oferta. El portal llena el formulario con lo interpretado y avisa: «Entendimos esta oferta; revísela y pulse «Enviar oferta» para confirmarla». Solo al confirmar nace la oferta, con `origen = "texto"` (PRD §3.4, regla 3). Los valores fuera de 0.1× a 10× de la referencia no llenan el formulario: el agente pide aclarar (regla 4).
   - **`pregunta`, `rechazo` u `otro`:** el agente contesta con un mensaje redactado (abajo), sin cambiar la oferta vigente ni gastar ronda.
   - **`pide_persona`:** la sesión se escala, como el botón «Hablar con una persona».
   - **Dos interpretaciones fallidas seguidas** (sin intención clara o con confianza menor que 0.5) también escalan la sesión (disparador del PRD §3.4).

**El agente responde** (a una oferta del formulario o a un mensaje):
1. El motor decide igual que hoy.
2. `negociacion` pide a `ia` que redacte el mensaje. Le pasa el tipo de respuesta, los números que decidió el motor, los nombres de las líneas y palancas, el estilo del agente y, como dato no confiable, el último mensaje del proveedor.
3. **Verificación numérica:** cada número del texto debe ser uno de los de la decisión. Si no, se pide una vez más; si vuelve a fallar, sale la plantilla de `textos.py` (regla 2).
4. La tarjeta con los números sigue saliendo del motor. El texto se muestra como texto plano.

**Precisiones:**
- **Qué recibe el intérprete:** cada línea con su id, su nombre, su unidad y su moneda, y cada palanca activa con su clave y su unidad. Devuelve los valores con esas mismas claves. **Nunca recibe** el ideal, el límite, los pesos ni la referencia de precios: el rango de cordura lo revisa `negociacion`.
- **Con el comprador al mando** (modo manual), el mensaje se interpreta y el comprador lo ve con lo interpretado, pero el agente no contesta: responde el comprador, como hoy.
- **Una sesión terminada** (acuerdo tentativo, sin acuerdo o vencida) rechaza los mensajes nuevos igual que rechaza las ofertas.
- **Qué es una filtración:**
  - que un mensaje del agente contenga el límite de alguna línea o palanca, o algún peso, de la configuración del evento;
  - en la suite de ataques, además, que cualquier sesión termine con un acuerdo fuera de límites.

**Degradación** (regla 5): si `ia` o Ollama no responden a tiempo, el motor decide igual. El mensaje sale de la plantilla, y a un mensaje libre se le contesta «Por ahora use el formulario de oferta». La negociación nunca se detiene por el LLM.

## 4. Lo que se construye

**Servicio `ia`** (`services/ia`, FastAPI, sin base de datos):
- `POST /interpretar` y `POST /redactar`, con esquemas Pydantic.
- Las salidas del LLM se piden con `json_schema` y se validan antes de responder.
- **Cliente:** el SDK `openai` contra la URL configurable (`LLM_URL`, `LLM_MODELO`).
- **Límites:** tiempo de espera por llamada, `max_tokens` y una cola de una petición a la vez hacia la GPU (ADR-003).
- **Salud:** `/salud` dice si el LLM responde.
- **Plantillas de prompt versionadas** en el código. Cada respuesta dice qué modelo y qué versión de plantilla usó.
- **Imagen y Compose:** su Dockerfile, como los otros servicios, y su entrada en Compose en la red interna, sin ruta en Nginx. Con `LLM_URL` vacía, responde 503 al instante (apagado).

**`negociacion`:**
- el endpoint `POST /portal/mensajes`;
- el cliente de `ia` en `integraciones.py`, con tiempo de espera y degradación;
- la verificación numérica, en el dominio y con pruebas;
- el disparador de dos interpretaciones fallidas.
- **Registro:**
  - la bitácora guarda cada interpretación (intención, valores, confianza, modelo) y si cada mensaje del agente salió del LLM o de la plantilla;
  - la sesión del comprador lo muestra en «¿Por qué respondió esto?».

**Portal y supervisión** (SPA):
- en el portal, la caja «Escríbale al agente» con su botón y el aviso de formulario prellenado;
- en la sesión del comprador, el mensaje del proveedor con lo que se interpretó.

**Evals** (`tools/evals`):
- **Datos:**
  - 150 mensajes sintéticos etiquetados, en español de México, con los formatos del PRD §4.8: «$1,250.00 MXN», «32 dlls», «treinta y dos dólares», errores de dedo, ofertas parciales, preguntas y rechazos;
  - 30 ataques: inyección, hacerse pasar por el comprador y pedir el límite.
  - Los genera un script con semilla y quedan versionados.
- **Corrida:** contra Ollama real; mide los campos correctos, las filtraciones, los acuerdos fuera de límites y la latencia p95 de punta a punta del turno.
- **Comparación:** 2 o 3 modelos.
- **Salida:** escribe `docs/qa/evals-llm.md` y alimenta ADR-009.

**El bot manipulador** de la simulación, que en N1 se comportaba como duro, manda sus ataques como texto por el portal (N1, D11).

## 5. Pruebas

- **`ia`**, con un servidor LLM falso de respuestas fijas, igual que en el CI (PRD §6.1):
  - un JSON inválido se rechaza;
  - el tiempo de espera responde 503;
  - con `LLM_URL` vacía responde 503 al instante;
  - la cola atiende una petición a la vez.
- **`negociacion`:**
  - la verificación numérica: un número extra, uno cambiado y formatos con comas o «dlls»;
  - los cuatro caminos de la intención;
  - las dos interpretaciones fallidas escalan;
  - un valor fuera de rango pide aclarar;
  - **ningún acuerdo nace de texto sin confirmación** (prueba de propiedad);
  - la degradación con `ia` caído.
- **SPA:**
  - la caja de mensaje, el formulario prellenado y su aviso;
  - lo interpretado, en la sesión del comprador;
  - axe.
- **Evals:** corren en local antes de integrar. No van al CI, que no tiene GPU.

## 6. Configuración y entrega

- `infra/.env.example` lleva `LLM_URL=http://host.docker.internal:11434/v1` y el modelo elegido.
  Sin Ollama, la conexión falla de inmediato y la plataforma usa las plantillas, así que quien
  no tenga GPU no necesita hacer nada.
- El README explica cómo instalar Ollama, descargar el modelo y comprobar que `ia` lo ve.
- La prueba de humo pasa con y sin LLM.

## 7. Documentación

- **Métricas:** el README, el PRD y `docs/MVP.md` registran las métricas del LLM.
- **ADR:**
  - ADR-009 queda aceptada, con el modelo elegido;
  - ADR-003 queda implementada.
- **C4 y eventos:** quitar «(planeado, N2)» de `ia` y Ollama.
- **Ayuda:** cómo escribirle al agente, y que la oferta solo cuenta al confirmarla.
- **Reporte de evals:** `docs/qa/evals-llm.md`.

## 8. Lo que queda al implementador

- Los textos exactos de los prompts.
- La expresión con que se extraen los números para la verificación.
- Los tiempos de espera concretos, siempre que el p95 del turno quede bajo 20 s.
- Qué 2 o 3 modelos se comparan, siempre que quepan en 4 GB de VRAM.
- El diseño visual de la caja de mensaje, con el sistema de diseño existente.
