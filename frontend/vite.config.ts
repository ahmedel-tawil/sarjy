import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('src', import.meta.url)),
    },
  },
  // In development the gateway runs separately on 8080; production serves both from one origin.
  server: {
    proxy: {
      '/health': 'http://127.0.0.1:8080',
      '/voices': 'http://127.0.0.1:8080',
      '/ws': { target: 'ws://127.0.0.1:8080', ws: true },
    },
  },
})
