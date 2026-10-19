import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// 前端工作台：开发环境通过代理转发到后端，避免 CORS，也方便切换真实/模拟数据。
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
