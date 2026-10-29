import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { GuardiaoPage } from './pages/Guardiao'
import { BBDecisionPage } from './pages/BBDecision'
import './styles/global.css'

export function App() {
  return (
    <BrowserRouter>
      <a href="#main-content" className="skip-link">Ir para o conteúdo principal</a>
      <nav className="nav" aria-label="Navegação principal">
        <NavLink
          to="/"
          end
          className={({ isActive }) => `nav__link${isActive ? ' nav__link--active' : ''}`}
          aria-current={undefined}
        >
          🛡️ Guardião
        </NavLink>
        <NavLink
          to="/bbdecision"
          className={({ isActive }) => `nav__link${isActive ? ' nav__link--active' : ''}`}
        >
          💡 BB Decision
        </NavLink>
      </nav>
      <div id="main-content">
        <Routes>
          <Route path="/" element={<GuardiaoPage />} />
          <Route path="/bbdecision" element={<BBDecisionPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
