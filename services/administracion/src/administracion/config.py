from comun.config import ConfiguracionBase


class Configuracion(ConfiguracionBase):
    nombre_servicio: str = "administracion"
    # Usuario de la aplicación: sin UPDATE ni DELETE sobre la bitácora.
    database_url: str = (
        "postgresql+asyncpg://administracion:administracion@localhost:5432/administracion_db"
    )
    # Dueño del esquema: solo para correr las migraciones.
    database_url_migraciones: str = (
        "postgresql+asyncpg://administracion_dueno:administracion_dueno"
        "@localhost:5432/administracion_db"
    )
    keycloak_url: str = "http://localhost:8080/auth"
    keycloak_realm: str = "plataforma"
    keycloak_cliente: str = "administracion"
    keycloak_secreto: str = ""
    url_app: str = "http://localhost:8080/"
    buzon_url: str = ""
    intervalo_eventos_s: int = 30
    # Las pruebas que levantan el ciclo de vida lo apagan: no hay RabbitMQ en ellas.
    consumir_eventos: bool = True
    proveedores_url: str = "http://localhost:8000"
    inteligencia_url: str = "http://localhost:8000"
    negociacion_url: str = "http://localhost:8000"
    mailpit_url: str = "http://localhost:8025"
    rabbitmq_api_url: str = "http://localhost:15672/api"
    version_app: str = "desarrollo"
