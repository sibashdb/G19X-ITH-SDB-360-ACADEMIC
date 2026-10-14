from comun.config import ConfiguracionBase


class Configuracion(ConfiguracionBase):
    nombre_servicio: str = "negociacion"
    # Usuario de la aplicación: nunca cambia ni borra la bitácora, los mensajes ni las ofertas.
    database_url: str = "postgresql+asyncpg://negociacion:negociacion@localhost:5432/negociacion_db"
    # Dueño del esquema: solo para correr las migraciones.
    database_url_migraciones: str = (
        "postgresql+asyncpg://negociacion_dueno:negociacion_dueno@localhost:5432/negociacion_db"
    )
    # Las pruebas lo apagan: no hay RabbitMQ en ellas.
    usar_rabbitmq: bool = True
