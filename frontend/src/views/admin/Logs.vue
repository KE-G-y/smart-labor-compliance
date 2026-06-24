<template>
  <AdminLayout :title="t('logsTitle')" :subtitle="t('logsSubtitle')" content-mode="fixed">
    <section class="panel">
      <div class="toolbar" style="margin-bottom: 14px">
        <input v-model="keyword" class="input" style="max-width: 320px" :placeholder="t('searchQuestion')" />
        <AppSelect v-model="status" style="width: 140px" :options="statusOptions" />
        <button class="btn primary" @click="queryLogs">{{ t('query') }}</button>
      </div>
      <AppTable :columns="logColumns" :rows="logs" :empty-text="t('noLogs')" :loading="loading" :loading-text="t('loading')" :sequence-start="sequenceStart">
        <template #cell-risk_level="{ row }">
          <span :class="['tag', riskClass(displayedRiskLevel(row))]">{{ riskLabel(displayedRiskLevel(row)) }}</span>
        </template>
        <template #cell-response_time="{ row }">
          <EllipsisText :value="`${row.response_time}ms`" />
        </template>
        <template #cell-created_at="{ row }">
          <EllipsisText :value="formatTime(row.created_at)" />
        </template>
        <template #cell-action="{ row }">
          <div class="table-actions">
            <button class="btn" @click="openLogDetail(row.id)">{{ t('viewDetail') }}</button>
          </div>
        </template>
      </AppTable>
      <AppPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @change="fetchLogs" />
    </section>

    <Teleport to="body">
      <div v-if="detailModalOpen" class="modal-mask">
        <div class="modal log-detail-modal">
          <div class="section-title modal-header">
            <h2>{{ t('logDetail') }}</h2>
            <button class="btn ghost" type="button" @click="closeLogDetail">×</button>
          </div>
          <template v-if="selectedLog">
          <div class="modal-body log-detail">
            <div class="detail-grid">
              <div>
                <span>{{ t('tenant') }}</span>
                <strong>{{ selectedLog.tenant?.name || selectedLog.tenant_name || '-' }}</strong>
              </div>
              <div>
                <span>{{ t('userId') }}</span>
                <strong>{{ selectedLog.user_id || '-' }}</strong>
              </div>
              <div>
                <span>{{ t('risk') }}</span>
                <strong>{{ riskLabel(displayedRiskLevel(selectedLog)) || '-' }}</strong>
              </div>
              <div>
                <span>{{ t('engine') }}</span>
                <strong>{{ selectedLog.provider || '-' }}</strong>
              </div>
              <div>
                <span>{{ t('response') }}</span>
                <strong>{{ selectedLog.response_time ?? '-' }}ms</strong>
              </div>
              <div>
                <span>{{ t('time') }}</span>
                <strong>{{ formatTime(selectedLog.created_at) || '-' }}</strong>
              </div>
            </div>
            <section v-if="traceMetricEntries.length">
              <h3>{{ t('traceMetrics') }}</h3>
              <div class="trace-metrics">
                <div v-for="metric in traceMetricEntries" :key="metric.key">
                  <span>{{ metric.label }}</span>
                  <strong>{{ metric.value }}</strong>
                </div>
              </div>
            </section>
            <section>
              <h3>{{ t('question') }}</h3>
              <p class="preline">{{ selectedLog.question }}</p>
            </section>
            <section>
              <h3>{{ t('answer') }}</h3>
              <div class="markdown-box markdown-content" v-html="renderMarkdown(selectedLog.answer || '-')"></div>
            </section>
            <section v-if="sourceList.length">
              <h3>{{ t('sourcesInfo') }}</h3>
              <div class="log-sources">
                <button
                  v-for="source in sourceList"
                  :key="sourceKey(source)"
                  class="log-source-card"
                  type="button"
                  @click="openSourceDetail(source)"
                >
                  <strong>{{ source.title || '-' }}</strong>
                  <span>{{ sourceListSummary(source) }}</span>
                </button>
              </div>
            </section>
          </div>
          <div class="modal-actions modal-footer">
            <button class="btn primary" type="button" @click="closeLogDetail">{{ t('close') }}</button>
          </div>
          </template>
        </div>
      </div>
    </Teleport>
    <SourceDetailModal :open="sourceDetailOpen" :source="selectedSource" @close="closeSourceDetail" />
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getLogDetail, getLogs } from '@/api'
import { useI18n } from '@/i18n'
import { renderMarkdown } from '@/utils/markdown'
import { displayedRiskLevel } from '@/utils/risk'
import { groupSources } from '@/utils/sources'
import AppPagination from '@/components/AppPagination.vue'
import AppSelect from '@/components/AppSelect.vue'
import AppTable from '@/components/AppTable.vue'
import EllipsisText from '@/components/EllipsisText.vue'
import SourceDetailModal from '@/components/SourceDetailModal.vue'
import AdminLayout from './AdminLayout.vue'

