import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// /api 요청은 FastAPI 백엔드(8000)로 프록시 → CORS 문제 회피
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
