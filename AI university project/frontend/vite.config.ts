import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://api:8000',
        changeOrigin: true,
      },
      '/health': 'http://api:8000',
      '/docs': 'http://api:8000',
      '/openapi.json': 'http://api:8000',
    },
  },
});
