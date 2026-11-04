import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { GuardiaoPage } from './pages/Guardiao'
import { BBDecisionPage } from './pages/BBDecision'
import { Sidebar } from './components/Sidebar'
import './styles/global.css'
import './styles/menu.css'
import './styles/guardiao.css'

function Layout() {
  const { pathname } = useLocation()
  const active = pathname.startsWith('/bbdecision') ? 'decision' : 'guardiao'

  return (
    <div className="gd-app">
      <Sidebar active={active} />
      <div className="gd-content" id="main-content" style={{ display: 'flex', flexDirection: 'column' }}>
        <Routes>
          {/* "/" abre direto a tela do Guardião. Troque aqui se quiser outra entrada. */}
          <Route path="/" element={<Navigate to="/guardiao" replace />} />
          <Route path="/guardiao" element={<GuardiaoPage />} />
          <Route path="/bbdecision" element={<BBDecisionPage />} />
        </Routes>
        <footer className="rodape" style={{ marginTop: 'auto' }}>
          <div className="rodape__inner">
            <div className="rodape__marca">
              <img src="/src/img/logobdb.png" alt="Banco do Brasil" className="rodape__logo-bb" />
              <span>Guardião</span>
              <span className="rodape__parceria">Um projeto <strong>SheTech</strong> em parceria com o Banco do Brasil.</span>
            </div>
            <nav className="rodape__links" aria-label="Rodapé">
              <a href="/src/pages/monitoramentoGuardiao.html">Guardião</a>
              <a href="/src/pages/BBDecision.html">BB Decision</a>
            </nav>
          </div>
        </footer>
      </div>
    </div>
  )
}

export function App() {
  return (
    <BrowserRouter>
      <a href="#main-content" className="skip-link">Ir para o conteúdo principal</a>
      <Layout />
    </BrowserRouter>
  )
}