import { defineConfig, devices } from '@playwright/test'

// Recorridos en un navegador real contra el stack levantado (uv run python infra/arrancar.py):
// por ahora, las capturas del manual de usuario; desde el 12/11, las pruebas de extremo a extremo.
export default defineConfig({
  testDir: 'e2e',
  // .e2e.ts y no .spec.ts: Vitest toma los .spec.ts como pruebas unitarias.
  testMatch: '*.e2e.ts',
  timeout: 180_000,
  workers: 1,
  reporter: 'list',
  use: {
    ...devices['Desktop Chrome'],
    baseURL: 'http://localhost:8080',
    viewport: { width: 1440, height: 900 },
    colorScheme: 'light',
    locale: 'es-MX',
    timezoneId: 'America/Mexico_City',
  },
})
