/**
 * SafeText — renderiza texto da API de forma segura.
 *
 * SEGURANÇA (T-13):
 * - Nunca usa dangerouslySetInnerHTML.
 * - Links suspeitos aparecem como texto simples, nunca clicáveis.
 * - Todo conteúdo da API é tratado como não confiável.
 */
interface SafeTextProps {
  text: string
  className?: string
  as?: 'p' | 'span' | 'li' | 'div'
}

// Detecta URLs que poderiam ser links maliciosos
function containsUrl(text: string): boolean {
  return /https?:\/\//i.test(text)
}

export function SafeText({ text, className, as: Tag = 'p' }: SafeTextProps) {
  // Divide por linhas preservando a estrutura, sem renderizar HTML
  const lines = text.split('\n')
  return (
    <Tag className={className}>
      {lines.map((line, i) => (
        <span key={i}>
          {containsUrl(line) ? (
            // Links aparecem como texto puro — nunca como <a>
            <span aria-label="URL suspeita — exibida como texto por segurança" className="url-as-text">
              {line}
            </span>
          ) : (
            line
          )}
          {i < lines.length - 1 && <br />}
        </span>
      ))}
    </Tag>
  )
}
