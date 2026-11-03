/**
 * Sidebar — menu lateral do Guardião (recolhível).
 * Mesmo visual/markup usado nas páginas HTML (styles/menu.css).
 * Sem localStorage: o estado recolhido vive só na memória.
 */
import { useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export type MenuKey = 'inicio' | 'aprender' | 'guardiao' | 'decision' | 'chat' | 'perfil'

const PAGES = '/src/pages/' // páginas HTML servidas pelo Vite

const icon = (children: ReactNode) => (
  <svg viewBox="0 0 24 24" aria-hidden="true">{children}</svg>
)

const ITEMS: { key: MenuKey; label: string; href: string; router?: boolean; icon: ReactNode }[] = [
  { key: 'inicio', label: 'Início', href: `${PAGES}monitoramentoGuardiao.html`,
    icon: icon(<><path d="M3 11 12 3l9 8" /><path d="M5 10v10h14V10" /><path d="M10 20v-6h4v6" /></>) },
  { key: 'aprender', label: 'Aprender', href: `${PAGES}aprender.html`,
    icon: icon(<><path d="M12 6v14" /><path d="M3 5h6a3 3 0 0 1 3 3v12a2.5 2.5 0 0 0-2.5-2.5H3z" /><path d="M21 5h-6a3 3 0 0 0-3 3v12a2.5 2.5 0 0 1 2.5-2.5H21z" /></>) },
  // "Guardião" leva à tela de apresentação (monitoramentoGuardiao.html)
  { key: 'guardiao', label: 'Guardião', href: `${PAGES}monitoramentoGuardiao.html`,
    icon: icon(<><path d="M12 3 5 6v5c0 4.5 3 8.2 7 10 4-1.8 7-5.5 7-10V6z" /><path d="M12 8v5" /><path d="M12 16h.01" /></>) },
  { key: 'decision', label: 'Decision', href: `${PAGES}apresentacaoDecision.html`,
    icon: icon(<><path d="M5 20V12" /><path d="M12 20V5" /><path d="M19 20v-9" /></>) },
  { key: 'chat', label: 'Chat', href: '#',
    icon: icon(<path d="M4 5h16v11H9l-5 4z" />) },
  { key: 'perfil', label: 'Perfil', href: '#',
    icon: icon(<><circle cx="12" cy="8" r="4" /><path d="M4 21c1-4 4-6 8-6s7 2 8 6" /></>) },
]

export function Sidebar({ active }: { active: MenuKey }) {
  const [min, setMin] = useState(
    () => typeof window !== 'undefined' && window.matchMedia?.('(max-width:760px)').matches,
  )

  return (
    <aside className={`gd-side${min ? ' min' : ''}`}>
      <button
        type="button"
        className="gd-collapse"
        aria-label={min ? 'Expandir menu' : 'Recolher menu'}
        onClick={() => setMin(v => !v)}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 6-6 6 6 6" /></svg>
      </button>

      <div className="gd-logo">
        <svg className="mk" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3Z" fill="#fcd116" />
          <path d="m8.5 12 2.6 2.6L16 9.7" stroke="#002a63" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="gd-wm">Guardião<i /></span>
      </div>

      <nav className="gd-nav" aria-label="Menu principal">
        {ITEMS.map(it => {
          const cur = active === it.key ? 'page' : undefined
          const body = <>{it.icon}<span className="gd-lbl">{it.label}</span></>
          return it.router ? (
            <Link key={it.key} to={it.href} className="gd-item" aria-current={cur} title={it.label}>{body}</Link>
          ) : (
            <a key={it.key} href={it.href} className="gd-item" aria-current={cur} title={it.label}>{body}</a>
          )
        })}
        <a href="#" className="gd-item gd-out" title="Sair">
          {icon(<><path d="M10 4H5v16h5" /><path d="M9 12h11" /><path d="m16 8 4 4-4 4" /></>)}
          <span className="gd-lbl">Sair</span>
        </a>
      </nav>
    </aside>
  )
}