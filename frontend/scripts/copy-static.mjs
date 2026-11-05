
import { cpSync, mkdirSync } from 'node:fs';

const pastas = ['pages', 'styles', 'img', 'js'];

for (const pasta of pastas) {
  mkdirSync(`dist/src/${pasta}`, { recursive: true });

  cpSync(`src/${pasta}`, `dist/src/${pasta}`, {
    recursive: true,
    force: true
  });

  console.log(`Copiado: src/${pasta}`);
}

console.log('Arquivos estáticos preparados para o Vercel!');
