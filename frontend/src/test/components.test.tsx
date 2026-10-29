/**
 * Testes de componentes — Bloco 4.
 *
 * Cobre:
 * - T-13/T-14: disclaimer sempre presente
 * - T-13: renderização segura (sem dangerouslySetInnerHTML, links como texto)
 * - T-13: estados de erro e vazio
 * - T-13: acessibilidade (aria-* presente, role="meter")
 * - T-14: clarification box exibida quando API pede
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { DisclaimerBanner } from '../components/DisclaimerBanner'
import { RiskGauge } from '../components/RiskGauge'
import { SafeText } from '../components/SafeText'
import { ScenarioCard } from '../components/ScenarioCard'
import { GuardiaoPage } from '../pages/Guardiao'
import { BBDecisionPage } from '../pages/BBDecision'
import * as client from '../api/client'

// ---- Helpers ----
function renderWithRouter(ui: React.ReactElement) {
  return render(<BrowserRouter>{ui}</BrowserRouter>)
}

// ============================================================
// DisclaimerBanner
// ============================================================

describe('DisclaimerBanner', () => {
  it('renderiza o aviso obrigatório', () => {
    render(<DisclaimerBanner />)
    expect(screen.getByRole('note')).toBeInTheDocument()
    expect(screen.getByText(/estimativas/i)).toBeInTheDocument()
  })

  it('exibe texto personalizado', () => {
    render(<DisclaimerBanner text="Aviso customizado" />)
    expect(screen.getByText('Aviso customizado')).toBeInTheDocument()
  })

  it('tem data-testid para testes de integração', () => {
    render(<DisclaimerBanner />)
    expect(screen.getByTestId('disclaimer-banner')).toBeInTheDocument()
  })
})

// ============================================================
// RiskGauge
// ============================================================

describe('RiskGauge', () => {
  it('renderiza label e pontuação', () => {
    render(<RiskGauge score={78} label="alto" />)
    expect(screen.getByText(/Risco Alto/i)).toBeInTheDocument()
    expect(screen.getByText('78%')).toBeInTheDocument()
  })

  it('tem role="meter" com aria attributes', () => {
    render(<RiskGauge score={45} label="médio" />)
    const meter = screen.getByRole('meter')
    expect(meter).toHaveAttribute('aria-valuenow', '45')
    expect(meter).toHaveAttribute('aria-valuemin', '0')
    expect(meter).toHaveAttribute('aria-valuemax', '100')
    expect(meter).toHaveAttribute('aria-label')
  })

  it('não depende apenas de cor — tem ícone e texto', () => {
    render(<RiskGauge score={90} label="alto" />)
    // Ícone presente
    expect(screen.getByText('🔴')).toBeInTheDocument()
    // Texto de risco presente (não apenas cor)
    expect(screen.getByText(/Alto/i)).toBeInTheDocument()
  })

  it('limita score entre 0 e 100', () => {
    render(<RiskGauge score={150} label="alto" />)
    expect(screen.getByText('100%')).toBeInTheDocument()
  })
})

// ============================================================
// SafeText — renderização segura
// ============================================================

describe('SafeText', () => {
  it('renderiza texto simples sem HTML', () => {
    render(<SafeText text="Mensagem simples" />)
    expect(screen.getByText('Mensagem simples')).toBeInTheDocument()
  })

  it('NUNCA usa dangerouslySetInnerHTML — links como texto', () => {
    const { container } = render(
      <SafeText text="Acesse http://bb-falso.xyz/verificar para confirmar" />
    )
    // Nenhum elemento <a> deve ser renderizado
    expect(container.querySelector('a')).toBeNull()
    // O texto da URL aparece como texto puro
    expect(screen.getByText(/bb-falso\.xyz/)).toBeInTheDocument()
  })

  it('renderiza conteúdo malicioso como texto seguro', () => {
    const malicious = '<script>alert("xss")</script>'
    render(<SafeText text={malicious} />)
    // Nunca renderiza script
    expect(document.querySelector('script')).toBeNull()
    // O texto é exibido como string literal
    expect(screen.getByText(/<script>/)).toBeInTheDocument()
  })

  it('conteúdo com tag HTML exibido como texto — nunca interpretado', () => {
    const htmlContent = '<img src=x onerror=alert(1)>'
    const { container } = render(<SafeText text={htmlContent} />)
    // Nenhuma imagem renderizada
    expect(container.querySelector('img')).toBeNull()
  })

  it('URLs marcadas com aria-label de segurança', () => {
    render(<SafeText text="Clique: https://phishing.example.com" />)
    const urlSpan = screen.getByLabelText(/URL suspeita/i)
    expect(urlSpan).toBeInTheDocument()
  })
})

// ============================================================
// ScenarioCard
// ============================================================

describe('ScenarioCard', () => {
  const data = {
    parcela_mensal: 100.0,
    total_pago: 1200.0,
    juros_totais: 0.0,
    novo_saldo_disponivel: 600.0,
  }

  it('renderiza label e valores da API', () => {
    render(<ScenarioCard label="Com a decisão" data={data} />)
    expect(screen.getByText('Com a decisão')).toBeInTheDocument()
    expect(screen.getByText(/100/)).toBeInTheDocument()
  })

  it('não recalcula valores — exibe exatamente o que veio da API', () => {
    render(<ScenarioCard label="Atual" data={{ saldo_disponivel: 700.0 }} />)
    // Deve exibir 700 (sem alteração)
    expect(screen.getByText(/700/)).toBeInTheDocument()
  })

  it('highlight aplica classe de destaque', () => {
    render(<ScenarioCard label="Alternativo" data={data} highlight />)
    expect(screen.getByTestId('scenario-card-alternativo')).toHaveClass('scenario-card--highlight')
  })
})

// ============================================================
// GuardiaoPage — estados de erro e vazio
// ============================================================

describe('GuardiaoPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('exibe estado vazio inicial', () => {
    renderWithRouter(<GuardiaoPage />)
    expect(screen.getByTestId('empty-state')).toBeInTheDocument()
  })

  it('exibe estado de carregamento ao submeter', async () => {
    vi.spyOn(client, 'analyzeMessage').mockImplementation(
      () => new Promise(resolve => setTimeout(resolve, 1000))
    )
    renderWithRouter(<GuardiaoPage />)

    const textarea = screen.getByRole('textbox', { name: /mensagem/i })
    fireEvent.change(textarea, { target: { value: 'Teste de mensagem' } })
    fireEvent.submit(textarea.closest('form')!)

    expect(screen.getByRole('status')).toBeInTheDocument()
    // Usa getAllByText porque "Analisando" aparece tanto no botão quanto no spinner
    expect(screen.getAllByText(/Analisando/i).length).toBeGreaterThanOrEqual(1)
  })

  it('exibe erro quando API falha — sem detalhes internos', async () => {
    vi.spyOn(client, 'analyzeMessage').mockRejectedValue(new Error('Erro 500: Internal'))
    renderWithRouter(<GuardiaoPage />)

    const textarea = screen.getByRole('textbox', { name: /mensagem/i })
    fireEvent.change(textarea, { target: { value: 'Mensagem qualquer' } })
    fireEvent.submit(textarea.closest('form')!)

    await waitFor(() => {
      expect(screen.getByTestId('error-state')).toBeInTheDocument()
    })
    // Não vaza detalhes internos
    const errorText = screen.getByTestId('error-state').textContent ?? ''
    expect(errorText).not.toContain('Traceback')
    expect(errorText).not.toContain('stack')
  })

  it('campo de mensagem não persiste em localStorage', () => {
    renderWithRouter(<GuardiaoPage />)
    const textarea = screen.getByRole('textbox', { name: /mensagem/i })
    fireEvent.change(textarea, { target: { value: 'texto secreto' } })
    // localStorage não deve ter nenhum dado da mensagem
    expect(localStorage.getItem('message')).toBeNull()
    expect(localStorage.getItem('guardiao_message')).toBeNull()
  })

  it('seletor de perfil renderiza dois perfis', () => {
    renderWithRouter(<GuardiaoPage />)
    const radios = screen.getAllByRole('radio')
    expect(radios).toHaveLength(2)
    expect(screen.getByLabelText(/Padrão/i)).toBeInTheDocument()
  })

  it('toggle de monitoramento é acessível como switch', () => {
    renderWithRouter(<GuardiaoPage />)
    const toggle = screen.getByRole('switch')
    expect(toggle).toHaveAttribute('aria-checked')
  })
})

// ============================================================
// BBDecisionPage — disclaimer e esclarecimento
// ============================================================

describe('BBDecisionPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('disclaimer SEMPRE visível antes de qualquer interação', () => {
    renderWithRouter(<BBDecisionPage />)
    // Deve haver pelo menos um disclaimer na página
    const disclaimers = screen.getAllByTestId('disclaimer-banner')
    expect(disclaimers.length).toBeGreaterThanOrEqual(1)
  })

  it('disclaimer presente ANTES de rolar — no topo da página', () => {
    renderWithRouter(<BBDecisionPage />)
    const disclaimers = screen.getAllByTestId('disclaimer-banner')
    // O primeiro disclaimer deve estar acima do formulário
    const form = document.querySelector('form')
    if (form && disclaimers[0]) {
      // O disclaimer vem antes do form no DOM
      expect(
        form.compareDocumentPosition(disclaimers[0]) & Node.DOCUMENT_POSITION_PRECEDING
      ).toBeTruthy()
    }
  })

  it('disclaimer contém texto de aviso obrigatório', () => {
    renderWithRouter(<BBDecisionPage />)
    const banners = screen.getAllByTestId('disclaimer-banner')
    const textos = banners.map(b => b.textContent ?? '').join(' ')
    expect(textos.toLowerCase()).toContain('estimativa')
  })

  it('exibe exemplos clicáveis dos 4 cenários', () => {
    renderWithRouter(<BBDecisionPage />)
    expect(screen.getByText(/Parcelamento/i)).toBeInTheDocument()
    expect(screen.getByText(/Perda de renda/i)).toBeInTheDocument()
    expect(screen.getByText(/Mudar de emprego/i)).toBeInTheDocument()
    expect(screen.getByText(/Comprar uma casa/i)).toBeInTheDocument()
  })

  it('clicar em exemplo preenche o campo de pergunta', () => {
    renderWithRouter(<BBDecisionPage />)
    const btn = screen.getByText(/Parcelamento/i)
    fireEvent.click(btn)
    const textarea = screen.getByRole('textbox', { name: /pergunta/i })
    expect((textarea as HTMLTextAreaElement).value).toContain('parcelar')
  })

  it('exibe clarification box quando API pede esclarecimento', async () => {
    vi.spyOn(client, 'simulate').mockResolvedValue({
      scenario_type: 'ambiguous',
      question_understood: 'algo',
      current_path: { label: 'atual', data: {} },
      alternative_path: { label: 'alternativo', data: {} },
      delta: {},
      warnings: [],
      assumptions: [],
      narrative: '',
      disclaimer: 'Estimativas apenas.',
      clarification_needed: true,
      clarification_question: 'Qual o valor da compra?',
    })
    renderWithRouter(<BBDecisionPage />)

    const textarea = screen.getByRole('textbox', { name: /pergunta/i })
    fireEvent.change(textarea, { target: { value: 'quero parcelar' } })
    fireEvent.submit(textarea.closest('form')!)

    await waitFor(() => {
      expect(screen.getByTestId('clarification-box')).toBeInTheDocument()
      expect(screen.getByText(/Qual o valor da compra/i)).toBeInTheDocument()
    })
  })

  it('exibe resultado com comparação quando simulação é bem-sucedida', async () => {
    vi.spyOn(client, 'simulate').mockResolvedValue({
      scenario_type: 'parcelamento',
      question_understood: 'parcelar em 12x',
      current_path: { label: 'Situação atual', data: { saldo_disponivel: 700 } },
      alternative_path: { label: 'Com a decisão', data: { parcela_mensal: 100 } },
      delta: { variacao_saldo: -100 },
      warnings: [],
      assumptions: ['Sistema Price'],
      narrative: 'Sua parcela será de R$ 100,00.',
      disclaimer: 'Estimativas apenas.',
      clarification_needed: false,
      clarification_question: null,
    })
    renderWithRouter(<BBDecisionPage />)

    const textarea = screen.getByRole('textbox', { name: /pergunta/i })
    fireEvent.change(textarea, { target: { value: 'parcelar em 12x R$ 1200' } })
    fireEvent.submit(textarea.closest('form')!)

    await waitFor(() => {
      expect(screen.getByTestId('comparison-section')).toBeInTheDocument()
      expect(screen.getByTestId('narrative')).toBeInTheDocument()
    })
  })

  it('erro da API exibido sem detalhes internos', async () => {
    vi.spyOn(client, 'simulate').mockRejectedValue(new Error('Erro 500'))
    renderWithRouter(<BBDecisionPage />)

    const textarea = screen.getByRole('textbox', { name: /pergunta/i })
    fireEvent.change(textarea, { target: { value: 'simular algo' } })
    fireEvent.submit(textarea.closest('form')!)

    await waitFor(() => {
      expect(screen.getByTestId('error-state')).toBeInTheDocument()
    })
    const errorText = screen.getByTestId('error-state').textContent ?? ''
    expect(errorText).not.toContain('Internal')
  })
})
