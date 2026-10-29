/**
 * DisclaimerBanner — aviso obrigatório sempre visível.
 *
 * RF-D-10, RN-06: SEMPRE visível, sem precisar rolar.
 * Acessibilidade: role="note", contraste adequado.
 */
interface DisclaimerBannerProps {
  text?: string
}

const DEFAULT_TEXT =
  '⚠️ As simulações são estimativas para fins educacionais. ' +
  'Não garantem resultados futuros nem constituem recomendação de investimento.'

export function DisclaimerBanner({ text = DEFAULT_TEXT }: DisclaimerBannerProps) {
  return (
    <aside
      role="note"
      aria-label="Aviso importante sobre a simulação"
      className="disclaimer-banner"
      data-testid="disclaimer-banner"
    >
      {text}
    </aside>
  )
}
