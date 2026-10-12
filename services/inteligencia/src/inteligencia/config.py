from pathlib import Path

from comun.config import ConfiguracionBase


class Configuracion(ConfiguracionBase):
    nombre_servicio: str = "inteligencia"
    # Usuario de la aplicación: sin DELETE en ninguna tabla.
    database_url: str = (
        "postgresql+asyncpg://inteligencia:inteligencia@localhost:5432/inteligencia_db"
    )
    # Dueño del esquema: solo para correr las migraciones.
    database_url_migraciones: str = (
        "postgresql+asyncpg://inteligencia_dueno:inteligencia_dueno@localhost:5432/inteligencia_db"
    )
    # Las pruebas lo apagan: no hay RabbitMQ en ellas.
    usar_rabbitmq: bool = True
    entrenamiento_automatico: bool = True
    directorio_modelos: Path = Path("modelos")
