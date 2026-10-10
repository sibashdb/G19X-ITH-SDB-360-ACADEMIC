/// <reference types="vitest/config" />
import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": resolve(import.meta.dirname, "./src") },
  },
  server: {
    port: 5173,
    // En desarrollo la API se consume a través del gateway (mismo camino que en producción).
    proxy: { "/api": "http://localhost:8080" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/setupPruebas.ts"],
    // Las pruebas de formularios largos (Catálogo, Usuarios) rozan los 5 s por defecto cuando
    // todos los archivos corren en paralelo.
    testTimeout: 15_000,
  },
})
