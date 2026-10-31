/**
 * RiskGauge — indicador visual de risco (%).
 *
 * Acessibilidade:
 * - role="meter" com aria-valuenow, aria-valuemin, aria-valuemax, aria-label.
 * - Não depende apenas de cor: inclui rótulo textual e ícone.
 * - Contraste WCAG AA garantido pelas cores escolhidas.
 */
interface RiskGaugeProps {
  score: number          // 0–100
  label: 'baixo' | 'médio' | 'alto' | 'crítico'
}

const CONFIG = {
  baixo:   { color: '#1a7f37', bg: '#dcfce7', icon: '🟢', text: 'Baixo',   border: '#1a7f37' },
  médio:   { color: '#9a6700', bg: '#fef9c3', icon: '🟡', text: 'Médio',   border: '#9a6700' },
  alto:    { color: '#b91c1c', bg: '#fee2e2', icon: '🔴', text: 'Alto',    border: '#b91c1c' },
  crítico: { color: '#7f1d1d', bg: '#fecaca', icon: '🚨', text: 'Crítico', border: '#7f1d1d' },
}

export function RiskGauge({ score, label }: RiskGaugeProps) {
  const cfg = CONFIG[label] ?? CONFIG['médio']
  const pct = Math.min(Math.max(score, 0), 100)

  return (
    <div
      style={{ border: `2px solid ${cfg.border}`, background: cfg.bg }}
      className="risk-gauge"
      data-testid="risk-gauge"
    >
      {/* Texto e ícone — não depende só de cor */}
      <div className="risk-gauge__header">
        <span aria-hidden="true" className="risk-gauge__icon">{cfg.icon}</span>
        <span className="risk-gauge__label" style={{ color: cfg.color }}>
          Risco {cfg.text}
        </span>
        <span className="risk-gauge__score" style={{ color: cfg.color }}
          aria-label={`Pontuação de risco: ${pct}%`}>
          {pct.toFixed(0)}%
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
      >
        <div
          className="risk-gauge__bar-fill"
          style={{ width: `${pct}%`, background: cfg.color }}
          data-testid="risk-bar"
        />
      </div>
    </div>
  )
}
