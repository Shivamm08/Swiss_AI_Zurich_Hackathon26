import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// All API calls go to /api/*. In dev, Vite proxies them to the backend, so the
// frontend never needs CORS or a hard-coded backend URL.
// Local:  backend on http://localhost:8000 (default)
// Docker: VITE_PROXY_TARGET=http://backend:8000 (set in docker-compose.yml)
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
