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
    # Servicios que se consultan al crear o editar un borrador, con el token del comprador.
    inteligencia_url: str = "http://localhost:8000"
    proveedores_url: str = "http://localhost:8000"
    # SMTP sin autenticación: Mailpit en desarrollo, solo en la red interna.
    smtp_host: str = "localhost"
    smtp_puerto: int = 1025
    smtp_remitente: str = "compras@plataforma.example"
    # Dirección pública de la plataforma, para el enlace del portal en las invitaciones.
    url_publica: str = "http://localhost:8080"
