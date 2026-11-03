
/**
 * Menu lateral compartilhado — Guardião
 *
 * Páginas HTML utilizam este arquivo.
 * Páginas React utilizam Sidebar.tsx.
 *
 * Mantém as telas de apresentação:
 * Início -> inicialopcao.html
 * Guardião -> monitoramentoGuardiao.html
 * Decision -> apresentacaoDecision.html
 * Perfil -> perfil.html
 * Sair -> telainicial.html
 */

// Restaura o tema salvo
(function () {
  const tema = localStorage.getItem('gd-theme')

  if (tema) {
    document.documentElement.setAttribute(
      'data-theme',
      tema
    )
  }
})()

// Configura o menu das páginas HTML
;(function () {
  const side = document.querySelector('.gd-side')

  if (!side) return

  const PAGES = '/src/pages/'

  const MENU = [
    {
      key: 'inicio',
      label: 'Início',
      href: `${PAGES}inicialopcao.html`,
      svg: `
        <path d="M3 11 12 3l9 8"/>
        <path d="M5 10v10h14V10"/>
        <path d="M10 20v-6h4v6"/>
      `
    },
    {
      key: 'guardiao',
      label: 'Guardião',
      href: `${PAGES}monitoramentoGuardiao.html`,
      svg: `
        <path d="M12 3 5 6v5c0 4.5 3 8.2 7 10 4-1.8 7-5.5 7-10V6z"/>
        <path d="M12 8v5"/>
        <path d="M12 16h.01"/>
      `
    },
    {
      key: 'decision',
      label: 'Decision',
      href: `${PAGES}apresentacaoDecision.html`,
      svg: `
        <path d="M5 20V12"/>
        <path d="M12 20V5"/>
        <path d="M19 20v-9"/>
      `
    },
    {
      key: 'perfil',
      label: 'Perfil',
      href: `${PAGES}perfil.html`,
      svg: `
        <circle cx="12" cy="8" r="4"/>
        <path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>
      `
    },
    {
      key: 'sair',
      label: 'Sair',
      href: `${PAGES}telainicial.html`,
      svg: `
        <path d="M10 4H5v16h5"/>
        <path d="M9 12h11"/>
        <path d="m16 8 4 4-4 4"/>
      `
    }
  ]

  // Identifica qual página está aberta
  const pagina = window.location.pathname
    .split('/')
    .pop()
    .toLowerCase()

  let active = ''

  if (pagina === 'inicialopcao.html') {
    active = 'inicio'
  } else if (
    pagina === 'monitoramentoguardiao.html' ||
    pagina === 'testegolpemensagem.html' ||
    pagina === 'testelink.html' ||
    pagina === 'testetransacoes.html' ||
    pagina === 'testeaplicativos.html' ||
    pagina === 'historicotestes.html'
  ) {
    active = 'guardiao'
  } else if (
    pagina === 'apresentacaodecision.html' ||
    pagina === 'bbdecision.html'
  ) {
    active = 'decision'
  } else if (pagina === 'perfil.html') {
    active = 'perfil'
  }

  // Reutiliza o menu existente
  const nav = side.querySelector('.gd-nav')

  if (nav) {
    nav.setAttribute('aria-label', 'Menu principal')

    // Substitui somente os itens de navegação.
    // Não modifica o conteúdo das páginas.
    nav.replaceChildren()

    MENU.forEach(item => {
      const link = document.createElement('a')

      link.className =
        item.key === 'sair'
          ? 'gd-item gd-out'
          : 'gd-item'

      link.href = item.href
      link.title = item.label

      if (active === item.key) {
        link.setAttribute('aria-current', 'page')
      }

      const svg = document.createElementNS(
        'http://www.w3.org/2000/svg',
        'svg'
      )

      svg.setAttribute('viewBox', '0 0 24 24')
      svg.setAttribute('aria-hidden', 'true')

      // SVGs são constantes definidas neste arquivo
      svg.innerHTML = item.svg

      const label = document.createElement('span')
      label.className = 'gd-lbl'
      label.textContent = item.label

      link.append(svg, label)
      nav.appendChild(link)
    })
  }

  // Botão de recolher e expandir
  const btn = side.querySelector('.gd-collapse')

  if (!btn) return

  if (
    window.matchMedia('(max-width:760px)').matches
  ) {
    side.classList.add('min')
  }

  function atualizarBotao() {
    const min = side.classList.contains('min')

    btn.setAttribute(
      'aria-label',
      min ? 'Expandir menu' : 'Recolher menu'
    )

    btn.setAttribute('aria-expanded', String(!min))
  }

  atualizarBotao()

  btn.addEventListener('click', function () {
    side.classList.toggle('min')
    atualizarBotao()
  })
})()
