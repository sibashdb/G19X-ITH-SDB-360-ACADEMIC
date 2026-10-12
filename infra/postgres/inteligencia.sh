#!/bin/bash
# Base de datos del servicio de inteligencia con dos usuarios: el dueño (corre las migraciones)
# y el de la aplicación (los permisos por tabla los da la migración; nunca borra). Es
# idempotente. Corre solo en volúmenes nuevos; en un volumen existente:
#   docker compose -f infra/docker-compose.yml exec -T postgres bash /docker-entrypoint-initdb.d/30-inteligencia.sh
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" --dbname postgres <<EOSQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'inteligencia_dueno') THEN
    CREATE ROLE inteligencia_dueno LOGIN PASSWORD '${INTELIGENCIA_DUENO_DB_PASSWORD}';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'inteligencia') THEN
    CREATE ROLE inteligencia LOGIN PASSWORD '${INTELIGENCIA_DB_PASSWORD}';
  END IF;
END
\$\$;
SELECT 'CREATE DATABASE inteligencia_db OWNER inteligencia_dueno'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'inteligencia_db')\gexec
REVOKE CONNECT ON DATABASE inteligencia_db FROM PUBLIC;
GRANT CONNECT ON DATABASE inteligencia_db TO inteligencia;
EOSQL
