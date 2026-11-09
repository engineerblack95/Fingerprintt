import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backendHttp = 'http://127.0.0.1:8000';

// The dev server and `vite preview` both need to reach the Django API,
// uploaded photos and the dashboard WebSocket on the same origin.
const proxy = {
  '/api': {
    target: backendHttp,
    changeOrigin: true,
  },
  '/media': {
    target: backendHttp,
    changeOrigin: true,
  },
  '/ws': {
    target: 'ws://127.0.0.1:8000',
    ws: true,
    changeOrigin: true,
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: 'localhost',
    proxy,
  },
  preview: {
    port: 4173,
    host: 'localhost',
    proxy,
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        // Keep the charting library out of the main app chunk so the login
        // screen and shell stay small and cache independently.
        manualChunks: {
          charts: ['recharts'],
          react: ['react', 'react-dom', 'react-router-dom'],
        },
      },
    },
  },
});
