#!/bin/bash
# Base de datos del servicio de negociación con dos usuarios: el dueño (corre las migraciones)
# y el de la aplicación (los permisos por tabla los da la migración; el historial es de solo
# inserción). Es idempotente. Corre solo en volúmenes nuevos; en un volumen existente:
#   docker compose -f infra/docker-compose.yml exec -T postgres bash /docker-entrypoint-initdb.d/40-negociacion.sh
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" --dbname postgres <<EOSQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'negociacion_dueno') THEN
    CREATE ROLE negociacion_dueno LOGIN PASSWORD '${NEGOCIACION_DUENO_DB_PASSWORD}';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'negociacion') THEN
    CREATE ROLE negociacion LOGIN PASSWORD '${NEGOCIACION_DB_PASSWORD}';
  END IF;
END
\$\$;
SELECT 'CREATE DATABASE negociacion_db OWNER negociacion_dueno'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'negociacion_db')\gexec
REVOKE CONNECT ON DATABASE negociacion_db FROM PUBLIC;
GRANT CONNECT ON DATABASE negociacion_db TO negociacion;
EOSQL
