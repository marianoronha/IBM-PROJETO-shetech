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
      <div className="gd-content" id="main-content">
        <Routes>
          {/* "/" abre direto a tela do Guardião. Troque aqui se quiser outra entrada. */}
          <Route path="/" element={<Navigate to="/guardiao" replace />} />
          <Route path="/guardiao" element={<GuardiaoPage />} />
          <Route path="/bbdecision" element={<BBDecisionPage />} />
        </Routes>
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