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
import { analyzeMessage, analyzeFile } from '../api/client'
import type { GuardiaoResponse } from '../types/api'
import { RiskGauge } from '../components/RiskGauge'
import { SafeText } from '../components/SafeText'

type Profile = 'standard' | 'low'

const MAX_LENGTH = 2000

// ── Anexo ──────────────────────────────────────────────────────────────────
const ATTACHMENT_ACCEPT_IMAGE = '.jpg,.jpeg,.png,.webp'
const ATTACHMENT_ACCEPT_AUDIO = '.mp3,.wav,.m4a,.ogg'
const ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024 // 10 MB

type AttachmentType = 'image' | 'audio'

interface AttachedFile {
  type: AttachmentType
  /** Referência ao File original para envio via FormData — nunca logado */
  rawFile: File
}

function validateAttachment(file: File): string | null {
  const imageTypes = ['image/jpeg', 'image/png', 'image/webp']
  const audioTypes = ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/mp4', 'audio/m4a', 'audio/ogg', 'audio/vnd.dlna.adts']
  const allAllowed = [...imageTypes, ...audioTypes]
  if (!allAllowed.includes(file.type) && file.type !== '') {
    // Fallback por extensão caso o MIME não seja detectado corretamente
    const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
    const validExts = ['jpg', 'jpeg', 'png', 'webp', 'mp3', 'wav', 'm4a', 'ogg']
    if (!validExts.includes(ext)) {
      return 'Formato não suportado. Envie uma imagem (JPG, PNG, WEBP) ou áudio (MP3, WAV, M4A, OGG).'
    }
  }
  if (file.size > ATTACHMENT_MAX_BYTES) {
    return 'O arquivo excede o limite de 10 MB.'
  }
  return null
}

// ── fim Anexo ───────────────────────────────────────────────────────────────

