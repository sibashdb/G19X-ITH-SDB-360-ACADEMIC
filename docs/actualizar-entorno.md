# Actualizar un entorno ya creado

Quien instala desde cero no necesita nada de esto: basta con `uv run python infra/arrancar.py`
(vea el README). Estas instrucciones son para un volumen de PostgreSQL o un realm de Keycloak
creados antes de que existiera algún servicio o ajuste, porque ambos solo se inicializan la
primera vez.

## Activar la administración en un entorno ya creado

El volumen de PostgreSQL y el realm de Keycloak solo se inicializan la primera vez. Si su entorno
ya existía antes de la administración, siga estos tres pasos, en este orden (en Git Bash, ejecute
antes `export MSYS_NO_PATHCONV=1`).

1. Agregue en `infra/.env` las tres variables de la administración (`ADMINISTRACION_DB_PASSWORD`,
   `ADMINISTRACION_DUENO_DB_PASSWORD` y `KEYCLOAK_ADMINISTRACION_SECRET`). Defina también las dos
   `INTELIGENCIA_*` y las dos `NEGOCIACION_*` (el `docker-compose.yml` las exige; vea las
   secciones de la inteligencia y de la negociación, más abajo) y vuelva a crear PostgreSQL y
   Keycloak para que las reciban:

   ```bash
   docker compose -f infra/docker-compose.yml up -d --wait postgres keycloak
   ```

2. Cree la base y configure Keycloak. Ambos comandos son idempotentes: puede repetirlos sin riesgo.
   El primero crea la base y sus dos usuarios. El segundo configura en Keycloak el cliente, los
   eventos, el correo y el tema.

   ```bash
   docker compose -f infra/docker-compose.yml exec -T postgres bash /docker-entrypoint-initdb.d/20-administracion.sh
   ```

   ```bash
   docker compose -f infra/docker-compose.yml exec -T keycloak bash /opt/keycloak/data/import/configurar-administracion.sh
   ```

3. Levante el resto del stack. Antes del paso 2, este comando falla porque la base de
   administración todavía no existe:

   ```bash
   docker compose -f infra/docker-compose.yml up -d --build --wait
   ```

## Activar la inteligencia en un entorno ya creado

Si su entorno ya existía antes del servicio de inteligencia, siga estos pasos, en este orden (en
Git Bash, ejecute antes `export MSYS_NO_PATHCONV=1`).

1. Agregue en `infra/.env` las dos variables de la inteligencia (cópielas de `infra/.env.example`)
   y vuelva a crear PostgreSQL para que las reciba:

   ```bash
   docker compose -f infra/docker-compose.yml up -d --wait postgres
   ```

2. Cree la base de la inteligencia y sus dos usuarios. El comando es idempotente:

   ```bash
   docker compose -f infra/docker-compose.yml exec -T postgres bash /docker-entrypoint-initdb.d/30-inteligencia.sh
   ```

3. Levante el resto del stack. El contenedor `rabbitmq-topologia` declara las colas y termina:

   ```bash
   docker compose -f infra/docker-compose.yml up -d --build --wait
   ```

4. Llene la copia local de la inteligencia con lo que ya estaba importado. Corra los dos comandos
   en este orden: el primero vuelve a publicar todos los eventos guardados y el segundo publica el
   estado actual del catálogo y del tipo de cambio. La instantánea va al final porque la copia se
   queda con lo último que recibe: si fuera antes, los eventos viejos que repite `--todo` (por
   ejemplo, el nombre de un servicio anterior a su última edición) la dejarían con datos
   desactualizados. Los servicios ignoran lo que ya recibieron (la Actividad no se duplica), así
   que repetirlos es seguro:

   ```bash
   docker compose -f infra/docker-compose.yml exec -T proveedores python -m proveedores.reproceso --todo
   ```

   ```bash
   docker compose -f infra/docker-compose.yml exec -T proveedores python -m proveedores.reproceso --instantanea
   ```

   Con el dataset por defecto, la copia tarda de uno a dos minutos en llenarse, según el equipo.
   Espere a que termine antes de correr la prueba de humo o de usar la plataforma: abra la consola
   de RabbitMQ (<http://localhost:15672>, usuario `plataforma` y la contraseña `RABBITMQ_PASSWORD`
   de `infra/.env`) y, en *Queues*, espere a que la cola `inteligencia.eventos` muestre 0 mensajes
   listos (*Ready*) y deje de recibir mensajes nuevos. Después, el modelo de precios se entrena
   solo.

