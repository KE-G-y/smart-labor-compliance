const escapeHtml = (value = '') => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;')

const restoreTokens = (html, tokens) => tokens.reduce(
  (result, replacement, index) => result.replaceAll(`@@MD_TOKEN_${index}@@`, replacement),
  html
)

const renderInlineMarkdown = (value = '') => {
  const tokens = []
  const tokenFor = (replacement) => {
    const token = `@@MD_TOKEN_${tokens.length}@@`
    tokens.push(replacement)
    return token
  }

  let html = String(value).replace(/`([^`\n]+)`/g, (_, code) => tokenFor(`<code>${escapeHtml(code)}</code>`))
  html = escapeHtml(html)
  html = html
    .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_\n]+)__/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>')
    .replace(/(^|[^_])_([^_\n]+)_(?!_)/g, '$1<em>$2</em>')
    .replace(
      /\[([^\]\n]+)\]\((https?:\/\/[^)\s]+|mailto:[^)\s]+|tel:[^)\s]+)\)/gi,
      '<a href="$2" target="_blank" rel="noreferrer">$1</a>'
    )

  return restoreTokens(html, tokens)
}

const closeParagraph = (blocks, paragraph) => {
  if (!paragraph.length) return []
  blocks.push(`<p>${paragraph.map(renderInlineMarkdown).join('<br>')}</p>`)
  return []
}

const closeList = (blocks, list) => {
  if (!list) return null
  blocks.push(`<${list.type}>${list.items.map(item => `<li>${renderInlineMarkdown(item)}</li>`).join('')}</${list.type}>`)
  return null
}

export const renderMarkdown = (value = '') => {
  const lines = String(value || '').replace(/\r\n?/g, '\n').split('\n')
  const blocks = []
  let paragraph = []
  let list = null

  lines.forEach((rawLine) => {
    const line = rawLine.trim()
    if (!line) {
      paragraph = closeParagraph(blocks, paragraph)
      list = closeList(blocks, list)
      return
    }

    const heading = line.match(/^(#{1,3})\s+(.+)$/)
    if (heading) {
      paragraph = closeParagraph(blocks, paragraph)
      list = closeList(blocks, list)
      const level = heading[1].length + 2
      blocks.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`)
      return
    }

    const ordered = line.match(/^\d+[.)]\s+(.+)$/)
    if (ordered) {
      paragraph = closeParagraph(blocks, paragraph)
      if (!list || list.type !== 'ol') {
        list = closeList(blocks, list)
        list = { type: 'ol', items: [] }
      }
      list.items.push(ordered[1])
      return
    }

    const unordered = line.match(/^[-*]\s+(.+)$/)
    if (unordered) {
      paragraph = closeParagraph(blocks, paragraph)
      if (!list || list.type !== 'ul') {
        list = closeList(blocks, list)
        list = { type: 'ul', items: [] }
      }
      list.items.push(unordered[1])
      return
    }

    list = closeList(blocks, list)
    paragraph.push(line)
  })

  paragraph = closeParagraph(blocks, paragraph)
  list = closeList(blocks, list)

  return blocks.join('')
}
