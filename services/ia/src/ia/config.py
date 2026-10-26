from comun.config import ConfiguracionBase


class Configuracion(ConfiguracionBase):
    nombre_servicio: str = "ia"
    database_url: str = ""  # sin base de datos: no guarda estado
    # API compatible con OpenAI (Ollama: http://host.docker.internal:11434/v1). Vacía = apagado:
    # negociacion usa las plantillas y la plataforma negocia igual (spec §3, «Degradación»).
    llm_url: str = ""
    llm_modelo: str = "llama3.2:3b"
    llm_espera_s: float = 8.0
