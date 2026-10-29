/**
 * Guardião — UI principal (T-13).
 *
 * Segue o layout da tela do PDF (p. 4):
 * - Entrada simples (colar link/mensagem/descrição)
 * - Indicador de risco em % com classificação
 * - Tipo do golpe + como é aplicado
 * - Sinais de alerta
 * - Resumo e próximo passo pelos canais oficiais
 * - Seletor de perfil (padrão / linguagem simples)
 * - Intervenção transparente (cliente decide)
 * - Flag de revisão humana
 * - Controle de monitoramento (LGPD)
 *
 * SEGURANÇA:
 * - Sem dangerouslySetInnerHTML.
 * - Texto da mensagem nunca vai para localStorage/console.
 * - Links suspeitos são texto puro (SafeText).
 */

import { useState, useRef } from 'react'
import { analyzeMessage } from '../api/client'
import type { GuardiaoResponse } from '../types/api'
import { RiskGauge } from '../components/RiskGauge'
import { SafeText } from '../components/SafeText'

type Profile = 'standard' | 'low'

const MAX_LENGTH = 2000

export function GuardiaoPage() {
  const [message, setMessage] = useState('')
  const [profile, setProfile] = useState<Profile>('standard')
  const [userId, setUserId] = useState('U001')
  const [monitoringActive, setMonitoringActive] = useState(true)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<GuardiaoResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const resultRef = useRef<HTMLDivElement>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!message.trim()) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const data = await analyzeMessage({
        message,
        user_id: userId,
        language_profile: profile,
        monitoring_consent: monitoringActive,
      })
      setResult(data)
      // Move foco para o resultado (acessibilidade)
      setTimeout(() => resultRef.current?.focus(), 100)
    } catch (err) {
      // Nunca exibe detalhes internos ao usuário
      const msg = err instanceof Error ? err.message : 'Erro ao analisar a mensagem.'
      setError(msg.startsWith('Erro 5') ? 'Erro interno. Tente novamente em instantes.' : msg)
    } finally {
      setLoading(false)
    }
  }

  function handleClear() {
    setMessage('')
    setResult(null)
    setError(null)
  }

  const riskLabel = result?.risk_label ?? 'baixo'
  const hasIntervention = result?.requires_intervention && result?.intervention
  const hasPix = !!result?.transaction_id_analyzed

  return (
    <main className="page">
      <div className="page__inner">
        <header className="page__header">
          <h1 className="page__title">🛡️ Guardião</h1>
          <p className="page__subtitle">
            IA agêntica contra golpes de engenharia social
          </p>
        </header>

        {/* Controle de monitoramento — LGPD */}
        <section className="monitoring-control" aria-label="Controle de monitoramento">
          <div className="monitoring-control__row">
            <label htmlFor="monitoring-toggle" className="monitoring-control__label">
              <strong>Monitoramento ativo</strong>
              <span className="monitoring-control__note">
                {monitoringActive
                  ? 'Análise usa seu perfil financeiro sintético para detectar anomalias.'
                  : 'Análise somente da mensagem, sem cruzamento de perfil.'}
              </span>
            </label>
            <button
              id="monitoring-toggle"
              role="switch"
              aria-checked={monitoringActive}
              onClick={() => setMonitoringActive(v => !v)}
              className={`toggle-btn${monitoringActive ? ' toggle-btn--on' : ''}`}
            >
              {monitoringActive ? 'Pausar' : 'Ativar'}
            </button>
          </div>
          <p className="monitoring-control__lgpd">
            <strong>Dados usados:</strong> ID do usuário (sintético), padrão de transações simulado
            e sinais da análise (score, rótulos, timestamp). O texto da mensagem <strong>não é
            registrado</strong> em nenhum log.{' '}
            <em>
              Base legal: legítimo interesse para proteção contra fraude — LGPD art.&nbsp;7º,
              IX.{' '}
              <strong>⚠️ Texto jurídico a validar por profissional antes de uso em produção.</strong>
            </em>
          </p>
        </section>

        {/* Formulário de entrada */}
        <form onSubmit={handleSubmit} className="form" noValidate>
          <div className="form__group">
            <label htmlFor="message-input" className="form__label">
              Cole aqui o link, mensagem ou descrição que você recebeu
            </label>
            <textarea
              id="message-input"
              value={message}
              onChange={e => setMessage(e.target.value)}
              maxLength={MAX_LENGTH}
              rows={5}
              placeholder="Ex: &quot;Oi mãe, troquei o número, precisa me mandar R$ 800 agora&quot;"
              className="form__textarea"
              aria-describedby="message-hint"
              aria-required="true"
              disabled={loading}
              // Segurança: não persiste nem loga o conteúdo
            />
            <span id="message-hint" className="form__hint">
              {message.length}/{MAX_LENGTH} caracteres. O texto da mensagem nunca é registrado em logs.
            </span>
          </div>

          {/* Seletor de perfil */}
          <fieldset className="form__fieldset">
            <legend className="form__legend">Perfil de explicação</legend>
            <div className="radio-group">
              <label className="radio-group__option">
                <input
                  type="radio"
                  name="profile"
                  value="standard"
                  checked={profile === 'standard'}
                  onChange={() => setProfile('standard')}
                  aria-describedby="profile-standard-desc"
                />
                <span>Padrão</span>
                <span id="profile-standard-desc" className="radio-group__desc">
                  Explicação técnica completa
                </span>
              </label>
              <label className="radio-group__option">
                <input
                  type="radio"
                  name="profile"
                  value="low"
                  checked={profile === 'low'}
                  onChange={() => setProfile('low')}
                  aria-describedby="profile-low-desc"
                />
                <span>Linguagem simples</span>
                <span id="profile-low-desc" className="radio-group__desc">
                  Explicação direta, sem termos técnicos
                </span>
              </label>
            </div>
          </fieldset>

          {/* ID do usuário (demo) */}
          <div className="form__group form__group--inline">
            <label htmlFor="user-id" className="form__label">
              Perfil sintético (demo)
            </label>
            <select
              id="user-id"
              value={userId}
              onChange={e => setUserId(e.target.value)}
              className="form__select"
              disabled={!monitoringActive}
            >
              <option value="U001">U001 — Maria S. (baixa familiaridade tech)</option>
              <option value="U002">U002 — Carlos M. (perfil padrão)</option>
              <option value="U003">U003 — Roberto A. (jovem adulto)</option>
              <option value="">Sem perfil</option>
            </select>
          </div>

          <div className="form__actions">
            <button
              type="submit"
              className="btn btn--primary"
              disabled={loading || !message.trim()}
              aria-busy={loading}
            >
              {loading ? 'Analisando…' : 'Analisar mensagem'}
            </button>
            <button
              type="button"
              className="btn btn--secondary"
              onClick={handleClear}
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
            Analisando a mensagem em 6 etapas…
          </div>
        )}

        {/* Estado de erro */}
        {error && (
          <div role="alert" className="error-state" data-testid="error-state">
            <strong>Não foi possível analisar.</strong> {error}
          </div>
        )}

        {/* Resultado */}
        {result && (
          <section
            ref={resultRef}
            tabIndex={-1}
            aria-label="Resultado da análise"
            className="result"
            data-testid="result-section"
          >
            {/* Gauge de risco */}
            <RiskGauge
              score={result.risk_score}
              label={riskLabel as 'baixo' | 'médio' | 'alto' | 'crítico'}
            />

            {/* Revisão humana */}
            {result.requires_human_review && (
              <div role="alert" className="human-review-flag" data-testid="human-review-flag">
                <strong>Revisão humana recomendada.</strong> Este caso apresenta risco
                elevado e foi sinalizado para análise por um especialista.
              </div>
            )}

            {/* Intervenção */}
            {hasIntervention && result.intervention ? (
              <div className="intervention" data-testid="intervention-panel">
                <div className="intervention__header">
                  {/* Selo do tipo de golpe específico */}
                  {result.intervention.scam_name && (
                    <span className="intervention__scam-badge" data-testid="scam-badge">
                      {result.intervention.scam_name}
                    </span>
                  )}
                  {/* Fluxo (b): Pix em andamento → pausa */}
                  {result.intervention.pix_flow ? (
                    <span className="intervention__badge intervention__badge--pix">
                      Pix pausado para sua proteção
                    </span>
                  ) : (
                    <span className="intervention__badge">
                      Alerta de segurança
                    </span>
                  )}
                  <span className="intervention__profile">
                    Perfil: {result.intervention.language_profile_label}
                  </span>
                </div>

                {/* Mensagem principal — SafeText, nunca HTML */}
                <SafeText
                  text={result.intervention_message}
                  className="intervention__message"
                />

                {/* Como o golpe funciona */}
                {result.intervention.how_it_works && (
                  <div className="intervention__scam">
                    <SafeText
                      text={result.intervention.how_it_works}
                      as="p"
                      className="intervention__how"
                    />
                    {result.intervention.how_applied && (
                      <details className="intervention__details">
                        <summary>Como esse golpe é aplicado passo a passo</summary>
                        <SafeText
                          text={result.intervention.how_applied}
                          as="p"
                          className="intervention__applied"
                        />
                      </details>
                    )}
                  </div>
                )}

                {/* Sinais detectados */}
                {result.intervention.alert_signals.length > 0 && (
                  <details className="intervention__signals">
                    <summary>
                      {result.intervention.alert_signals.length} sinal(is) detectado(s)
                    </summary>
                    <ul aria-label="Sinais de alerta">
                      {result.intervention.alert_signals.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </details>
                )}

                {/* Próximo passo */}
                <div className="intervention__next-step" data-testid="next-step">
                  <h3>O que fazer agora</h3>
                  <SafeText
                    text={result.intervention.next_step}
                    className="intervention__next-step-text"
                  />
                </div>

                {/* Fluxo (b): botão de atendente quando Pix está pausado */}
                {result.intervention.pix_flow && (
                  <div className="intervention__pix-actions" data-testid="pix-actions">
                    <p className="intervention__pix-note">
                      Esta transação está temporariamente pausada para sua proteção.
                      Você decide o próximo passo.
                    </p>
                    <a
                      href="tel:40040001"
                      className="btn btn--danger"
                      data-testid="btn-attendant"
                    >
                      Falar com atendente BB (4004-0001)
                    </a>
                  </div>
                )}

                {/* Controle do cliente — sempre visível */}
                <div className="intervention__control" data-testid="user-control-note">
                  <SafeText
                    text={result.intervention.user_control_note}
                    className="intervention__control-text"
                  />
                </div>

                {/* Detalhes técnicos — recolhível, perfil standard */}
                <details className="intervention__technical">
                  <summary>Detalhes técnicos</summary>
                  <p>
                    Score de risco: {result.risk_score.toFixed(0)}% —
                    classificação: {result.risk_label}
                  </p>
                  {result.rules_triggered.filter(r => r.triggered).map(r => (
                    <p key={r.rule_id} className="intervention__rule">
                      Regra {r.rule_id}: {r.reason}
                    </p>
                  ))}
                </details>
              </div>
            ) : result && !result.requires_intervention ? (
              <div className="no-intervention" data-testid="no-intervention">
                <SafeText text={result.intervention_message} className="no-intervention__text" />
              </div>
            ) : null}

            {/* Sinais técnicos (perfil standard) */}
            {result.signals.length > 0 && (
              <details className="signals-detail">
                <summary>
                  Ver {result.signals.length} sinal(is) técnico(s) detectado(s)
                </summary>
                <ul className="signals-list" aria-label="Sinais técnicos">
                  {result.signals.map(s => (
                    <li key={s.signal_id} className="signals-list__item">
                      <strong>{s.label}</strong>: {s.description}
                      {s.evidence && (
                        <span className="signals-list__evidence" aria-label="Evidência na mensagem">
                          {' '}— evidência: <em>{s.evidence}</em>
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </details>
            )}

            {/* Acompanhamento */}
            <div className="followup" data-testid="followup-message">
              <h3 className="followup__title">Orientação final</h3>
              <SafeText text={result.followup_message} className="followup__text" />
            </div>

            {/* Nível 2 — anomalias de perfil */}
            {result.profile_found && result.anomalies.length > 0 && (
              <details className="anomalies-detail">
                <summary>
                  Análise de perfil ({result.anomalies.length} anomalia(s))
                </summary>
                <ul aria-label="Anomalias de perfil">
                  {result.anomalies.map(a => (
                    <li key={a.anomaly_id}>
                      <strong>{a.label}</strong>: {a.description}
                      <span className={`delta ${a.score_delta > 0 ? 'delta--up' : 'delta--down'}`}>
                        {a.score_delta > 0 ? `+${a.score_delta}` : a.score_delta} pts
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="score-breakdown">
                  Score: Nível 1 = {result.level1_score}% → Nível 2 ={' '}
                  {(result.level1_score + result.level2_score_delta).toFixed(1)}%
                </p>
              </details>
            )}
          </section>
        )}

        {/* Estado vazio */}
        {!result && !loading && !error && (
          <div className="empty-state" data-testid="empty-state">
            Cole uma mensagem suspeita acima para analisar.
          </div>
        )}
      </div>
    </main>
  )
}
