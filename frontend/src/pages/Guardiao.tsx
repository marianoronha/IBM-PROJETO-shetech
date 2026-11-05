/**
 * Guardião — UI principal (T-13).
 *
 * - Entrada de mensagens, links e descrições
 * - Anexos de imagens e áudios
 * - Indicador de risco e classificação
 * - Tipo do golpe e como é aplicado
 * - Sinais de alerta
 * - Orientações de segurança
 * - Perfil de linguagem
 * - Monitoramento (LGPD)
 *
 * SEGURANÇA:
 * - Sem dangerouslySetInnerHTML
 * - Sem armazenar mensagens no localStorage
 * - Sem registrar conteúdo dos anexos no console
 * - Links suspeitos exibidos como texto puro (SafeText)
 */

import { useState, useRef, useEffect } from 'react'
import { analyzeMessage, analyzeFile } from '../api/client'
import type { GuardiaoResponse } from '../types/api'
import { RiskGauge } from '../components/RiskGauge'
import { SafeText } from '../components/SafeText'

type Profile = 'standard' | 'low'

const MAX_LENGTH = 2000

// ── Anexo ───────────────────────────────────────

const ATTACHMENT_ACCEPT_IMAGE = '.jpg,.jpeg,.png,.webp'
const ATTACHMENT_ACCEPT_AUDIO = '.mp3,.wav,.m4a,.ogg'
const ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024

type AttachmentType = 'image' | 'audio'

interface AttachedFile {
  type: AttachmentType

  /** Referência ao arquivo original para envio via FormData */
  rawFile: File
}

function validateAttachment(file: File): string | null {
  const imageTypes = [
    'image/jpeg',
    'image/png',
    'image/webp',
  ]

  const audioTypes = [
    'audio/mpeg',
    'audio/wav',
    'audio/x-wav',
    'audio/mp4',
    'audio/m4a',
    'audio/ogg',
    'audio/vnd.dlna.adts',
  ]

  const allAllowed = [...imageTypes, ...audioTypes]

  if (!allAllowed.includes(file.type) && file.type !== '') {
    const ext = file.name.split('.').pop()?.toLowerCase() ?? ''

    const validExts = [
      'jpg', 'jpeg', 'png', 'webp',
      'mp3', 'wav', 'm4a', 'ogg',
    ]

    if (!validExts.includes(ext)) {
      return 'Formato não suportado. Envie uma imagem (JPG, PNG, WEBP) ou áudio (MP3, WAV, M4A, OGG).'
    }
  }

  if (file.size > ATTACHMENT_MAX_BYTES) {
    return 'O arquivo excede o limite de 10 MB.'
  }

  return null
}

// ── Página Guardião ─────────────────────────────

/**
 * Separa o número de destaque da descrição da anomalia.
 * Procura "12.7x" ou "54.3%" em qualquer parte do texto.
 * "12.7x o Pix médio histórico (R$ 150.00)." -> big "12,7x",
 *   text "maior que o Pix médio histórico (R$ 150,00)."
 * "54.3% da renda mensal estimada." -> big "54%",
 *   text "da renda mensal estimada."
 * Se o número estiver no meio da frase, o texto completo é mantido.
 * Se não houver número, devolve big = null.
 */
function splitHighlight(
  description: string
): { big: string | null; text: string } {
  const m = description.match(/(\d+(?:[.,]\d+)?)\s*(x|×|%)/i)
  if (!m || m.index === undefined) {
    return { big: null, text: description }
  }
  const num = parseFloat(m[1].replace(',', '.'))
  const unit = m[2] === '%' ? '%' : 'x'
  const big =
    unit === '%'
      ? `${Math.round(num)}%`
      : `${String(num).replace('.', ',')}x`
  const commaDecimals = (t: string) => t.replace(/(\d)\.(\d)/g, '$1,$2')

  const atStart = description.slice(0, m.index).trim() === ''
  if (!atStart) return { big, text: commaDecimals(description) }

  let text = commaDecimals(description.slice(m.index + m[0].length).trim())
  if (unit === 'x' && !/^maior/i.test(text)) text = `maior que ${text}`
  return { big, text }
}

