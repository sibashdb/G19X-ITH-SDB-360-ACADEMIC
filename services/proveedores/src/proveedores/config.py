from comun.config import ConfiguracionBase


class Configuracion(ConfiguracionBase):
    nombre_servicio: str = "proveedores"
    database_url: str = "postgresql+asyncpg://proveedores:proveedores@localhost:5432/proveedores_db"
