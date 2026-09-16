import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// Config dedicada aos testes de componente (Vitest + jsdom). Não reusa o
// vite.config.js para não puxar os plugins de dev (visual editor etc.).
// Os testes ficam em tests/frontend/ (ver regra do CLAUDE.md); o alias '@'
// continua apontando para client/src.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      // Os testes ficam fora de client/, então seus imports "bare" não acham
      // client/node_modules sozinhos — apontamos os pacotes de teste para cá.
      '@testing-library/react': path.resolve(__dirname, 'node_modules/@testing-library/react'),
      '@testing-library/jest-dom': path.resolve(__dirname, 'node_modules/@testing-library/jest-dom'),
      '@testing-library/user-event': path.resolve(__dirname, 'node_modules/@testing-library/user-event'),
    },
  },
  // Os testes ficam em ../tests/frontend (fora de client/); libera o Vite a
  // ler/transformar arquivos a partir da raiz do repositório.
  server: {
    fs: { allow: [path.resolve(__dirname, '..')] },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.js'],
    include: ['../tests/frontend/**/*.test.{js,jsx}'],
    css: false,
  },
});
