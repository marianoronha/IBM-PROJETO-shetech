/**
 * RiskGauge — indicador visual de risco (%).
 *
 * Auto-contido: o visual (card azul-marinho + anel) vem dos estilos
 * inline deste componente, então funciona com qualquer CSS.
 *
 * Acessibilidade:
 * - role="meter" com aria-valuenow, aria-valuemin, aria-valuemax, aria-label.
 * - Não depende apenas de cor: inclui rótulo textual e ícone.
 * - Contraste WCAG AA: fundo azul-marinho com cores claras no texto,
 *   no anel e na barra.
 */
import type { CSSProperties } from 'react'

interface RiskGaugeProps {
  score: number          // 0–100
  label: 'baixo' | 'médio' | 'alto' | 'crítico'
}

const NAVY = '#002a63'

const CONFIG = {
  baixo:   { icon: '🟢', text: 'Baixo',   onDark: '#6ee7a0' },
  médio:   { icon: '🟡', text: 'Médio',   onDark: '#ffd166' },
  alto:    { icon: '🔴', text: 'Alto',    onDark: '#ff8a80' },
  crítico: { icon: '🚨', text: 'Crítico', onDark: '#ff6b6b' },
}

const RING = 92
const RING_THICKNESS = 9

export function RiskGauge({ score, label }: RiskGaugeProps) {
  const cfg = CONFIG[label] ?? CONFIG['médio']
  const pct = Math.min(Math.max(score, 0), 100)

  const card: CSSProperties = {
    position: 'relative',
    overflow: 'hidden',
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 20,
    margin: 0,
    padding: '22px 24px',
    border: 0,
    borderRadius: 24,
    background: NAVY,
    color: '#fff',
    boxShadow: '0 1px 2px rgba(10,30,70,.06), 0 8px 24px rgba(10,30,70,.12)',
  }

  const deco: CSSProperties = {
    position: 'absolute',
    right: -60,
    top: -70,
    width: 200,
    height: 200,
    borderRadius: '50%',
    border: '22px solid rgba(255,255,255,.08)',
    pointerEvents: 'none',
  }

  const ring: CSSProperties = {
    position: 'relative',
    flex: 'none',
    width: RING,
    height: RING,
    borderRadius: '50%',
    display: 'grid',
    placeItems: 'center',
    background: `conic-gradient(${cfg.onDark} ${pct}%, rgba(255,255,255,.2) 0)`,
  }

  const ringHole: CSSProperties = {
    position: 'absolute',
    inset: RING_THICKNESS,
    borderRadius: '50%',
    background: NAVY,
  }

  const scoreStyle: CSSProperties = {
    position: 'relative',
    margin: 0,
    fontSize: '1.5rem',
    fontWeight: 800,
    lineHeight: 1,
    color: cfg.onDark,
  }

  return (
    <div
      style={card}
      className="risk-gauge"
      data-level={label}
      data-testid="risk-gauge"
    >
      <span aria-hidden="true" style={deco} />

      {/* Anel com a pontuação */}
      <div style={ring} className="risk-gauge__ring">
        <span aria-hidden="true" style={ringHole} />
        <span
          className="risk-gauge__score"
          style={scoreStyle}
          aria-label={`Pontuação de risco: ${pct}%`}
        >
          {pct.toFixed(0)}%
        </span>
      </div>

      <div style={{ position: 'relative', flex: 1, minWidth: 180 }}>
        {/* Texto e ícone — não depende só de cor */}
        <div
          className="risk-gauge__header"
          style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '0 0 12px' }}
        >
          <span aria-hidden="true" className="risk-gauge__icon">{cfg.icon}</span>
          <span
            className="risk-gauge__label"
            style={{ color: cfg.onDark, fontSize: '1.4rem', fontWeight: 800 }}
          >
            Risco {cfg.text}
          </span>
        </div>

        {/* Barra de progresso acessível */}
        <div
          role="meter"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Risco ${cfg.text}: ${pct}%`}
          className="risk-gauge__bar-track"
          style={{
            height: 10,
            borderRadius: 999,
            overflow: 'hidden',
            background: 'rgba(255,255,255,.2)',
          }}
        >
          <div
            className="risk-gauge__bar-fill"
            style={{
              width: `${pct}%`,
              height: '100%',
              borderRadius: 999,
              background: cfg.onDark,
              transition: 'width .4s ease',
            }}
            data-testid="risk-bar"
          />
        </div>
      </div>
    </div>
  )
}