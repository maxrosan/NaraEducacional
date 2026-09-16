#!/usr/bin/env node
// Copia assets de imagem usados na geração de relatórios (ex.: mascote da
// capa "Com a Nara") para o diretório estático do backend, onde o serviço
// de geração de PDF os referencia via MASCOTE_IMG_URL (relatorio_capa.py).
// Fonte de verdade permanece em client/public/.
//
// Mesmo padrão de copy-pdf-css.js — adicione aqui qualquer novo arquivo
// estático que precise existir tanto no frontend (preview) quanto no
// backend (PDF real).
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = path.resolve(__dirname, '..', 'public');
const TARGET_DIR = path.resolve(__dirname, '..', '..', 'server', 'api', 'static');

// Lista de arquivos que precisam existir nos dois lados. Adicione novos
// assets aqui conforme forem referenciados em relatorio_capa.py.
const ASSETS = [
  'mascote-nara.png',
];

fs.mkdirSync(TARGET_DIR, { recursive: true });

let falhou = false;
for (const nome of ASSETS) {
  const origem = path.join(PUBLIC_DIR, nome);
  const destino = path.join(TARGET_DIR, nome);

  if (!fs.existsSync(origem)) {
    console.error(`[copy-pdf-assets] Arquivo fonte não encontrado: ${origem}`);
    falhou = true;
    continue;
  }

  fs.copyFileSync(origem, destino);
  console.log(`[copy-pdf-assets] ${path.relative(process.cwd(), origem)} -> ${path.relative(process.cwd(), destino)}`);
}

if (falhou) {
  process.exit(1);
}