/**
 * SafeText — renderiza texto da API de forma segura.
 *
 * SEGURANÇA (T-13):
 * - Nunca usa dangerouslySetInnerHTML.
 * - Links suspeitos aparecem como texto simples, nunca clicáveis.
 * - Todo conteúdo da API é tratado como não confiável.
 *
 * FORMATAÇÃO:
 * - Texto simples continua como antes (linhas separadas por <br>).
 * - Se o texto tiver itens numerados ("1. ...") ou com marcador
 *   ("- ...", "• ..."), eles viram <ol>/<ul> de verdade, e linhas
 *   de continuação são anexadas ao item anterior.
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

const ORDERED = /^\s*\d{1,2}[.)]\s+(.*)$/
const BULLET = /^\s*[-•*]\s+(.*)$/

type Block =
  | { kind: 'p'; lines: string[] }
  | { kind: 'ol' | 'ul'; items: string[] }

function parseBlocks(text: string): Block[] {
  const blocks: Block[] = []
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    const last = blocks[blocks.length - 1]

    if (!line) {
      // linha em branco encerra o parágrafo atual
      if (last?.kind === 'p') blocks.push({ kind: 'p', lines: [] })
      continue
    }

    const ol = ORDERED.exec(line)
    const ul = ol ? null : BULLET.exec(line)

    if (ol || ul) {
      const kind = ol ? 'ol' : 'ul'
      const content = (ol ?? ul)![1]
      if (last?.kind === kind) last.items.push(content)
      else blocks.push({ kind, items: [content] })
      continue
    }

    if (last && last.kind !== 'p') {
      // continuação de um item de lista
      last.items[last.items.length - 1] += ' ' + line
    } else if (last?.kind === 'p') {
      last.lines.push(line)
    } else {
      blocks.push({ kind: 'p', lines: [line] })
    }
  }
  return blocks.filter(b => (b.kind === 'p' ? b.lines.length > 0 : true))
}

function Inline({ text }: { text: string }) {
  return containsUrl(text) ? (
    // Links aparecem como texto puro — nunca como <a>
    <span
      aria-label="URL suspeita — exibida como texto por segurança"
      className="url-as-text"
    >
      {text}
    </span>
  ) : (
    <>{text}</>
  )
}

export function SafeText({ text, className, as: Tag = 'p' }: SafeTextProps) {
  const hasList = text.split('\n').some(l => ORDERED.test(l) || BULLET.test(l))
  const hasParagraphs = /\n\s*\n/.test(text.trim())

  // Caminho simples: comportamento original
  if (!hasList && !hasParagraphs) {
    const lines = text.split('\n')
    return (
      <Tag className={className}>
        {lines.map((line, i) => (
          <span key={i}>
            <Inline text={line} />
            {i < lines.length - 1 && <br />}
          </span>
        ))}
      </Tag>
    )
  }

  // Caminho estruturado: parágrafos e listas
  const blocks = parseBlocks(text)
  return (
    <div className={`safe-text ${className ?? ''}`.trim()}>
      {blocks.map((b, i) => {
        if (b.kind === 'p') {
          return (
            <p key={i} className="safe-text__p">
              {b.lines.map((l, j) => (
                <span key={j}>
                  <Inline text={l} />
                  {j < b.lines.length - 1 && <br />}
                </span>
              ))}
            </p>
          )
        }
        const List = b.kind
        return (
          <List key={i} className={`safe-text__list safe-text__list--${b.kind}`}>
            {b.items.map((it, j) => (
              <li key={j}>
                <Inline text={it} />
              </li>
            ))}
          </List>
        )
      })}
    </div>
  )
}
