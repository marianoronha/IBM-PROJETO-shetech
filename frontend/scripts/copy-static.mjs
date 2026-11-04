
import { cp, copyFile, mkdir } from 'node:fs/promises'
import { join } from 'node:path'

// Pastas necessárias para as páginas HTML
const folders = [
  'pages',
  'styles',
  'js',
  'img'
]

// Copia os arquivos estáticos para o build
for (const folder of folders) {
  const source = join('src', folder)
  const target = join('dist', 'src', folder)

  await mkdir(target, {
    recursive: true
  })

  await cp(source, target, {
    recursive: true,

    // Não copia arquivos React/TypeScript
    // como se fossem páginas HTML.
    filter: path =>
      folder !== 'pages' ||
      !/\.(tsx?|jsx?)$/i.test(path)
  })

  console.log(
    `Copiado: ${source} → ${target}`
  )
}

// Corrige o destino do botão Sair.
//
// No projeto existe:
// telainicial-recuperada.html
//
// Mas os menus apontam para:
// telainicial.html
//
// Cria uma cópia no build sem modificar
// o arquivo original.
await copyFile(
  join(
    'dist',
    'src',
    'pages',
    'telainicial-recuperada.html'
  ),
  join(
    'dist',
    'src',
    'pages',
    'telainicial.html'
  )
)

console.log(
  'Página telainicial.html criada no build.'
)

console.log(
  'Arquivos HTML, CSS, JS e imagens preparados.'
)
