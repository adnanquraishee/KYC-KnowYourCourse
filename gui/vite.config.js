import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // three is pulled in directly and again through @react-three/*; without this
  // the browser loads two copies and logs "Multiple instances of Three.js".
  resolve: {
    dedupe: ['three', 'react', 'react-dom'],
  },
  optimizeDeps: {
    include: ['three', '@react-three/fiber', '@react-three/drei'],
  },
  server: {
    port: 5300,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:5350',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:5350',
        changeOrigin: true,
      },
      '/chat': {
        target: 'http://localhost:5350',
        changeOrigin: true,
      },
      '/upload': {
        target: 'http://localhost:5350',
        changeOrigin: true,
      },
    },
  },
})
