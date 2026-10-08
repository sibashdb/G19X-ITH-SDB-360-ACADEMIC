#!/bin/bash
# Base de datos del servicio de administración con dos usuarios: el dueño (corre las migraciones)
# y el de la aplicación (los permisos por tabla los da la migración; sin UPDATE ni DELETE sobre la
# bitácora). Es idempotente. Corre solo en volúmenes nuevos; en un volumen existente:
#   docker compose -f infra/docker-compose.yml exec -T postgres bash /docker-entrypoint-initdb.d/20-administracion.sh
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" --dbname postgres <<EOSQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'administracion_dueno') THEN
    CREATE ROLE administracion_dueno LOGIN PASSWORD '${ADMINISTRACION_DUENO_DB_PASSWORD}';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'administracion') THEN
    CREATE ROLE administracion LOGIN PASSWORD '${ADMINISTRACION_DB_PASSWORD}';
  END IF;
END
\$\$;
SELECT 'CREATE DATABASE administracion_db OWNER administracion_dueno'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'administracion_db')\gexec
REVOKE CONNECT ON DATABASE administracion_db FROM PUBLIC;
GRANT CONNECT ON DATABASE administracion_db TO administracion;
EOSQL