const { t, formatDateTime, riskLabel } = useI18n()
const logs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const status = ref('')
const selectedLog = ref(null)
const selectedSource = ref(null)
const detailModalOpen = ref(false)
const sourceDetailOpen = ref(false)
const loading = ref(false)
const sequenceStart = computed(() => (page.value - 1) * pageSize.value + 1)
const logColumns = computed(() => [
  { key: 'sequence', label: t('sequence'), width: '64px', sticky: true },
  { key: 'question', label: t('question'), width: '23%', sticky: true },
  { key: 'tenant_name', label: t('tenant'), width: '13%' },
  { key: 'answer', label: t('answerSummary'), width: '28%' },
  { key: 'risk_level', label: t('risk'), width: '96px' },
  { key: 'provider', label: t('engine'), width: '88px' },
  { key: 'response_time', label: t('response'), width: '88px' },
  { key: 'created_at', label: t('time'), width: '156px' },
  { key: 'action', label: t('action'), width: '112px' }
])
const sourceList = computed(() => groupSources(selectedLog.value?.sources || []))
const traceMetrics = computed(() => selectedLog.value?.evaluation?.metrics?.trace || {})
const traceMetricOrder = [
  'query_strategy',
  'precheck_ms',
  'knowledge_package_ms',
  'vector_search_ms',
  'vector_search_count',
  'vector_search_cache_hits',
  'vector_search_reused',
  'vector_source_count',
  'langchain_source_context_ms',
  'source_context_chars',
  'prompt_context_chars',
  'langchain_model_ms',
  'langchain_total_ms',
  'dify_total_ms',
  'quality_report_ms'
]
const traceMetricLabels = computed(() => ({
  query_strategy: t('traceMetricQueryStrategy'),
  precheck_ms: t('traceMetricPrecheck'),
  knowledge_package_ms: t('traceMetricKnowledgePackage'),
  vector_search_ms: t('traceMetricVectorSearch'),
  vector_search_count: t('traceMetricVectorSearchCount'),
  vector_search_cache_hits: t('traceMetricVectorCacheHits'),
  vector_search_reused: t('traceMetricVectorReused'),
  vector_source_count: t('traceMetricVectorSourceCount'),
  langchain_source_context_ms: t('traceMetricSourceContext'),
  source_context_chars: t('traceMetricSourceContextChars'),
  prompt_context_chars: t('traceMetricPromptChars'),
  langchain_model_ms: t('traceMetricLangchainModel'),
  langchain_total_ms: t('traceMetricLangchainTotal'),
  dify_total_ms: t('traceMetricDifyTotal'),
  quality_report_ms: t('traceMetricQualityReport')
}))
const traceMetricEntries = computed(() => traceMetricOrder
  .filter((key) => traceMetrics.value[key] !== undefined && traceMetrics.value[key] !== null)
  .map((key) => ({
    key,
    label: traceMetricLabels.value[key] || key,
    value: formatTraceMetricValue(key, traceMetrics.value[key])
  })))
const statusOptions = computed(() => [
  { value: '', label: t('allStatus') },
  { value: 'success', label: t('statusSuccess') },
  { value: 'failed', label: t('statusFailed') }
])

const fetchLogs = async () => {
  loading.value = true
  try {
    const res = await getLogs({ keyword: keyword.value, status: status.value, page: page.value, page_size: pageSize.value })
    logs.value = res.data?.list || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}
const queryLogs = () => {
  page.value = 1
  fetchLogs()
}
const riskClass = (risk) => risk === 'high' ? 'danger' : risk === 'medium' ? 'warning' : 'success'
const formatTime = (time) => formatDateTime(time)
const formatTraceMetricValue = (key, value) => {
  if (typeof value === 'boolean') return value ? t('enable') : t('statusDisabled')
  if (key.endsWith('_ms') && value !== '') return `${value}ms`
  return String(value)
}
const sourceKey = (source) => [source.document_id || source.local_file || source.title, source.url || '', source.source_type || ''].join('|')
const sourceListSummary = (source) => {
  const count = Array.isArray(source.chunks) ? source.chunks.length : 0
  return count > 1 ? t('sourceChunkCount').replace('{count}', count) : t('sourceListHint')
}
const openLogDetail = async (id) => {
  const res = await getLogDetail(id)
  selectedLog.value = res.data
  detailModalOpen.value = true
}
const closeLogDetail = () => {
  detailModalOpen.value = false
  selectedLog.value = null
  closeSourceDetail()
}
const openSourceDetail = (source) => {
  selectedSource.value = source
  sourceDetailOpen.value = true
}
const closeSourceDetail = () => {
  sourceDetailOpen.value = false
  selectedSource.value = null
}

onMounted(fetchLogs)
</script>

<style scoped>
.log-detail-modal {
  width: min(920px, calc(100vw - 32px));
}

.log-detail {
  display: grid;
  gap: 16px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.trace-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.detail-grid > div,
.trace-metrics > div {
  display: grid;
  gap: 4px;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-soft);
}

.detail-grid span,
.trace-metrics span,
.log-sources span {
  color: var(--muted);
}

.log-detail h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.log-detail p,
.markdown-box {
  margin: 0;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-soft);
}

.markdown-box {
  display: grid;
  gap: 8px;
  overflow-wrap: anywhere;
}

.log-sources {
  display: grid;
  gap: 8px;
}

.log-source-card {
  width: 100%;
  display: grid;
  gap: 4px;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  text-decoration: none;
  background: var(--surface-soft);
  color: var(--text);
  cursor: pointer;
  font: inherit;
  text-align: left;
  white-space: normal;
}

.log-source-card:hover {
  border-color: var(--primary);
}

@media (max-width: 760px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
