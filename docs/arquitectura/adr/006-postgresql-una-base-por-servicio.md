# ADR-006: Una instancia de PostgreSQL con una base y un usuario por servicio

- **Estado:** Aceptada
- **Fecha:** 2026-09-28

## Contexto

Con microservicios, cada servicio debe ser dueño de sus datos. Una instancia por servicio no cabe
en el equipo de desarrollo (14 GB de RAM).

## Decisión

Una sola instancia de PostgreSQL. Cada servicio tiene su base y un usuario que solo puede entrar a
ella. En `administracion`, `inteligencia` y `negociacion` hay dos usuarios: el dueño, que solo crea
y migra tablas con Alembic, y el de la aplicación, con permisos mínimos. Por ejemplo, la bitácora
es de solo inserción.

## Consecuencias

- Aislamiento real de datos con poca memoria (unos 200 MB).
- Separarlos después en instancias distintas es cambiar la URL de conexión.
- Ninguna consulta cruza bases: lo compartido viaja por eventos.