export function GuardiaoPage() {
  const [message, setMessage] = useState('')
  const [profile, setProfile] = useState<Profile>('standard')
  const [userId, setUserId] = useState('U001')
  const [monitoringActive, setMonitoringActive] = useState(true)

  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<GuardiaoResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const resultRef = useRef<HTMLDivElement>(null)

  // ── Estado do Anexo ───────────────────────────

  const [attachment, setAttachment] =
    useState<AttachedFile | null>(null)

  const [attachmentError, setAttachmentError] =
    useState<string | null>(null)

  const [attachmentMenuOpen, setAttachmentMenuOpen] =
    useState(false)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const attachmentMenuRef = useRef<HTMLDivElement>(null)
  const attachBtnRef = useRef<HTMLButtonElement>(null)

  const [pendingAttachType, setPendingAttachType] =
    useState<AttachmentType | null>(null)

  // ── Fechar menu de anexo com Esc / clique fora ──
  useEffect(() => {
    if (!attachmentMenuOpen) return

    function handleClickOutside(e: MouseEvent) {
      if (
        attachmentMenuRef.current &&
        !attachmentMenuRef.current.contains(e.target as Node)
      ) {
        setAttachmentMenuOpen(false)
      }
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setAttachmentMenuOpen(false)
        attachBtnRef.current?.focus()
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [attachmentMenuOpen])

  // ── Análise de mensagens e arquivos ──────────

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
        // Envia o arquivo bruto via FormData.
        // O backend extrai o conteúdo com GPT-4o Vision
        // (imagem) ou Whisper (áudio).
        // O texto livre é enviado como contexto adicional.

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

      // Acessibilidade: foco no resultado
      setTimeout(() => resultRef.current?.focus(), 100)

    } catch (err) {
      const msg = err instanceof Error
        ? err.message
        : 'Erro ao analisar a mensagem.'

      setError(
        msg.startsWith('Erro 5')
          ? 'Erro interno. Tente novamente em instantes.'
          : msg
      )
    } finally {
      setLoading(false)
    }
  }

  // ── Limpar formulário ────────────────────────

  function handleClear() {
    setMessage('')
    setResult(null)
    setError(null)
    setAttachment(null)
    setAttachmentError(null)
    setAttachmentMenuOpen(false)
    setPendingAttachType(null)

    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  // ── Handlers do Anexo ────────────────────────

  function openAttachmentPicker(type: AttachmentType) {
    setAttachmentMenuOpen(false)
    setPendingAttachType(type)

    if (fileInputRef.current) {
      fileInputRef.current.accept =
        type === 'image'
          ? ATTACHMENT_ACCEPT_IMAGE
          : ATTACHMENT_ACCEPT_AUDIO

      fileInputRef.current.value = ''
      fileInputRef.current.click()
    }
  }

  function handleFileChange(
    e: React.ChangeEvent<HTMLInputElement>
  ) {
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

    // Guarda apenas a referência ao arquivo.
    // O conteúdo é processado exclusivamente no backend.
    setAttachment({
      type: pendingAttachType,
      rawFile: file,
    })

    setPendingAttachType(null)
  }

  function removeAttachment() {
    setAttachment(null)
    setAttachmentError(null)

    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  // ── Dados do resultado ───────────────────────

  const riskLabel = result?.risk_label ?? 'baixo'

  const hasIntervention =
    result?.requires_intervention && result?.intervention

  // ── Interface ────────────────────────────────

  return (
    <main className="gd-page">

      {/* Cabeçalho */}
      <header className="gd-hero">
        <div className="gd-hero__in">

          <a
            href="/src/pages/monitoramentoGuardiao.html"
            className="gd-back"
            aria-label="Voltar para a apresentação do Guardião"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M19 12H5" />
              <path d="m12 19-7-7 7-7" />
            </svg>
          </a>

          <div className="gd-shield" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path
                d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3Z"
                fill="#fcd116"
              />
              <path
                d="m8.5 12 2.6 2.6L16 9.7"
                stroke="#002a63"
                strokeWidth="2.2"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>

          <div>
            <h1 className="gd-title">Guardião</h1>
            <p className="gd-sub">
              IA agêntica contra golpes de engenharia social
            </p>
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
                <strong>
                  {monitoringActive
                    ? 'Monitoramento ativo'
                    : 'Monitoramento pausado'}
                </strong>
              </span>

              <span
                className="gd-status__d"
                style={{ display: 'block' }}
              >
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
            <strong>Dados usados:</strong> ID do usuário
            (sintético), padrão de transações simulado
            e sinais da análise (score, rótulos, timestamp).
            O texto da mensagem <strong>não é registrado</strong>
            {' '}em logs pela interface.{' '}

            <em>
              Base legal: legítimo interesse para proteção
              contra fraude — LGPD art.&nbsp;7º, IX.
            </em>

            <strong className="gd-legal">
              ⚠️ Texto jurídico a validar por profissional
              antes de uso em produção.
            </strong>
          </p>
        </section>

        {/* Formulário de entrada */}
        <form
          onSubmit={handleSubmit}
          className="gd-card"
          noValidate
        >
          <div>
            <label
              htmlFor="message-input"
              className="gd-label"
            >
              Cole aqui o link, mensagem ou descrição que você recebeu
            </label>

            <textarea
              id="message-input"
              value={message}
              onChange={e => setMessage(e.target.value)}
              maxLength={MAX_LENGTH}
              rows={5}
              placeholder="Ex: Oi mãe, troquei o número, precisa me mandar R$ 800 agora"
              className="gd-textarea"
              aria-describedby="message-hint"
              disabled={loading}
            />

            {/* Contador e botão Anexo */}
            <div className="gd-hint-row">

              <span
                id="message-hint"
                className="gd-hint"
              >
                {message.length}/{MAX_LENGTH} caracteres.
                O texto da mensagem nunca é registrado
                em logs pela interface.
              </span>

              <div
                className="gd-attach-wrap"
                ref={attachmentMenuRef}
              >
                <button
                  ref={attachBtnRef}
                  type="button"
                  className="gd-btn-attach"
                  aria-haspopup="true"
                  aria-expanded={attachmentMenuOpen}
                  onClick={() =>
                    setAttachmentMenuOpen(v => !v)
                  }
                  disabled={loading}
                  aria-label="Anexar arquivo (imagem ou áudio)"
                >
                  <svg
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                    className="gd-attach-icon"
                  >
                    <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                  </svg>
                  Anexo
                </button>

                {attachmentMenuOpen && (
                  <div
                    className="gd-attach-menu"
                    role="menu"
                    aria-label="Tipo de anexo"
                  >
                    <button
                      type="button"
                      role="menuitem"
                      className="gd-attach-menu__item"
                      onClick={() =>
                        openAttachmentPicker('image')
                      }
                    >
                      🖼 Imagem (JPG, PNG, WEBP)
                    </button>

                    <button
                      type="button"
                      role="menuitem"
                      className="gd-attach-menu__item"
                      onClick={() =>
                        openAttachmentPicker('audio')
                      }
                    >
                      🎵 Áudio (MP3, WAV, M4A, OGG)
                    </button>
                  </div>
                )}
              </div>

              {/* Input oculto */}
              <input
                ref={fileInputRef}
                type="file"
                className="gd-attach-input-hidden"
                aria-hidden="true"
                tabIndex={-1}
                onChange={handleFileChange}
              />

            </div>

            {/* Arquivo anexado */}
            {attachment && (
              <div
                className="gd-attach-preview"
                role="status"
                aria-live="polite"
              >
                <span
                  className="gd-attach-preview__icon"
                  aria-hidden="true"
                >
                  {attachment.type === 'image' ? '🖼' : '🎵'}
                </span>

                <span className="gd-attach-preview__name">
                  {attachment.rawFile.name}
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

            {/* Erro de anexo */}
            {attachmentError && (
              <div
                role="alert"
                className="gd-attach-error"
              >
                {attachmentError}
              </div>
            )}

          </div>

          {/* Seletor de perfil */}
          <fieldset className="gd-fieldset">
            <legend className="gd-legend">
              Perfil de explicação
            </legend>

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
                  <small id="profile-standard-desc">
                    Explicação técnica completa
                  </small>
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
                  <small id="profile-low-desc">
                    Explicação direta, sem termos técnicos
                  </small>
                </span>
              </label>

            </div>
          </fieldset>

          {/* ID do usuário */}
          <fieldset className="gd-fieldset">
            <label
              htmlFor="user-id"
              className="gd-legend"
            >
              Perfil sintético (demo)
            </label>

            <select
              id="user-id"
              value={userId}
              onChange={e => setUserId(e.target.value)}
              className="gd-select"
              disabled={!monitoringActive}
            >
              <option value="U001">
                U001 — Maria S. (baixa familiaridade tech)
              </option>

              <option value="U002">
                U002 — Carlos M. (perfil padrão)
              </option>

              <option value="U003">
                U003 — Roberto A. (jovem adulto)
              </option>

              <option value="">
                Sem perfil
              </option>
            </select>
          </fieldset>

          {/* Botões de ação */}
          <div className="gd-actions">
            <button
              type="submit"
              className="gd-btn gd-btn--primary"
              disabled={
                loading || (!message.trim() && !attachment)
              }
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
          <div
            role="status"
            aria-live="polite"
            className="loading-state"
          >
            <span
              className="loading-state__spinner"
              aria-hidden="true"
            />

            {attachment
              ? 'Analisando o anexo em 6 etapas…'
              : 'Analisando a mensagem em 6 etapas…'}
          </div>
        )}

        {/* Estado de erro */}
        {error && (
          <div
            role="alert"
            className="error-state"
            data-testid="error-state"
          >
            <strong>Não foi possível analisar.</strong>
            {' '}{error}
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

            {/* Indicador de risco */}
            <RiskGauge
              score={result.risk_score}
              label={
                riskLabel as
                  'baixo' | 'médio' | 'alto' | 'crítico'
              }
            />

            {/* Revisão humana */}
            {result.requires_human_review && (
              <div
                role="alert"
                className="human-review-flag"
                data-testid="human-review-flag"
              >
                <strong>Revisão humana recomendada.</strong>
                {' '}Este caso apresenta risco elevado e foi
                sinalizado para análise por um especialista.
              </div>
            )}

            {/* Intervenção */}
            {hasIntervention && result.intervention ? (
              <div
                className="intervention"
                data-testid="intervention-panel"
              >

                <div className="intervention__header">

                  {/* Tipo específico do golpe */}
                  {result.intervention.scam_name && (
                    <span
                      className="intervention__scam-badge"
                      data-testid="scam-badge"
                    >
                      {result.intervention.scam_name}
                    </span>
                  )}

                  {/* Pix em andamento */}
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

                {/* Mensagem principal */}
                <SafeText
                  text={result.intervention_message}
                  className="intervention__message"
                />

                {/* Como funciona o golpe */}
                {result.intervention.how_it_works && (
                  <div className="intervention__scam">

                    <SafeText
                      text={result.intervention.how_it_works}
                      as="p"
                      className="intervention__how"
                    />

                    {result.intervention.how_applied && (
                      <details className="intervention__details">
                        <summary>
                          Como esse golpe é aplicado passo a passo
                        </summary>

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
                      {result.intervention.alert_signals.length}
                      {' '}sinal(is) detectado(s)
                    </summary>

                    <ul aria-label="Sinais de alerta">
                      {result.intervention.alert_signals.map(
                        (s, i) => (
                          <li key={i}>{s}</li>
                        )
                      )}
                    </ul>
                  </details>
                )}

                {/* Próximo passo */}
                <div
                  className="intervention__next-step"
                  data-testid="next-step"
                >
                  <h3>O que fazer agora</h3>

                  <SafeText
                    text={result.intervention.next_step}
                    className="intervention__next-step-text"
                  />
                </div>

                {/* Caixa de proteção: Pix pausado ou alerta geral */}
                <div
                  className="intervention__pix-actions"
                  data-testid={
                    result.intervention.pix_flow
                      ? 'pix-actions'
                      : 'alert-actions'
                  }
                >
                  <div className="intervention__pix-text">
                    <p className="intervention__pix-title">
                      {result.intervention.pix_flow
                        ? 'Pix pausado para sua proteção'
                        : 'Alerta de segurança'}
                    </p>
                    <p className="intervention__pix-note">
                      Você decide o próximo passo.
                      {result.intervention.pix_flow && (
                        <span className="gd-sr-only">
                          {' '}Esta transação está temporariamente
                          pausada.
                        </span>
                      )}
                    </p>
                  </div>

                  <a
                    href="tel:40040001"
                    className="gd-btn gd-btn--danger"
                    data-testid={
                      result.intervention.pix_flow
                        ? 'btn-attendant'
                        : 'btn-attendant-alert'
                    }
                    aria-label="Falar com atendente BB, telefone 4004-0001"
                  >
                    <span aria-hidden="true">📞</span>
                    {' '}Falar com atendente BB
                  </a>
                </div>

                {/* Controle do cliente */}
                <div
                  className="intervention__control"
                  data-testid="user-control-note"
                >
                  <SafeText
                    text={result.intervention.user_control_note}
                    className="intervention__control-text"
                  />
                </div>

                {/* Detalhes técnicos */}
                <details className="intervention__technical">
                  <summary>Detalhes técnicos</summary>

                  <p>
                    Score de risco: {result.risk_score.toFixed(0)}%
                    {' '}— classificação: {result.risk_label}
                  </p>

                  {result.rules_triggered
                    .filter(r => r.triggered)
                    .map(r => (
                      <p
                        key={r.rule_id}
                        className="intervention__rule"
                      >
                        Regra {r.rule_id}: {r.reason}
                      </p>
                    ))}
                </details>

              </div>

            ) : result && !result.requires_intervention ? (
              <div
                className="no-intervention"
                data-testid="no-intervention"
              >
                <SafeText
                  text={result.intervention_message}
                  className="no-intervention__text"
                />
              </div>
            ) : null}

            {/* Sinais técnicos */}
            {result.signals.length > 0 && (
              <details className="signals-detail">
                <summary>
                  Ver {result.signals.length}
                  {' '}sinal(is) técnico(s) detectado(s)
                </summary>

                <ul
                  className="signals-list"
                  aria-label="Sinais técnicos"
                >
                  {result.signals.map(s => (
                    <li
                      key={s.signal_id}
                      className="signals-list__item"
                    >
                      <strong className="signals-list__label">
                        {s.label}
                      </strong>
                      <span className="signals-list__desc">
                        {s.description}
                      </span>

                      {s.evidence && (
                        <span
                          className="signals-list__evidence"
                          aria-label="Evidência na mensagem"
                        >
                          <span className="signals-list__tag">
                            Evidência
                          </span>
                          <em>{s.evidence}</em>
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </details>
            )}

            {/* Acompanhamento */}
            <div
              className="followup"
              data-testid="followup-message"
            >
              <h3 className="followup__title">
                Orientação final
              </h3>

              <SafeText
                text={result.followup_message}
                className="followup__text"
              />
            </div>

            {/* Perfil: o que chamou atenção */}
            {result.profile_found &&
              result.anomalies.length > 0 && (
                <section
                  className="gd-profile"
                  aria-labelledby="gd-profile-title"
                  data-testid="profile-analysis"
                >
                  <h3
                    id="gd-profile-title"
                    className="gd-profile__title"
                  >
                    O que chamou atenção no seu perfil
                  </h3>
                  <p className="gd-profile__sub">
                    Comparamos o pedido com o seu histórico.
                  </p>

                  <div
                    className="gd-profile__grid"
                    role="list"
                    aria-label="Anomalias de perfil"
                  >
                    {result.anomalies.map(a => {
                      const { big, text } = splitHighlight(a.description)
                      return (
                        <div
                          key={a.anomaly_id}
                          role="listitem"
                          className="gd-profile__card"
                        >
                          <span className="gd-sr-only">
                            {a.label}:{' '}
                          </span>
                          <span
                            className={
                              big
                                ? 'gd-profile__big'
                                : 'gd-profile__big gd-profile__big--text'
                            }
                          >
                            {big ?? a.label}
                          </span>
                          <p className="gd-profile__text">
                            {big ? text : a.description}
                          </p>
                          <span
                            className={`delta ${
                              a.score_delta > 0
                                ? 'delta--up'
                                : 'delta--down'
                            }`}
                          >
                            {a.score_delta > 0
                              ? `+${a.score_delta}`
                              : a.score_delta}
                            {' '}pts
                          </span>
                        </div>
                      )
                    })}
                  </div>

                  <p className="gd-profile__sum score-breakdown">
                    <span aria-hidden="true">🧮</span>
                    <span>
                      Score da mensagem{' '}
                      <strong>{Math.round(result.level1_score)}%</strong>
                      {' '}+ perfil{' '}
                      <strong>
                        {Math.round(result.level2_score_delta)} pts
                      </strong>
                      {' '}= risco final{' '}
                      <strong>
                        {Math.round(
                          result.level1_score +
                            result.level2_score_delta
                        )}%
                      </strong>
                    </span>
                  </p>
                </section>
              )}

          </section>
        )}

        {/* Estado vazio */}
        {!result && !loading && !error && (
          <div
            className="empty-state"
            data-testid="empty-state"
          >
            Cole uma mensagem suspeita acima para analisar.
            Você também pode anexar uma imagem ou áudio.
          </div>
        )}

      </div>
    </main>
  )
}