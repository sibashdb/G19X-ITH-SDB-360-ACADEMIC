import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

// Colores literales: hex de 3 a 8 dígitos o funciones de color.
const COLOR_LITERAL = '/#[0-9a-fA-F]{3,8}\\b|\\b(rgba?|hsla?|oklch)\\(/'
const MENSAJE_COLOR =
  'Use los tokens del sistema de diseño (p. ej. text-destructive o var(--chart-1)), no colores literales.'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  {
    // Las pantallas solo usan los tokens de web/src/index.css.
    files: ['src/paginas/**/*.{ts,tsx}', 'src/componentes/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-syntax': [
        'error',
        { selector: `Literal[value=${COLOR_LITERAL}]`, message: MENSAJE_COLOR },
        { selector: `TemplateElement[value.raw=${COLOR_LITERAL}]`, message: MENSAJE_COLOR },
      ],
    },
  },
])
