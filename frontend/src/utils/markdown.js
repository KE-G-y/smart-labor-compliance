const escapeHtml = (value = '') => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;')

const restoreTokens = (html, tokens) => tokens.reduce(
  (result, replacement, index) => result.replaceAll(`@@MDTOKEN${index}@@`, replacement).replaceAll(`@@MD_TOKEN_${index}@@`, replacement),
  html
)

const renderInlineMarkdown = (value = '') => {
  const tokens = []
  const tokenFor = (replacement) => {
    // 占位符不能包含 `_`、`*`、`[` 等 Markdown 语法字符，否则会被后续规则误处理。
    const token = `@@MDTOKEN${tokens.length}@@`
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

const isTableSeparator = (line = '') => /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line)

const splitTableRow = (line = '') => {
  const normalized = line.trim().replace(/^\|/, '').replace(/\|$/, '')
  return normalized.split('|').map(cell => cell.trim())
}

const renderTable = (headers, rows) => {
  const thead = `<thead><tr>${headers.map(cell => `<th>${renderInlineMarkdown(cell)}</th>`).join('')}</tr></thead>`
  const tbody = `<tbody>${rows.map(row => `<tr>${row.map(cell => `<td>${renderInlineMarkdown(cell)}</td>`).join('')}</tr>`).join('')}</tbody>`
  return `<div class="markdown-table-wrap"><table>${thead}${tbody}</table></div>`
}

export const renderMarkdown = (value = '') => {
  const lines = String(value || '').replace(/\r\n?/g, '\n').split('\n')
  const blocks = []
  let paragraph = []
  let list = null

  for (let index = 0; index < lines.length; index += 1) {
    const rawLine = lines[index]
    const line = rawLine.trim()
    if (!line) {
      paragraph = closeParagraph(blocks, paragraph)
      list = closeList(blocks, list)
      continue
    }

    const fence = line.match(/^```([\w-]+)?\s*$/)
    if (fence) {
      paragraph = closeParagraph(blocks, paragraph)
      list = closeList(blocks, list)
      const codeLines = []
      index += 1
      while (index < lines.length && !lines[index].trim().match(/^```\s*$/)) {
        codeLines.push(lines[index])
        index += 1
      }
      const language = fence[1] ? ` class="language-${escapeHtml(fence[1])}"` : ''
      blocks.push(`<pre><code${language}>${escapeHtml(codeLines.join('\n'))}</code></pre>`)
      continue
    }

    if (line.includes('|') && isTableSeparator(lines[index + 1] || '')) {
      paragraph = closeParagraph(blocks, paragraph)
      list = closeList(blocks, list)
      const headers = splitTableRow(line)
      const rows = []
      index += 2
      while (index < lines.length && lines[index].trim() && lines[index].includes('|')) {
        rows.push(splitTableRow(lines[index]))
        index += 1
      }
      index -= 1
      blocks.push(renderTable(headers, rows))
      continue
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/)
    if (heading) {
      paragraph = closeParagraph(blocks, paragraph)
      list = closeList(blocks, list)
      const level = Math.min(heading[1].length + 1, 6)
      blocks.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`)
      continue
    }

    if (/^[-*_]{3,}$/.test(line)) {
      paragraph = closeParagraph(blocks, paragraph)
      list = closeList(blocks, list)
      blocks.push('<hr>')
      continue
    }

    const quote = line.match(/^>\s+(.+)$/)
    if (quote) {
      paragraph = closeParagraph(blocks, paragraph)
      list = closeList(blocks, list)
      blocks.push(`<blockquote>${renderInlineMarkdown(quote[1])}</blockquote>`)
      continue
    }

    const ordered = line.match(/^\d+[.)]\s+(.+)$/)
    if (ordered) {
      paragraph = closeParagraph(blocks, paragraph)
      if (!list || list.type !== 'ol') {
        list = closeList(blocks, list)
        list = { type: 'ol', items: [] }
      }
      list.items.push(ordered[1])
      continue
    }

    const unordered = line.match(/^[-*]\s+(.+)$/)
    if (unordered) {
      paragraph = closeParagraph(blocks, paragraph)
      if (!list || list.type !== 'ul') {
        list = closeList(blocks, list)
        list = { type: 'ul', items: [] }
      }
      list.items.push(unordered[1])
      continue
    }

    list = closeList(blocks, list)
    paragraph.push(line)
  }

  paragraph = closeParagraph(blocks, paragraph)
  list = closeList(blocks, list)

  return blocks.join('')
}
