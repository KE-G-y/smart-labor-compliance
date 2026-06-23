const CHUNK_SUFFIX_RE = /\s+#chunk-(\d+)\s*$/i

export const cleanSourceTitle = (source = {}) => {
  const rawTitle = String(source.title || source.url || '').trim()
  return rawTitle.replace(CHUNK_SUFFIX_RE, '').trim() || '-'
}

export const sourceChunkIndex = (source = {}) => {
  if (source.chunk_index !== null && source.chunk_index !== undefined && source.chunk_index !== '') {
    const numeric = Number(source.chunk_index)
    if (Number.isInteger(numeric) && numeric >= 0) return numeric
  }
  const match = String(source.title || '').match(CHUNK_SUFFIX_RE)
  return match ? Number(match[1]) : null
}

const sourceGroupKey = (source = {}) => {
  const documentKey = source.document_id || source.local_file || cleanSourceTitle(source)
  return [documentKey, source.url || '', source.source_type || ''].join('|')
}

export const groupSources = (sources = []) => {
  const groups = new Map()
  for (const source of Array.isArray(sources) ? sources : []) {
    const title = cleanSourceTitle(source)
    const chunk = {
      ...source,
      title,
      chunk_index: sourceChunkIndex(source)
    }
    const key = sourceGroupKey(chunk)
    if (!groups.has(key)) {
      groups.set(key, {
        ...chunk,
        title,
        chunks: []
      })
    }
    groups.get(key).chunks.push(chunk)
  }
  return Array.from(groups.values())
}
