#!/usr/bin/env node
// Copia o CSS do editor de relatórios para o diretório estático do backend,
// onde o serviço de geração de PDF o embute no HTML antes de renderizar.
// Fonte de verdade permanece em client/src/styles/relatorio-editor.css.

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SOURCE = path.resolve(__dirname, '..', 'src', 'styles', 'relatorio-editor.css');
const TARGET_DIR = path.resolve(__dirname, '..', '..', 'server', 'api', 'static', 'pdf');
const TARGET = path.join(TARGET_DIR, 'relatorio.css');

if (!fs.existsSync(SOURCE)) {
  console.error(`[copy-pdf-css] Arquivo fonte não encontrado: ${SOURCE}`);
  process.exit(1);
}

fs.mkdirSync(TARGET_DIR, { recursive: true });

const banner = [
  '/*',
  ' * ATENÇÃO: arquivo gerado automaticamente.',
  ' * Fonte: client/src/styles/relatorio-editor.css',
  ' * Gerado por: client/tools/copy-pdf-css.js (npm run build / npm run copy:pdf-css)',
  ' * NÃO EDITE AQUI — edite o arquivo fonte e rode `npm run copy:pdf-css`.',
  ' */',
  '',
].join('\n');

const content = fs.readFileSync(SOURCE, 'utf8');
fs.writeFileSync(TARGET, banner + content, 'utf8');

console.log(`[copy-pdf-css] ${path.relative(process.cwd(), SOURCE)} -> ${path.relative(process.cwd(), TARGET)}`);
