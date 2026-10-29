/**
 * BB Decision — UI principal (T-14).
 *
 * - Campo em linguagem natural com exemplos clicáveis dos 4 cenários do PDF.
 * - Disclaimer SEMPRE visível sem precisar rolar.
 * - Quando API pede esclarecimento, mostra a pergunta de forma clara.
 * - Comparação lado a lado atual vs. alternativo.
 * - Valores exatamente como vieram da API — sem recalcular no front.
 */

import { useState, useRef } from 'react'
import { simulate } from '../api/client'
import type { BBDecisionResponse } from '../types/api'
import { DisclaimerBanner } from '../components/DisclaimerBanner'
import { ScenarioCard } from '../components/ScenarioCard'
import { SafeText } from '../components/SafeText'

const EXAMPLE_QUESTIONS = [
  {
    label: '📦 Parcelamento',
    text: 'E se eu parcelar em 12x no valor de R$ 1200?',
    userId: 'U002',
  },
  {
    label: '📉 Perda de renda',
    text: 'E se eu perder minha renda por 3 meses?',
    userId: 'U003',
  },
  {
    label: '💼 Mudar de emprego',
    text: 'E se eu mudar de emprego e ganhar R$ 6000?',
    userId: 'U003',
  },
  {
    label: '🏠 Comprar uma casa',
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
      const msg = err instanceof Error ? err.message : 'Erro ao processar a simulação.'
      setError(msg.startsWith('Erro 5') ? 'Erro interno. Tente novamente.' : msg)
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

  const scenarioLabel = result ? (SCENARIO_LABELS[result.scenario_type] ?? result.scenario_type) : ''

  return (
    <main className="page">
      <div className="page__inner">

        {/* Disclaimer SEMPRE visível no topo — RF-D-10 */}
        <DisclaimerBanner />

        <header className="page__header">
          <h1 className="page__title">💡 BB Decision</h1>
          <p className="page__subtitle">
            Simule decisões financeiras antes de tomá-las
          </p>
        </header>

        {/* Exemplos clicáveis dos 4 cenários do PDF */}
        <nav aria-label="Exemplos de perguntas" className="examples">
          <p className="examples__label">Experimente:</p>
          <div className="examples__grid">
            {EXAMPLE_QUESTIONS.map(ex => (
              <button
                key={ex.label}
                type="button"
                className="examples__btn"
                onClick={() => applyExample(ex)}
                aria-label={`Usar exemplo: ${ex.text}`}
              >
                {ex.label}
              </button>
            ))}
          </div>
        </nav>

        {/* Formulário */}
        <form onSubmit={handleSubmit} className="form" noValidate>
          <div className="form__group">
            <label htmlFor="question-input" className="form__label">
              Faça sua pergunta como faria em uma conversa
            </label>
            <textarea
              id="question-input"
              value={question}
              onChange={e => setQuestion(e.target.value)}
              maxLength={1000}
              rows={3}
              placeholder='Ex: "E se eu parcelar essa compra em 12x?"'
              className="form__textarea"
              aria-describedby="question-hint"
              aria-required="true"
              disabled={loading}
            />
            <span id="question-hint" className="form__hint">
              {question.length}/1000 caracteres
            </span>
          </div>

          <div className="form__row">
            <div className="form__group form__group--inline">
              <label htmlFor="bb-user-id" className="form__label">
                Perfil sintético (demo)
              </label>
              <select
                id="bb-user-id"
                value={userId}
                onChange={e => setUserId(e.target.value)}
                className="form__select"
              >
                <option value="U001">U001 — Maria S. (renda R$ 3.500)</option>
                <option value="U002">U002 — Carlos M. (renda R$ 8.500)</option>
                <option value="U003">U003 — Roberto A. (renda R$ 4.800)</option>
                <option value="">Sem perfil</option>
              </select>
            </div>

            <div className="form__group form__group--inline">
              <label htmlFor="bb-profile" className="form__label">Linguagem</label>
              <select
                id="bb-profile"
                value={profile}
                onChange={e => setProfile(e.target.value as 'standard' | 'low')}
                className="form__select"
              >
                <option value="standard">Padrão</option>
                <option value="low">Linguagem simples</option>
              </select>
            </div>
          </div>

          <div className="form__actions">
            <button
              type="submit"
              className="btn btn--primary"
              disabled={loading || !question.trim()}
              aria-busy={loading}
            >
              {loading ? 'Simulando…' : 'Simular'}
            </button>
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => { setQuestion(''); setResult(null); setError(null) }}
              disabled={loading}
            >
              Limpar
            </button>
          </div>
        </form>

        {/* Estado de carregamento */}
        {loading && (
          <div role="status" aria-live="polite" className="loading-state">
            <span className="loading-state__spinner" aria-hidden="true" />
            Calculando cenários…
          </div>
        )}

        {/* Estado de erro */}
        {error && (
          <div role="alert" className="error-state" data-testid="error-state">
            <strong>Não foi possível processar.</strong> {error}
          </div>
        )}

        {/* Esclarecimento necessário */}
        {result?.clarification_needed && result.clarification_question && (
          <div
            className="clarification"
            role="status"
            aria-live="polite"
            data-testid="clarification-box"
          >
            <p className="clarification__title">💬 Preciso de mais detalhes</p>
            <SafeText
              text={result.clarification_question}
              className="clarification__text"
            />
          </div>
        )}

        {/* Resultado da simulação */}
        {result && !result.clarification_needed && (
          <section
            ref={resultRef}
            tabIndex={-1}
            aria-label="Resultado da simulação"
            className="result"
            data-testid="result-section"
          >
            <h2 className="result__scenario-title">
              Simulação: {scenarioLabel}
            </h2>
            <p className="result__question-understood">
              Entendi: <em>{result.question_understood}</em>
            </p>

            {/* Narrativa da IA */}
            <div className="result__narrative" data-testid="narrative">
              <h3>Resumo</h3>
              <SafeText text={result.narrative} className="result__narrative-text" />
            </div>

            {/* Comparação lado a lado */}
            <div className="comparison" data-testid="comparison-section">
              <h3 className="comparison__title">Comparação de cenários</h3>
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

            {/* Atenções — bloco único, sem duplicar aviso de estimativa */}
            {result.warnings.length > 0 && (
              <div className="warnings" role="alert" data-testid="warnings">
                <h3>Atenções</h3>
                <ul aria-label="Alertas da simulação">
                  {result.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Premissas */}
            <details className="assumptions">
              <summary>Premissas e fórmulas utilizadas</summary>
              <ul aria-label="Premissas da simulação">
                {result.assumptions.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </details>
          </section>
        )}

        {/* Estado vazio */}
        {!result && !loading && !error && (
          <div className="empty-state" data-testid="empty-state">
            Faça uma pergunta acima ou clique em um dos exemplos para começar.
          </div>
        )}

      </div>
    </main>
  )
}
