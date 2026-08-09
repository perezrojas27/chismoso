import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const base = process.env.VITE_PUBLIC_PATH || '/'

export default defineConfig({
  base,
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8004',
        changeOrigin: true,
      },
    },
  },
})
