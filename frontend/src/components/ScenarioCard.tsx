/**
 * ScenarioCard — exibe a comparação atual vs. alternativo do BB Decision.
 * Valores exibidos exatamente como vieram da API — sem recálculo no front.
 */
interface ScenarioCardProps {
  label: string
  data: Record<string, unknown>
  highlight?: boolean
}

const FIELD_LABELS: Record<string, string> = {
  despesas_mensais: 'Despesas mensais',
  saldo_disponivel: 'Saldo disponível',
  comprometimento_renda_pct: 'Comprometimento de renda (%)',
  reserva_emergencia: 'Reserva de emergência',
  meses_reserva_cobre: 'Meses de reserva',
  renda_mensal: 'Renda mensal',
  parcela_mensal: 'Parcela mensal',
  total_pago: 'Total pago',
  juros_totais: 'Juros totais',
  novas_despesas: 'Novas despesas mensais',
  novo_saldo_disponivel: 'Novo saldo disponível',
  novo_comprometimento_renda_pct: 'Novo comprometimento (%)',
  taxa_mensal_pct: 'Taxa de juros (%/mês)',
  num_parcelas: 'Número de parcelas',
  deficit_mensal: 'Déficit mensal',
  meses_perda: 'Meses de perda',
  reserva_restante: 'Reserva restante',
  reserva_insuficiente: 'Reserva insuficiente?',
  nova_renda_mensal: 'Nova renda mensal',
  novo_saldo_disponivel2: 'Novo saldo disponível',
  meses_reserva_suporta_transicao: 'Meses de transição suportados',
  variacao_renda_mensal: 'Variação de renda mensal',
  valor_imovel: 'Valor do imóvel',
  entrada: 'Entrada',
  financiamento: 'Financiamento',
  prestacao_mensal: 'Prestação mensal',
  prazo_meses: 'Prazo (meses)',
  custo_total_imovel: 'Custo total do imóvel',
}

function formatValue(value: unknown): string {
  if (typeof value === 'boolean') return value ? 'Sim' : 'Não'
  if (typeof value === 'number') {
    // Valores com casas decimais → moeda BRL (exceto percentuais e contagens)
    if (Number.isInteger(value) && value > 12) return String(value)
    if (value > 1 && !Number.isInteger(value)) {
      return `R$ ${value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    }
    return String(value)
  }
  return String(value ?? '—')
}

export function ScenarioCard({ label, data, highlight = false }: ScenarioCardProps) {
  const entries = Object.entries(data).filter(([, v]) => v !== null && v !== undefined)

  return (
    <div
      className={`scenario-card${highlight ? ' scenario-card--highlight' : ''}`}
      data-testid={`scenario-card-${label.toLowerCase().replace(/\s/g, '-')}`}
    >
      <h3 className="scenario-card__title">{label}</h3>
      <dl className="scenario-card__list">
        {entries.map(([key, value]) => (
          <div key={key} className="scenario-card__row">
            <dt className="scenario-card__key">
              {FIELD_LABELS[key] ?? key.replace(/_/g, ' ')}
            </dt>
            <dd className="scenario-card__value">{formatValue(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
