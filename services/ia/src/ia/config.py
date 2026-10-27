from comun.config import ConfiguracionBase


class Configuracion(ConfiguracionBase):
    nombre_servicio: str = "ia"
    database_url: str = ""  # sin base de datos: no guarda estado
    # API compatible con OpenAI (Ollama: http://host.docker.internal:11434/v1). Vacía = apagado:
    # negociacion usa las plantillas y la plataforma negocia igual (spec §3, «Degradación»).
    llm_url: str = ""
    llm_modelo: str = "qwen2.5:3b"  # el que eligieron los evals (ADR-009)
    # Cubre la carga en frío del modelo, si Ollama lo descargó por falta de uso, dentro de los 18 s
    # que tiene el turno en negociacion (ia_presupuesto_s).
    llm_espera_s: float = 15.0
