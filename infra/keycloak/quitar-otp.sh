#!/usr/bin/env bash
# Quita el OTP de los usuarios de desarrollo en un realm ya importado (Keycloak no reimporta).
# Uso (desde la raíz del repositorio):
#   docker compose -f infra/docker-compose.yml exec -T keycloak bash /opt/keycloak/data/import/quitar-otp.sh
# La contraseña del administrador se lee del entorno del propio contenedor; no se escribe en ningún lado.
set -euo pipefail

kcadm=/opt/keycloak/bin/kcadm.sh
config=/tmp/kcadm.config

KC_CLI_PASSWORD="$KC_BOOTSTRAP_ADMIN_PASSWORD" "$kcadm" config credentials --config "$config" \
  --server http://localhost:8080/auth --realm master --user admin

for usuario in admin1 aprobador1; do
  id=$("$kcadm" get users --config "$config" -r plataforma -q exact=true -q "username=$usuario" \
    --fields id --format csv --noquotes)
  if [ -z "$id" ]; then
    echo "No existe $usuario; se omite."
    continue
  fi
  "$kcadm" update "users/$id" --config "$config" -r plataforma -s 'requiredActions=[]'
  "$kcadm" get "users/$id/credentials" --config "$config" -r plataforma --fields id,type \
    --format csv --noquotes | while IFS=, read -r a b; do
      if [ "$b" = "otp" ]; then credencial=$a
      elif [ "$a" = "otp" ]; then credencial=$b
      else continue
      fi
      "$kcadm" delete "users/$id/credentials/$credencial" --config "$config" -r plataforma
    done
  echo "OTP retirado de $usuario."
done
