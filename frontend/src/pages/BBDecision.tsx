
/**
 * BB Decision — UI principal (T-14).
 *
 * - Campo em linguagem natural com exemplos clicáveis dos 4 cenários.
 * - Disclaimer sempre visível no topo.
 * - Quando API pede esclarecimento, mostra a pergunta.
 * - Comparação lado a lado atual vs. alternativo.
 * - Valores exatamente como vieram da API.
 * - Botão para voltar à apresentação do BB Decision.
 */

import { useState, useRef } from 'react'
import { simulate } from '../api/client'
import type { BBDecisionResponse } from '../types/api'
import { DisclaimerBanner } from '../components/DisclaimerBanner'
import { ScenarioCard } from '../components/ScenarioCard'
import { SafeText } from '../components/SafeText'
import '../styles/bbdecision.css'

const EXAMPLE_QUESTIONS = [
  {
    icon: '📦',
    title: 'Parcelamento',
    desc: 'Quanto pesa dividir uma compra no mês',
    text: 'E se eu parcelar em 12x no valor de R$ 1200?',
    userId: 'U002',
  },
  {
    icon: '📉',
    title: 'Perda de renda',
    desc: 'Por quanto tempo a reserva aguenta',
    text: 'E se eu perder minha renda por 3 meses?',
    userId: 'U003',
  },
  {
    icon: '💼',
    title: 'Mudar de emprego',
    desc: 'Compare a renda atual com a nova',
    text: 'E se eu mudar de emprego e ganhar R$ 6000?',
    userId: 'U003',
  },
  {
    icon: '🏠',
    title: 'Comprar uma casa',
    desc: 'Veja entrada, prestação e custo total',
    text: 'E se eu comprar uma casa de R$ 300000 com entrada de R$ 60000?',
    userId: 'U002',
  },
]

const SCENARIO_LABELS: Record<string, string> = {
  parcelamento: 'Parcelamento',
  perda_renda: 'Perda de Renda',
  mudanca_emprego: 'Mudança de Emprego',
  compra_casa: 'Compra de Casa',
  ambiguous: 'Cenário não identificado',
}

const PROFILE_OPTIONS: {
  value: 'standard' | 'low'
  label: string
}[] = [
  { value: 'standard', label: 'Padrão' },
  { value: 'low', label: 'Linguagem simples' },
]