## Activar la negociación en un entorno ya creado

Si su entorno ya existía antes del servicio de negociación, siga estos pasos, en este orden (en
Git Bash, ejecute antes `export MSYS_NO_PATHCONV=1`).

1. Agregue en `infra/.env` las dos variables de la negociación (cópielas de `infra/.env.example`)
   y vuelva a crear PostgreSQL para que las reciba:

   ```bash
   docker compose -f infra/docker-compose.yml up -d --wait postgres
   ```

2. Cree la base de la negociación y sus dos usuarios. El comando es idempotente:

   ```bash
   docker compose -f infra/docker-compose.yml exec -T postgres bash /docker-entrypoint-initdb.d/40-negociacion.sh
   ```

3. Levante el stack, construyendo la imagen nueva:

   ```bash
   docker compose -f infra/docker-compose.yml up -d --build --wait
   ```

4. Llene las copias de proveedores y servicios de la negociación con lo que ya estaba importado.
   Corra los dos comandos en este orden: primero `--todo` y después `--instantanea`. Los demás
   servicios ignoran lo que ya recibieron, así que repetirlos es seguro:

   ```bash
   docker compose -f infra/docker-compose.yml exec -T proveedores python -m proveedores.reproceso --todo
   ```

   ```bash
   docker compose -f infra/docker-compose.yml exec -T proveedores python -m proveedores.reproceso --instantanea
   ```

5. Espere a que termine antes de correr la prueba de humo o de crear una negociación: abra la
   consola de RabbitMQ (<http://localhost:15672>) y, en *Queues*, espere a que la cola
   `negociacion.eventos` muestre 0 mensajes listos (*Ready*). La cola `negociacion.eventos.dlq`
   debe quedar vacía.

## Tema de inicio de sesión en un realm ya importado

Keycloak importa el realm solo la primera vez. Si su volumen de PostgreSQL ya tenía el realm
`plataforma`, aplique el tema de inicio de sesión una sola vez (no borra datos). Primero, en
cualquier terminal:

```bash
docker compose -f infra/docker-compose.yml up -d --wait keycloak
```

Después, este comando. Sirve igual en Git Bash y en PowerShell porque no lleva comillas dobles, y
la contraseña viaja en la variable `KC_CLI_PASSWORD` dentro del contenedor: no aparece en la línea
de comandos ni en la lista de procesos. En **Git Bash**, ejecute antes `export MSYS_NO_PATHCONV=1`;
sin eso, Git Bash convierte `/opt/…` y `/tmp/…` en rutas de Windows y el comando falla.

```bash
docker compose -f infra/docker-compose.yml exec keycloak bash -c 'KC_CLI_PASSWORD=$KC_BOOTSTRAP_ADMIN_PASSWORD /opt/keycloak/bin/kcadm.sh config credentials --config /tmp/kcadm.config --server http://localhost:8080/auth --realm master --user admin && /opt/keycloak/bin/kcadm.sh update realms/plataforma --config /tmp/kcadm.config -s loginTheme=plataforma'
```

**Sin línea de comandos**: abra <http://localhost:8080/auth/admin/>, entre como `admin` (contraseña
`KEYCLOAK_ADMIN_PASSWORD` de `infra/.env`), elija el realm `plataforma` y vaya a
*Realm settings → Themes → Login theme*, seleccione `plataforma` y guarde.

## Quitar el OTP en un realm ya importado

Las versiones anteriores pedían OTP a `admin1` y `aprobador1`. Si su realm se importó entonces,
quíteselo una sola vez (solo retira la acción pendiente y la credencial OTP; no toca contraseñas
ni otros datos). El comando funciona igual en PowerShell y en Git Bash (en Git Bash, ejecute antes
`export MSYS_NO_PATHCONV=1`):

```bash
docker compose -f infra/docker-compose.yml exec -T keycloak bash /opt/keycloak/data/import/quitar-otp.sh
```

**Sin línea de comandos**: en <http://localhost:8080/auth/admin/>, realm `plataforma` →
*Users* → `admin1` → deje vacío *Required user actions* y, en *Credentials*, borre la de tipo
`otp`; repita con `aprobador1`.
