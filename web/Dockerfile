# Contexto: raíz del repositorio. Construye la SPA y la sirve desde el gateway Nginx.
FROM node:26-alpine AS construccion
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.29-alpine
COPY infra/nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=construccion /web/dist /usr/share/nginx/html
EXPOSE 8080
