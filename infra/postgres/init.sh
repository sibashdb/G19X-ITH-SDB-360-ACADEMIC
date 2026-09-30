#!/bin/bash
# Crea una base de datos y un usuario por servicio. Solo corre con el volumen vacío.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<EOSQL
CREATE USER proveedores WITH PASSWORD '${PROVEEDORES_DB_PASSWORD}';
CREATE DATABASE proveedores_db OWNER proveedores;
REVOKE CONNECT ON DATABASE proveedores_db FROM PUBLIC;

CREATE USER keycloak WITH PASSWORD '${KEYCLOAK_DB_PASSWORD}';
CREATE DATABASE keycloak_db OWNER keycloak;
REVOKE CONNECT ON DATABASE keycloak_db FROM PUBLIC;
EOSQL
