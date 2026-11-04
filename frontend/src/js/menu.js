
/**
 * MENU LATERAL COMPARTILHADO — GUARDIÃO
 *
 * Usado pelas páginas HTML do projeto.
 * Mantém as telas de apresentação.
 *
 * Início   -> inicialopcao.html
 * Guardião -> monitoramentoGuardiao.html
 * Decision -> apresentacaoDecision.html
 * Perfil   -> perfil.html
 * Sair     -> telainicial.html
 *
 * O menu React continua em Sidebar.tsx.
 */

(function () {
  'use strict'

  // ============================================
  // 1. RESTAURAR TEMA
  // ============================================

  const tema = localStorage.getItem('gd-theme')

  if (tema) {
    document.documentElement.setAttribute(
      'data-theme',
      tema
    )
  }

  // ============================================
  // 2. LOCALIZAR MENU
  // ============================================

  const sidebar = document.querySelector('.gd-side')

  if (!sidebar) return

  const nav = sidebar.querySelector('.gd-nav')

  if (!nav) return

  const PAGES = '/src/pages/'

  // ============================================
  // 3. ITENS DO MENU
  // ============================================

  const itens = [
    {
      id: 'inicio',
      texto: 'Início',
      link: PAGES + 'inicialopcao.html',
      icone: [
        'M3 11 12 3l9 8',
        'M5 10v10h14V10',
        'M10 20v-6h4v6'
      ]
    },
    {
      id: 'guardiao',
      texto: 'Guardião',
      link: PAGES + 'monitoramentoGuardiao.html',
      icone: [
        'M12 3 5 6v5c0 4.5 3 8.2 7 10 4-1.8 7-5.5 7-10V6z',
        'M12 8v5',
        'M12 16h.01'
      ]
    },
    {
      id: 'decision',
      texto: 'Decision',
      link: PAGES + 'apresentacaoDecision.html',
      icone: [
        'M5 20V12',
        'M12 20V5',
        'M19 20v-9'
      ]
    },
    {
      id: 'perfil',
      texto: 'Perfil',
      link: PAGES + 'perfil.html',
      icone: [
        null
      ]
    },
    {
      id: 'sair',
      texto: 'Sair',
      link: PAGES + 'telainicial.html',
      icone: [
        'M10 4H5v16h5',
        'M9 12h11',
        'm16 8 4 4-4 4'
      ]
    }
  ]

  // ============================================
  // 4. IDENTIFICAR PÁGINA ATUAL
  // ============================================

  const pagina = window.location.pathname
    .split('/')
    .pop()
    .toLowerCase()

  let paginaAtiva = ''

  const paginasGuardiao = [
    'monitoramentoguardiao.html',
    'testegolpemensagem.html',
    'testelink.html',
    'testetransacoes.html',
    'testeaplicativos.html'
  ]

  const paginasPerfil = [
    'perfil.html',
    'historicotestes.html'
  ]

  const paginasDecision = [
    'apresentacaodecision.html',
    'bbdecision.html'
  ]

  if (pagina === 'inicialopcao.html') {
    paginaAtiva = 'inicio'
  } else if (paginasGuardiao.includes(pagina)) {
    paginaAtiva = 'guardiao'
  } else if (paginasDecision.includes(pagina)) {
    paginaAtiva = 'decision'
  } else if (paginasPerfil.includes(pagina)) {
    paginaAtiva = 'perfil'
  }

  // ============================================
  // 5. CRIAR ÍCONES
  // ============================================

  const SVG_NS = 'http://www.w3.org/2000/svg'

  function criarIcone(item) {
    const svg = document.createElementNS(
      SVG_NS,
      'svg'
    )

    svg.setAttribute('viewBox', '0 0 24 24')
    svg.setAttribute('aria-hidden', 'true')

    if (item.id === 'perfil') {
      const circulo = document.createElementNS(
        SVG_NS,
        'circle'
      )

      circulo.setAttribute('cx', '12')
      circulo.setAttribute('cy', '8')
      circulo.setAttribute('r', '4')

      svg.appendChild(circulo)

      const path = document.createElementNS(
        SVG_NS,
        'path'
      )

      path.setAttribute(
        'd',
        'M4 21c1-4 4-6 8-6s7 2 8 6'
      )

      svg.appendChild(path)
    } else {
      item.icone.forEach(d => {
        const path = document.createElementNS(
          SVG_NS,
          'path'
        )

        path.setAttribute('d', d)
        svg.appendChild(path)
      })
    }

    return svg
  }

  // ============================================
  // 6. CONSTRUIR MENU
  // ============================================

  const fragmento = document.createDocumentFragment()

  itens.forEach(item => {
    const link = document.createElement('a')

    link.href = item.link
    link.title = item.texto

    link.className =
      item.id === 'sair'
        ? 'gd-item gd-out'
        : 'gd-item'

    if (paginaAtiva === item.id) {
      link.setAttribute('aria-current', 'page')
    }

    const svg = criarIcone(item)

    const texto = document.createElement('span')
    texto.className = 'gd-lbl'
    texto.textContent = item.texto

    link.appendChild(svg)
    link.appendChild(texto)

    fragmento.appendChild(link)
  })

  nav.replaceChildren(fragmento)

  // ============================================
  // 7. CORRIGIR LINKS ANTIGOS DO DECISION
  // ============================================

  document.querySelectorAll('a[href]').forEach(link => {
    const href = link.getAttribute('href')

    if (
      href === 'BBDecision.html' ||
      href === '/src/pages/BBDecision.html'
    ) {
      link.setAttribute(
        'href',
        PAGES + 'apresentacaoDecision.html'
      )
    }
  })

  // ============================================
  // 8. RECOLHER / EXPANDIR MENU
  // ============================================

  const botao = sidebar.querySelector('.gd-collapse')

  if (!botao) return

  function atualizarBotao() {
    const recolhido = sidebar.classList.contains(
      'min'
    )

    botao.setAttribute(
      'aria-label',
      recolhido
        ? 'Expandir menu'
        : 'Recolher menu'
    )

    botao.setAttribute(
      'aria-expanded',
      String(!recolhido)
    )
  }

  if (
    window.matchMedia('(max-width:760px)').matches
  ) {
    sidebar.classList.add('min')
  }

  atualizarBotao()

  botao.addEventListener('click', () => {
    sidebar.classList.toggle('min')
    atualizarBotao()
  })

})()
