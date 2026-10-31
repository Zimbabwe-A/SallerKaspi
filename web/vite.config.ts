import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Запросы /api уходят на Python-сервер — CORS в разработке не нужен.
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
