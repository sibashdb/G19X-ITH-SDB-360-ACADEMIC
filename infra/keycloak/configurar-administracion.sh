#!/usr/bin/env bash
# Aplica en un realm ya importado lo que necesita el servicio de administración (Keycloak no
# reimporta): eventos de inicio de sesión, SMTP hacia Mailpit, tema de correos y el cliente
# "administracion" con su cuenta de servicio. Es idempotente.
# Uso (desde la raíz del repositorio):
#   docker compose -f infra/docker-compose.yml exec -T keycloak bash /opt/keycloak/data/import/configurar-administracion.sh
# La contraseña del administrador y el secreto del cliente se leen del entorno del contenedor, nunca
# como argumentos: la contraseña llega a kcadm en la variable KC_CLI_PASSWORD de esa sola orden, y
# el secreto va dentro del JSON del cliente, que kcadm recibe por la entrada estándar (-f -).
set -euo pipefail

kcadm=/opt/keycloak/bin/kcadm.sh
config=/tmp/kcadm.config
realm=plataforma

KC_CLI_PASSWORD="$KC_BOOTSTRAP_ADMIN_PASSWORD" "$kcadm" config credentials --config "$config" \
  --server http://localhost:8080/auth --realm master --user admin

"$kcadm" update events/config --config "$config" -r "$realm" \
  -s eventsEnabled=true -s eventsExpiration=2592000 \
  -s 'enabledEventTypes=["LOGIN","LOGIN_ERROR","LOGOUT"]'
echo "Eventos de inicio de sesión activados (30 días)."

"$kcadm" update "realms/$realm" --config "$config" -s emailTheme=plataforma \
  -s smtpServer.host=mailpit -s smtpServer.port=1025 \
  -s smtpServer.from=no-responder@pluri.one.test -s smtpServer.fromDisplayName=PluriOne \
  -s smtpServer.auth=false -s smtpServer.ssl=false -s smtpServer.starttls=false
echo "Correo hacia Mailpit y tema de correos configurados."

cliente_json() {
  printf '{"clientId":"administracion","name":"Servicio de administración","enabled":true,"publicClient":false,"clientAuthenticatorType":"client-secret","secret":"%s","standardFlowEnabled":false,"implicitFlowEnabled":false,"directAccessGrantsEnabled":false,"serviceAccountsEnabled":true}' \
    "$KEYCLOAK_ADMINISTRACION_SECRET"
}

id=$("$kcadm" get clients --config "$config" -r "$realm" -q clientId=administracion \
  --fields id --format csv --noquotes)
if [ -z "$id" ]; then
  cliente_json | "$kcadm" create clients --config "$config" -r "$realm" -f -
  echo "Cliente administracion creado."
else
  cliente_json | "$kcadm" update "clients/$id" --config "$config" -r "$realm" -f -
  echo "Cliente administracion ya existía; configuración y secreto actualizados."
fi

"$kcadm" add-roles --config "$config" -r "$realm" --uusername service-account-administracion \
  --cclientid realm-management --rolename view-users --rolename manage-users \
  --rolename view-events
echo "Permisos de la cuenta de servicio: view-users, manage-users, view-events."
