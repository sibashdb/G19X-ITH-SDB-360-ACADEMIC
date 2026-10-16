# ADR-004: Keycloak (OIDC) en lugar de Entra ID o autenticación propia

- **Estado:** Aceptada
- **Fecha:** 2026-09-28

## Contexto

El brief mencionaba Entra ID. Una autenticación propia es riesgosa, y Entra ID requiere un tenant
de Azure.

## Decisión

Keycloak emite JWT RS256 y publica su JWKS. Cada servicio valida el token contra el JWKS
(`libs/comun/src/comun/auth.py`) y usa los roles del realm: `comprador`, `aprobador` y `admin`. La
administración gestiona usuarios con la API de Keycloak.

## Consecuencias

- Mismo protocolo que Entra ID: migrar es cambiar el emisor OIDC y el mapeo de roles.
- El realm incluido trae credenciales de prueba y solo sirve para desarrollo.
- El portal del proveedor no usa Keycloak: entra con un enlace personal, del que solo se guarda el
  hash.