export function GuardiaoPage() {
  const [message, setMessage] = useState('')
  const [profile, setProfile] = useState<Profile>('standard')
  const [userId, setUserId] = useState('U001')
  const [monitoringActive, setMonitoringActive] = useState(true)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<GuardiaoResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const resultRef = useRef<HTMLDivElement>(null)

  // ── Estado do Anexo ────────────────────────────────────────────────────────
  const [attachment, setAttachment] = useState<AttachedFile | null>(null)
  const [attachmentError, setAttachmentError] = useState<string | null>(null)
  const [attachmentMenuOpen, setAttachmentMenuOpen] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const attachmentMenuRef = useRef<HTMLDivElement>(null)
  const [pendingAttachType, setPendingAttachType] = useState<AttachmentType | null>(null)
  // ── fim Estado do Anexo ────────────────────────────────────────────────────

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const hasText = message.trim().length > 0
    const hasAttachment = attachment !== null
    if (!hasText && !hasAttachment) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      let data: GuardiaoResponse
      if (attachment) {
        // Envia o arquivo bruto via FormData — o backend extrai o conteúdo
        // com GPT-4o Vision (imagem) ou Whisper (áudio) antes de analisar.
        // O texto livre do usuário vai como contexto adicional.
        data = await analyzeFile({
          file: attachment.rawFile,
          userId,
          languageProfile: profile,
          monitoringConsent: monitoringActive,
          contextText: message.trim(),
        })
      } else {
        data = await analyzeMessage({
          message,
          user_id: userId,
          language_profile: profile,
          monitoring_consent: monitoringActive,
        })
      }
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
    setAttachment(null)
    setAttachmentError(null)
  }

  // ── Handlers do Anexo ──────────────────────────────────────────────────────
  function openAttachmentPicker(type: AttachmentType) {
    setAttachmentMenuOpen(false)
    setPendingAttachType(type)
    if (fileInputRef.current) {
      fileInputRef.current.accept = type === 'image' ? ATTACHMENT_ACCEPT_IMAGE : ATTACHMENT_ACCEPT_AUDIO
      fileInputRef.current.value = ''
      fileInputRef.current.click()
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file || !pendingAttachType) return
    const validationError = validateAttachment(file)
    if (validationError) {
      setAttachmentError(validationError)
      setAttachment(null)
      setPendingAttachType(null)
      return
    }
    setAttachmentError(null)
    // Armazena apenas a referência ao File — sem ler o conteúdo no frontend
    // (privacidade: o conteúdo é processado exclusivamente no backend)
    setAttachment({ type: pendingAttachType, rawFile: file })
    setPendingAttachType(null)
  }

  function removeAttachment() {
    setAttachment(null)
    setAttachmentError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }
  // ── fim Handlers do Anexo ──────────────────────────────────────────────────

  const riskLabel = result?.risk_label ?? 'baixo'
  const hasIntervention = result?.requires_intervention && result?.intervention
  const hasPix = !!result?.transaction_id_analyzed

  return (
    <main className="gd-page">
      <header className="gd-hero">
        <div className="gd-hero__in">
          <a href="/src/pages/monitoramentoGuardiao.html" className="gd-back" aria-label="Voltar para a apresentação do Guardião">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5" /><path d="m12 19-7-7 7-7" /></svg>
          </a>
          <div className="gd-shield" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3Z" fill="#fcd116" />
              <path d="m8.5 12 2.6 2.6L16 9.7" stroke="#002a63" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div>
            <h1 className="gd-title">Guardião</h1>
            <p className="gd-sub">IA agêntica contra golpes de engenharia social</p>
          </div>
        </div>
      </header>

      <div className="gd-wrap">
        {/* Controle de monitoramento — LGPD */}
        <section
          className={`gd-card${monitoringActive ? '' : ' gd-off'}`}
          aria-label="Controle de monitoramento"
        >
          <div className="gd-status">
            <label htmlFor="monitoring-toggle">
              <span className="gd-status__h">
                <span className="gd-dot" aria-hidden="true" />
                <strong>{monitoringActive ? 'Monitoramento ativo' : 'Monitoramento pausado'}</strong>
              </span>
              <span className="gd-status__d" style={{ display: 'block' }}>
                {monitoringActive
                  ? 'Análise usa seu perfil financeiro sintético para detectar anomalias.'
                  : 'Análise somente da mensagem, sem cruzamento de perfil.'}
              </span>
            </label>
            <button
              id="monitoring-toggle"
              type="button"
              role="switch"
              aria-checked={monitoringActive}
              onClick={() => setMonitoringActive(v => !v)}
              className="gd-pill"
            >
              {monitoringActive ? 'Pausar' : 'Ativar'}
            </button>
          </div>
          <p className="gd-privacy">
            <strong>Dados usados:</strong> ID do usuário (sintético), padrão de transações simulado
            e sinais da análise (score, rótulos, timestamp). O texto da mensagem <strong>não é
            registrado</strong> em nenhum log.{' '}
            <em>
              Base legal: legítimo interesse para proteção contra fraude — LGPD art.&nbsp;7º, IX.
            </em>
            <strong className="gd-legal">⚠️ Texto jurídico a validar por profissional antes de uso em produção.</strong>
          </p>
        </section>

        {/* Formulário de entrada */}
        <form onSubmit={handleSubmit} className="gd-card" noValidate>
          <div>
            <label htmlFor="message-input" className="gd-label">
              Cole aqui o link, mensagem ou descrição que você recebeu
            </label>
            <textarea
              id="message-input"
              value={message}
              onChange={e => setMessage(e.target.value)}
              maxLength={MAX_LENGTH}
              rows={5}
              placeholder="Ex: “Oi mãe, troquei o número, precisa me mandar R$ 800 agora”"
              className="gd-textarea"
              aria-describedby="message-hint"
              aria-required="true"
              disabled={loading}
              // Segurança: não persiste nem loga o conteúdo
            />
            <div className="gd-hint-row">
              <span id="message-hint" className="gd-hint">
                {message.length}/{MAX_LENGTH} caracteres. O texto da mensagem nunca é registrado em logs.
              </span>

              {/* Botão Anexo */}
              <div className="gd-attach-wrap" ref={attachmentMenuRef}>
                <button
                  type="button"
                  className="gd-btn-attach"
                  aria-haspopup="true"
                  aria-expanded={attachmentMenuOpen}
                  onClick={() => setAttachmentMenuOpen(v => !v)}
                  disabled={loading}
                  aria-label="Anexar arquivo (imagem ou áudio)"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true" className="gd-attach-icon">
                    <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                  </svg>
                  Anexo
                </button>

                {attachmentMenuOpen && (
                  <div className="gd-attach-menu" role="menu" aria-label="Tipo de anexo">
                    <button
                      type="button"
                      role="menuitem"
                      className="gd-attach-menu__item"
                      onClick={() => openAttachmentPicker('image')}
                    >
                      🖼 Imagem (JPG, PNG, WEBP)
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      className="gd-attach-menu__item"
                      onClick={() => openAttachmentPicker('audio')}
                    >
                      🎵 Áudio (MP3, WAV, M4A, OGG)
                    </button>
                  </div>
                )}
              </div>

              {/* Input de arquivo oculto */}
              <input
                ref={fileInputRef}
                type="file"
                className="gd-attach-input-hidden"
                aria-hidden="true"
                tabIndex={-1}
                onChange={handleFileChange}
              />
            </div>

            {/* Exibição do arquivo anexado */}
            {attachment && (
              <div className="gd-attach-preview" role="status" aria-live="polite">
                <span className="gd-attach-preview__icon" aria-hidden="true">
                  {attachment.type === 'image' ? '🖼' : '🎵'}
                </span>
                <span className="gd-attach-preview__name">
                  {attachment.type === 'image' ? 'Imagem' : 'Áudio'} anexado
                </span>
                <button
                  type="button"
                  className="gd-attach-preview__remove"
                  onClick={removeAttachment}
                  aria-label="Remover anexo"
                >
                  ✕
                </button>
              </div>
            )}

            {/* Erro de validação do anexo */}
            {attachmentError && (
              <div role="alert" className="gd-attach-error">
                {attachmentError}
              </div>
            )}
          </div>

          {/* Seletor de perfil */}
          <fieldset className="gd-fieldset">
            <legend className="gd-legend">Perfil de explicação</legend>
            <div className="gd-opts">
              <label className="gd-opt">
                <input
                  type="radio"
                  name="profile"
                  value="standard"
                  checked={profile === 'standard'}
                  onChange={() => setProfile('standard')}
                  aria-describedby="profile-standard-desc"
                />
                <span className="gd-opt__box">
                  <strong>Padrão</strong>
                  <small id="profile-standard-desc">Explicação técnica completa</small>
                </span>
              </label>
              <label className="gd-opt">
                <input
                  type="radio"
                  name="profile"
                  value="low"
                  checked={profile === 'low'}
                  onChange={() => setProfile('low')}
                  aria-describedby="profile-low-desc"
                />
                <span className="gd-opt__box">
                  <strong>Linguagem simples</strong>
                  <small id="profile-low-desc">Explicação direta, sem termos técnicos</small>
                </span>
              </label>
            </div>
          </fieldset>

          {/* ID do usuário (demo) */}
          <fieldset className="gd-fieldset">
            <label htmlFor="user-id" className="gd-legend">
              Perfil sintético (demo)
            </label>
            <select
              id="user-id"
              value={userId}
              onChange={e => setUserId(e.target.value)}
              className="gd-select"
              disabled={!monitoringActive}
            >
              <option value="U001">U001 — Maria S. (baixa familiaridade tech)</option>
              <option value="U002">U002 — Carlos M. (perfil padrão)</option>
              <option value="U003">U003 — Roberto A. (jovem adulto)</option>
              <option value="">Sem perfil</option>
            </select>
          </fieldset>

          <div className="gd-actions">
            <button
              type="submit"
              className="gd-btn gd-btn--primary"
              disabled={loading || (!message.trim() && !attachment)}
              aria-busy={loading}
            >
              {loading
                ? 'Analisando…'
                : attachment && !message.trim()
                  ? 'Analisar anexo'
                  : 'Analisar mensagem'}
            </button>
            <button
              type="button"
              className="gd-btn gd-btn--ghost"
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
            {attachment ? 'Analisando o anexo em 6 etapas…' : 'Analisando a mensagem em 6 etapas…'}
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
            className="result gd-result"
            data-testid="result-section"
          >
            {/* Gauge de risco */}
            <RiskGauge
              score={result.risk_score}
              label={riskLabel as "baixo" | "médio" | "alto" | "crítico"}
            />

            {/* Revisão humanaSSSSSSSSSSs */}
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
                      className="gd-btn gd-btn--danger"
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