export function BBDecisionPage() {
  const [question, setQuestion] = useState('')
  const [userId, setUserId] = useState('U002')
  const [profile, setProfile] = useState<'standard' | 'low'>('standard')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<BBDecisionResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const resultRef = useRef<HTMLDivElement>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    if (!question.trim()) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const data = await simulate({
        question,
        user_id: userId,
        language_profile: profile,
        simulation_consent: true,
      })

      setResult(data)

      setTimeout(() => resultRef.current?.focus(), 100)
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Erro ao processar a simulação.'

      setError(
        msg.startsWith('Erro 5')
          ? 'Erro interno. Tente novamente.'
          : msg
      )
    } finally {
      setLoading(false)
    }
  }

  function applyExample(ex: typeof EXAMPLE_QUESTIONS[0]) {
    setQuestion(ex.text)
    setUserId(ex.userId)
    setResult(null)
    setError(null)
  }

  const scenarioLabel = result
    ? (SCENARIO_LABELS[result.scenario_type] ?? result.scenario_type)
    : ''

  return (
    <main className="gd-page bb-page">

      {/* =========================================
          CABEÇALHO DO BB DECISION
         ========================================= */}

      <header className="gd-hero">
        <div className="gd-hero__in">

          {/* BOTÃO DE VOLTAR */}
          <a
            href="/src/pages/apresentacaoDecision.html"
            className="bb-back"
            aria-label="Voltar para a apresentação do BB Decision"
            title="Voltar"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M19 12H5" />
              <path d="m12 19-7-7 7-7" />
            </svg>
          </a>

          {/* ÍCONE DA LÂMPADA */}
          <div className="gd-shield" aria-hidden="true">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="#fcd116"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M9 18h6" />
              <path d="M10 21h4" />
              <path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V16h5v-.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3Z" />
            </svg>
          </div>

          {/* TÍTULO */}
          <div>
            <h1 className="gd-title">BB Decision</h1>
            <p className="gd-sub">
              Simule decisões financeiras antes de tomá-las
            </p>
          </div>

        </div>
      </header>

      {/* =========================================
          CONTEÚDO PRINCIPAL
         ========================================= */}

      <div className="gd-wrap">

        {/* AVISO OBRIGATÓRIO */}
        <DisclaimerBanner />

        {/* =========================================
            EXEMPLOS DE SIMULAÇÃO
           ========================================= */}

        <nav
          aria-label="Exemplos de perguntas"
          className="gd-card bb-examples"
        >
          <p className="bb-examples__label">
            Comece por um exemplo
          </p>

          <p className="bb-examples__sub">
            Clique em um cenário para preencher a pergunta.
          </p>

          <div className="bb-examples__grid">
            {EXAMPLE_QUESTIONS.map(ex => (
              <button
                key={ex.title}
                type="button"
                className="bb-chip"
                onClick={() => applyExample(ex)}
                aria-pressed={question === ex.text}
                aria-label={`Usar exemplo ${ex.title}: ${ex.text}`}
              >
                <span
                  className="bb-chip__icon"
                  aria-hidden="true"
                >
                  {ex.icon}
                </span>

                <span className="bb-chip__body">
                  <span className="bb-chip__title">
                    {ex.title}
                  </span>

                  <span className="bb-chip__text">
                    {ex.desc}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </nav>

        {/* =========================================
            FORMULÁRIO DE SIMULAÇÃO
           ========================================= */}

        <form
          onSubmit={handleSubmit}
          className="gd-card bb-form"
          noValidate
        >
          <div>
            <label
              htmlFor="question-input"
              className="gd-label"
            >
              Faça sua pergunta como faria em uma conversa
            </label>

            <textarea
              id="question-input"
              value={question}
              onChange={e => setQuestion(e.target.value)}
              maxLength={1000}
              rows={3}
              placeholder="Ex: “E se eu parcelar essa compra em 12x?”"
              className="gd-textarea"
              aria-describedby="question-hint"
              aria-required="true"
              disabled={loading}
            />

            <span
              id="question-hint"
              className="gd-hint"
            >
              {question.length}/1000 caracteres
            </span>
          </div>

          {/* PERFIL E LINGUAGEM */}
          <div className="bb-row">

            <div>
              <label
                htmlFor="bb-user-id"
                className="gd-legend"
              >
                Perfil sintético (demo)
              </label>

              <select
                id="bb-user-id"
                value={userId}
                onChange={e => setUserId(e.target.value)}
                className="gd-select"
                disabled={loading}
              >
                <option value="U001">
                  U001 — Maria S. (renda R$ 3.500)
                </option>

                <option value="U002">
                  U002 — Carlos M. (renda R$ 8.500)
                </option>

                <option value="U003">
                  U003 — Roberto A. (renda R$ 4.800)
                </option>

                <option value="">
                  Sem perfil
                </option>
              </select>
            </div>

            <fieldset
              style={{
                border: 0,
                padding: 0,
                margin: 0,
                minWidth: 0,
              }}
            >
              <legend
                className="gd-legend"
                style={{ padding: 0 }}
              >
                Linguagem
              </legend>

              <div
                className="bb-seg"
                role="radiogroup"
                aria-label="Linguagem da resposta"
              >
                {PROFILE_OPTIONS.map(opt => (
                  <label
                    key={opt.value}
                    className="bb-seg__opt"
                  >
                    <input
                      type="radio"
                      name="bb-profile"
                      value={opt.value}
                      checked={profile === opt.value}
                      onChange={() => setProfile(opt.value)}
                      disabled={loading}
                    />

                    <span>{opt.label}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          </div>

          {/* BOTÕES DE AÇÃO */}
          <div className="gd-actions">
            <button
              type="submit"
              className="gd-btn gd-btn--primary"
              disabled={loading || !question.trim()}
              aria-busy={loading}
            >
              {loading ? 'Simulando…' : 'Simular'}
            </button>

            <button
              type="button"
              className="gd-btn gd-btn--ghost"
              onClick={() => {
                setQuestion('')
                setResult(null)
                setError(null)
              }}
              disabled={loading}
            >
              Limpar
            </button>
          </div>
        </form>

        {/* =========================================
            ESTADO DE CARREGAMENTO
           ========================================= */}

        {loading && (
          <div
            role="status"
            aria-live="polite"
            className="loading-state"
          >
            <span
              className="loading-state__spinner"
              aria-hidden="true"
            />

            Calculando cenários…
          </div>
        )}

        {/* =========================================
            ESTADO DE ERRO
           ========================================= */}

        {error && (
          <div
            role="alert"
            className="error-state"
            data-testid="error-state"
          >
            <strong>Não foi possível processar.</strong>{' '}
            {error}
          </div>
        )}

        {/* =========================================
            ESCLARECIMENTO NECESSÁRIO
           ========================================= */}

        {result?.clarification_needed &&
          result.clarification_question && (
            <div
              className="clarification"
              role="status"
              aria-live="polite"
              data-testid="clarification-box"
            >
              <p className="clarification__title">
                💬 Preciso de mais detalhes
              </p>

              <SafeText
                text={result.clarification_question}
                className="clarification__text"
              />
            </div>
          )}

        {/* =========================================
            RESULTADO DA SIMULAÇÃO
           ========================================= */}

        {result && !result.clarification_needed && (
          <section
            ref={resultRef}
            tabIndex={-1}
            aria-label="Resultado da simulação"
            className="result gd-result"
            data-testid="result-section"
          >

            {/* TÍTULO DO CENÁRIO */}
            <div className="gd-card bb-head">
              <h2 className="result__scenario-title">
                Simulação: {scenarioLabel}
              </h2>

              <p className="result__question-understood">
                Entendi:{' '}
                <em>{result.question_understood}</em>
              </p>
            </div>

            {/* RESUMO DA IA */}
            <div
              className="gd-card result__narrative"
              data-testid="narrative"
            >
              <h3>Resumo</h3>

              <SafeText
                text={result.narrative}
                className="result__narrative-text"
              />
            </div>

            {/* COMPARAÇÃO DOS CENÁRIOS */}
            <div
              className="comparison"
              data-testid="comparison-section"
            >
              <h3 className="comparison__title">
                Comparação de cenários
              </h3>

              <div className="comparison__grid">
                <ScenarioCard
                  label={result.current_path.label}
                  data={result.current_path.data}
                />

                <ScenarioCard
                  label={result.alternative_path.label}
                  data={result.alternative_path.data}
                  highlight
                />
              </div>
            </div>

            {/* AVISOS */}
            {result.warnings.length > 0 && (
              <div
                className="warnings"
                role="alert"
                data-testid="warnings"
              >
                <h3>Atenções</h3>

                <ul aria-label="Alertas da simulação">
                  {result.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* PREMISSAS */}
            <details className="assumptions">
              <summary>
                Premissas e fórmulas utilizadas
              </summary>

              <ul aria-label="Premissas da simulação">
                {result.assumptions.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </details>
          </section>
        )}

        {/* =========================================
            ESTADO VAZIO
           ========================================= */}

        {!result && !loading && !error && (
          <div
            className="empty-state"
            data-testid="empty-state"
          >
            Faça uma pergunta acima ou clique em um dos exemplos
            para começar.
          </div>
        )}

      </div>
    </main>
  )
}
