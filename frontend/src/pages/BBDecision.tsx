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
    <main className="gd-page bb-page">
      <header className="gd-hero">
        <div className="gd-hero__in">
          <div className="gd-shield" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="#fcd116" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18h6" /><path d="M10 21h4" />
              <path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V16h5v-.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3Z" />
            </svg>
          </div>
          <div>
            <h1 className="gd-title">BB Decision</h1>
            <p className="gd-sub">Simule decisões financeiras antes de tomá-las</p>
          </div>
        </div>
      </header>

      <div className="gd-wrap">
        {/* Disclaimer SEMPRE visível no topo — RF-D-10 */}
        <DisclaimerBanner />

        {/* Exemplos clicáveis dos 4 cenários do PDF */}
        <nav aria-label="Exemplos de perguntas" className="gd-card bb-examples">
          <p className="bb-examples__label">Experimente:</p>
          <div className="bb-examples__grid">
            {EXAMPLE_QUESTIONS.map(ex => (
              <button
                key={ex.label}
                type="button"
                className="bb-chip"
                onClick={() => applyExample(ex)}
                aria-label={`Usar exemplo: ${ex.text}`}
              >
                {ex.label}
              </button>
            ))}
          </div>
        </nav>

        {/* Formulário */}
        <form onSubmit={handleSubmit} className="gd-card" noValidate>
          <div>
            <label htmlFor="question-input" className="gd-label">
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
            <span id="question-hint" className="gd-hint">
              {question.length}/1000 caracteres
            </span>
          </div>

          <div className="bb-row">
            <div>
              <label htmlFor="bb-user-id" className="gd-legend">
                Perfil sintético (demo)
              </label>
              <select
                id="bb-user-id"
                value={userId}
                onChange={e => setUserId(e.target.value)}
                className="gd-select"
              >
                <option value="U001">U001 — Maria S. (renda R$ 3.500)</option>
                <option value="U002">U002 — Carlos M. (renda R$ 8.500)</option>
                <option value="U003">U003 — Roberto A. (renda R$ 4.800)</option>
                <option value="">Sem perfil</option>
              </select>
            </div>

            <div>
              <label htmlFor="bb-profile" className="gd-legend">Linguagem</label>
              <select
                id="bb-profile"
                value={profile}
                onChange={e => setProfile(e.target.value as 'standard' | 'low')}
                className="gd-select"
              >
                <option value="standard">Padrão</option>
                <option value="low">Linguagem simples</option>
              </select>
            </div>
          </div>

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
            className="result gd-result"
            data-testid="result-section"
          >
            <div className="gd-card bb-head">
              <h2 className="result__scenario-title">
                Simulação: {scenarioLabel}
              </h2>
              <p className="result__question-understood">
                Entendi: <em>{result.question_understood}</em>
              </p>
            </div>

            {/* Narrativa da IA */}
            <div className="gd-card result__narrative" data-testid="narrative">
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