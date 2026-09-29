"""Configuración común leída de variables de entorno (o de un archivo .env)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfiguracionBase(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    nombre_servicio: str
    database_url: str
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    oidc_issuer: str = "http://localhost:8080/auth/realms/plataforma"
    oidc_jwks_url: str = (
        "http://localhost:8080/auth/realms/plataforma/protocol/openid-connect/certs"
    )
    oidc_audience: str = "plataforma-api"
    root_path: str = ""
    log_level: str = "INFO"
