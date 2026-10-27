# ADR-003: LLM local con Ollama detrás de una API compatible con OpenAI

- **Estado:** Implementada (N2, 26/10/2026)
- **Fecha:** 2026-09-28

## Contexto

El brief proponía Azure OpenAI, pero el presupuesto de infraestructura es cero (decisión D6 del
PRD).

## Decisión

El servicio `ia` es el único que habla con el LLM, a través de una API compatible con OpenAI
servida por Ollama en local. Cambiar a Azure OpenAI u otro proveedor es cambiar la URL y el modelo
por configuración (`LLM_URL` y `LLM_MODELO`).

## Consecuencias

- Sin costo y sin datos fuera del equipo.
- La GPU de desarrollo (4 GB) atiende una petición a la vez: `ia` las pone en cola (un semáforo
  de una plaza) y precarga el modelo al arrancar, para que la primera respuesta no pague la carga
  en frío.
- Ollama corre en el anfitrión, fuera de Docker, y los contenedores lo alcanzan en
  `host.docker.internal`. Con `LLM_URL` vacía, `ia` responde 503 y el agente usa sus plantillas.
- `ia` pide cada respuesta con `response_format` de tipo JSON Schema y temperatura 0, así que el
  formato no depende de que el modelo lo respete por su cuenta.
- El modelo se eligió con los evals ([ADR-009](009-eleccion-del-llm-por-evals.md)).
