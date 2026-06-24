export const normalizeRiskLevel = (value) => {
  const normalized = String(value || '').trim().toLowerCase().replace(/^[*：:，,。.;；\s]+|[*：:，,。.;；\s]+$/g, '')
  const mapping = {
    高: 'high',
    高风险: 'high',
    high: 'high',
    中: 'medium',
    中风险: 'medium',
    中等: 'medium',
    中等风险: 'medium',
    medium: 'medium',
    低: 'low',
    低风险: 'low',
    low: 'low'
  }
  return mapping[normalized] || ''
}

export const riskFromAnswer = (value) => {
  const text = String(value || '')
  const patterns = [
    /风险等级\s*[:：]\s*(?:\*\*)?\s*(高风险|中风险|低风险|高|中|低|high|medium|low)/i,
    /初步风险等级\s*为\s*[:：]?\s*(?:\*\*)?\s*(高风险|中风险|低风险|高|中|低|high|medium|low)/i,
    /(?:属|属于|构成|认定为|判断为|应视为|可视为)\s*(高风险|中风险|低风险|高|中|低|high|medium|low)\s*(?:违规|违法|事项|行为|问题|风险)?/i
  ]
  for (const pattern of patterns) {
    const match = text.match(pattern)
    const risk = normalizeRiskLevel(match?.[1])
    if (risk) return risk
  }
  const fallbackLabels = [
    ['高风险', 'high'],
    ['中风险', 'medium'],
    ['低风险', 'low'],
    ['high risk', 'high'],
    ['medium risk', 'medium'],
    ['low risk', 'low']
  ]
  const lowered = text.toLowerCase()
  const hits = fallbackLabels
    .map(([label, risk]) => ({ index: lowered.indexOf(label), risk }))
    .filter(item => item.index >= 0)
    .sort((a, b) => a.index - b.index)
  if (hits.length) return hits[0].risk
  return ''
}

export const highRiskFromQuestion = (value) => {
  const text = String(value || '').toLowerCase()
  const highRiskKeywords = [
    '自杀',
    '自残',
    '轻生',
    '跳楼',
    '寻死',
    '结束生命',
    '不想活',
    '黑客',
    '黑进',
    '入侵',
    '破解密码',
    '攻击服务器',
    '攻击网站',
    '洗钱',
    '诈骗',
    '偷税',
    '逃税',
    '毒品',
    '枪支',
    '爆炸'
  ]
  return highRiskKeywords.some(keyword => text.includes(keyword)) ? 'high' : ''
}

export const displayedRiskLevel = (item) => {
  return riskFromAnswer(item?.answer) || highRiskFromQuestion(item?.question) || normalizeRiskLevel(item?.risk_level ?? item?.riskLevel) || 'medium'
}
