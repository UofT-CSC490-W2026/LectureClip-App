import { defineConfig } from 'vitest/config'
import type { InlineConfig } from 'vitest/node'
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const coverage = {
  provider: 'istanbul',
  all: false,
  reporter: ['text', 'html', 'lcov', 'json-summary'],
  reportsDirectory: './coverage',
  include: ['src/**/*.{ts,tsx}'],
  exclude: ['src/main.tsx', 'src/lib/types.ts', 'src/test/**'],
} as NonNullable<InlineConfig['coverage']> & { all: boolean }

// https://vite.dev/config/
export default defineConfig({
  define: { global: 'globalThis' },
  plugins: [tailwindcss(), react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
    coverage,
  },
})
