<template>
  <AdminLayout :title="t('vectorVersionsTitle')" :subtitle="t('vectorVersionsSubtitle')">
    <div class="grid">
      <section class="panel">
        <div class="section-title">
          <h2>{{ t('vectorVersionList') }}</h2>
          <div class="toolbar">
            <AppSelect v-model="status" style="width: 160px" :options="statusOptions" @change="queryVersions" />
            <button class="btn primary" type="button" @click="queryVersions">{{ t('query') }}</button>
            <button class="btn" type="button" @click="fetchVersions">{{ t('refresh') }}</button>
          </div>
        </div>
        <AppTable
          :columns="versionColumns"
          :rows="versions"
          :empty-text="t('noVectorVersions')"
          :loading="loading"
          :loading-text="t('loading')"
          :sequence-start="sequenceStart"
          min-width="1480px"
        >
          <template #cell-version="{ row }">
            <div class="version-name-cell">
              <strong>{{ row.version }}</strong>
              <span v-if="row.description">{{ row.description }}</span>
            </div>
          </template>
          <template #cell-status="{ row }">
            <span :class="['tag', statusClass(row)]">
              {{ row.is_active ? t('vectorVersionActive') : vectorStatusLabel(row.status) }}
            </span>
          </template>
          <template #cell-indexed_count="{ row }">
            {{ row.indexed_count || 0 }} / {{ row.document_count || 0 }}
          </template>
          <template #cell-chunk_count="{ row }">
            {{ row.chunk_count || 0 }}
          </template>
          <template #cell-quality_overview="{ row }">
            <div class="quality-overview-cell">
              <span :class="['tag', qualityOverviewClass(row)]">{{ qualityOverviewLabel(row) }}</span>
              <button
                v-if="hasQualityReports(row)"
                class="btn ghost quality-toggle"
                type="button"
                @click.stop="toggleQuality(row)"
              >
                {{ selectedQualityVersion?.id === row.id ? t('hideQualityReport') : t('viewQualityReport') }}
              </button>
            </div>
          </template>
          <template #cell-build_finished_at="{ row }">
            {{ formatDateTime(row.build_finished_at || row.created_at) || '-' }}
          </template>
          <template #cell-action="{ row }">
            <div class="table-actions">
              <button
                :class="activateButtonClass(row)"
                type="button"
                :disabled="activateDisabled(row)"
                :title="activateButtonTitle(row)"
                @click.stop="activate(row)"
              >
                {{ activateButtonText(row) }}
              </button>
              <button
                class="btn danger"
                type="button"
                :disabled="row.is_active || row.status === 'archived' || actionId === row.id"
                @click.stop="archive(row)"
              >
                {{ t('archiveVectorVersion') }}
              </button>
            </div>
          </template>
        </AppTable>
        <AppPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @change="fetchVersions" />
        <section v-if="selectedQualityVersion" class="quality-detail">
          <div class="quality-detail-head">
            <div>
              <h3>{{ t('vectorQualityReportTitle') }}：{{ selectedQualityVersion.version }}</h3>
              <p>{{ selectedQualityVersion.collection_name }}</p>
            </div>
            <button class="btn ghost" type="button" @click="selectedQualityVersion = null">{{ t('hideQualityReport') }}</button>
          </div>
          <div class="quality-summary-grid">
            <div class="quality-summary-item">
              <span>{{ t('vectorQualityReportCount') }}</span>
              <strong>{{ selectedQualityOverview.total_reports || selectedQualityReports.length }}</strong>
            </div>
            <div class="quality-summary-item">
              <span>{{ t('vectorQualityAverageScore') }}</span>
              <strong>{{ selectedQualityOverview.average_score || 0 }}</strong>
            </div>
            <div class="quality-summary-item">
              <span>{{ t('vectorQualityNeedsReview') }}</span>
              <strong>{{ selectedQualityOverview.needs_review_count || 0 }}</strong>
            </div>
            <div class="quality-summary-item">
              <span>{{ t('vectorQualityPassCount') }}</span>
              <strong>{{ selectedQualityOverview.pass_count || 0 }}</strong>
            </div>
            <div class="quality-summary-item">
              <span>{{ t('vectorQualityWarningCount') }}</span>
              <strong>{{ selectedQualityOverview.warning_count || 0 }}</strong>
            </div>
            <div class="quality-summary-item">
              <span>{{ t('vectorQualityFailCount') }}</span>
              <strong>{{ selectedQualityOverview.fail_count || 0 }}</strong>
            </div>
          </div>
          <div v-if="selectedQualityReports.length" class="quality-report-list">
            <article v-for="report in previewQualityReports" :key="report.document_id || report.prepared_file" class="quality-report-item">
              <div class="quality-report-item-head">
                <strong>{{ report.title || report.document_id || '-' }}</strong>
                <span :class="['tag', qualityClass(report.status)]">
                  {{ qualityStatusText(report.status) }} · {{ report.score || 0 }} / {{ report.grade || '-' }}
                </span>
              </div>
              <div class="quality-report-meta">
                <span>{{ t('documentId') }}：{{ report.document_id || '-' }}</span>
                <span>{{ t('category') }}：{{ report.kb_category || '-' }}</span>
                <span>{{ t('docType') }}：{{ report.doc_type || '-' }}</span>
                <span>{{ t('preparedFile') }}：{{ report.prepared_file || '-' }}</span>
              </div>
              <div v-if="report.findings?.length" class="quality-report-block">
                <span>{{ t('vectorQualityFindings') }}</span>
                <p>{{ report.findings.join('；') }}</p>
              </div>
              <div v-if="report.recommendations?.length" class="quality-report-block">
                <span>{{ t('vectorQualityRecommendations') }}</span>
                <p>{{ report.recommendations.join('；') }}</p>
              </div>
            </article>
            <p v-if="selectedQualityReports.length > previewQualityReports.length" class="quality-more">
              {{ t('vectorQualityMoreHint') }} {{ previewQualityReports.length }} / {{ selectedQualityReports.length }}
            </p>
          </div>
          <div v-else class="empty">{{ t('vectorQualityNoReport') }}</div>
        </section>
      </section>
    </div>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { activateVectorVersion, archiveVectorVersion, getVectorVersions } from '@/api'
import { useI18n } from '@/i18n'
import AppPagination from '@/components/AppPagination.vue'
import AppSelect from '@/components/AppSelect.vue'
import AppTable from '@/components/AppTable.vue'
import AdminLayout from './AdminLayout.vue'

const { t, formatDateTime } = useI18n()

const versions = ref([])
const loading = ref(false)
const actionId = ref(null)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const status = ref('')
const selectedQualityVersion = ref(null)

const sequenceStart = computed(() => (page.value - 1) * pageSize.value + 1)
const selectedQualityReports = computed(() => selectedQualityVersion.value?.quality_reports || [])
const selectedQualityOverview = computed(() => selectedQualityVersion.value?.quality_overview || {})
const previewQualityReports = computed(() => selectedQualityReports.value.slice(0, 12))
const statusOptions = computed(() => [
  { value: '', label: t('allStatus') },
  { value: 'active', label: t('vectorVersionActive') },
  { value: 'ready', label: t('vectorVersionReady') },
  { value: 'building', label: t('vectorVersionBuilding') },
  { value: 'failed', label: t('vectorVersionFailed') },
  { value: 'archived', label: t('vectorVersionArchived') }
])
const versionColumns = computed(() => [
  { key: 'sequence', label: t('sequence'), width: '56px' },
  { key: 'tenant_name', label: t('tenant'), width: '128px' },
  { key: 'version', label: t('vectorVersion'), width: '150px' },
  { key: 'collection_name', label: t('milvusCollection'), width: '210px' },
  { key: 'status', label: t('status'), width: '96px' },
  { key: 'indexed_count', label: t('vectorIndexedDocs'), width: '104px' },
  { key: 'chunk_count', label: t('vectorChunks'), width: '92px' },
  { key: 'quality_overview', label: t('vectorIngestQuality'), width: '132px' },
  { key: 'embedding_model', label: t('langchainEmbeddingModel'), width: '150px' },
  { key: 'build_finished_at', label: t('buildFinishedAt'), width: '154px' },
  { key: 'action', label: t('action'), width: '196px', sticky: 'right' }
])

const vectorStatusLabel = (value) => {
  const labels = {
    building: t('vectorVersionBuilding'),
    ready: t('vectorVersionReady'),
    active: t('vectorVersionActive'),
    failed: t('vectorVersionFailed'),
    archived: t('vectorVersionArchived')
  }
  return labels[value] || value || '-'
}

const statusClass = (row) => {
  if (row.is_active || row.status === 'active') return 'success'
  if (row.status === 'ready') return 'success'
  if (row.status === 'building') return 'warning'
  if (row.status === 'failed') return 'danger'
  return ''
}

const hasQualityReports = (row) => Array.isArray(row.quality_reports) && row.quality_reports.length > 0

const qualityStatusFromOverview = (overview = {}) => {
  if (!overview.total_reports) return ''
  if ((overview.fail_count || 0) > 0) return 'fail'
  if ((overview.warning_count || 0) > 0) return 'warning'
  return 'pass'
}

const qualityClass = (status) => status === 'pass' ? 'success' : status === 'warning' ? 'warning' : status === 'fail' ? 'danger' : ''

const qualityOverviewClass = (row) => qualityClass(qualityStatusFromOverview(row.quality_overview || {}))

const qualityStatusText = (status) => {
  if (status === 'pass') return t('qualityPass')
  if (status === 'warning') return t('qualityWarning')
  if (status === 'fail') return t('qualityFail')
  return t('vectorQualityNoReport')
}

const qualityOverviewLabel = (row) => {
  const overview = row.quality_overview || {}
  if (!overview.total_reports) return t('vectorQualityNoReport')
  return `${overview.average_score || 0} / ${overview.total_reports}`
}

const toggleQuality = (row) => {
  selectedQualityVersion.value = selectedQualityVersion.value?.id === row.id ? null : row
}

const canActivate = (row) => row.status === 'ready' && !row.is_active

const activateDisabled = (row) => !canActivate(row) || actionId.value === row.id

const activateButtonClass = (row) => [
  'btn',
  canActivate(row) ? 'primary' : 'muted'
]

const activateButtonText = (row) => {
  if (actionId.value === row.id) return t('activatingVectorVersion')
  if (row.is_active) return t('vectorVersionActive')
  if (row.status === 'building') return t('vectorVersionBuilding')
  if (row.status === 'failed') return t('vectorVersionCannotActivate')
  if (row.status === 'archived') return t('vectorVersionArchived')
  return t('activateVectorVersion')
}

const activateButtonTitle = (row) => {
  if (canActivate(row)) return t('activateVectorVersion')
  if (row.is_active) return t('vectorVersionAlreadyActiveHint')
  if (row.status === 'building') return t('vectorVersionBuildingHint')
  if (row.status === 'failed') return t('vectorVersionFailedHint')
  if (row.status === 'archived') return t('vectorVersionArchivedHint')
  return t('vectorVersionCannotActivateHint')
}

const fetchVersions = async () => {
  // 这里展示的是 MySQL 里的版本元数据；真正的向量内容在对应 Milvus collection。
  loading.value = true
  try {
    const res = await getVectorVersions({
      page: page.value,
      page_size: pageSize.value,
      status: status.value || undefined
    })
    versions.value = res.data?.list || []
    total.value = res.data?.total || 0
    if (selectedQualityVersion.value) {
      selectedQualityVersion.value = versions.value.find((item) => item.id === selectedQualityVersion.value.id) || null
    }
  } finally {
    loading.value = false
  }
}

const queryVersions = () => {
  page.value = 1
  fetchVersions()
}

const activate = async (row) => {
  if (!canActivate(row)) return
  if (!confirm(t('activateVectorVersionConfirm'))) return
  actionId.value = row.id
  try {
    // 激活版本会让后端把当前租户的 milvus_collection 切换到该 collection。
    await activateVectorVersion(row.id, { tenant_id: row.tenant_id })
    await fetchVersions()
    alert(t('activateVectorVersionSuccess'))
  } catch (e) {
    const errorMessage = e.response?.data?.message || e.response?.data?.detail || e.message || t('activateVectorVersionFailed')
    alert(errorMessage)
  } finally {
    actionId.value = null
  }
}

const archive = async (row) => {
  if (!confirm(t('archiveVectorVersionConfirm'))) return
  actionId.value = row.id
  try {
    // 归档只是隐藏/停用版本记录，不删除 Milvus 数据，便于后续人工清理或回滚。
    await archiveVectorVersion(row.id, { tenant_id: row.tenant_id })
    await fetchVersions()
  } finally {
    actionId.value = null
  }
}

onMounted(fetchVersions)
</script>

<style scoped>
.version-name-cell {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.version-name-cell strong,
.version-name-cell span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.version-name-cell span {
  color: var(--text-muted);
  font-size: 12px;
}

.quality-overview-cell {
  min-width: 0;
  display: grid;
  gap: 6px;
  align-items: start;
}

.quality-overview-cell .tag {
  justify-self: start;
}

.quality-toggle {
  min-height: 28px;
  padding: 3px 8px;
  justify-self: start;
  font-size: 12px;
}

.quality-detail {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}

.quality-detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.quality-detail-head h3 {
  margin: 0 0 4px;
  font-size: 16px;
}

.quality-detail-head p {
  margin: 0;
  color: var(--text-muted);
  font-size: 12px;
  word-break: break-all;
}

.quality-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.quality-summary-item {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
}

.quality-summary-item span {
  display: block;
  color: var(--text-muted);
  font-size: 12px;
}

.quality-summary-item strong {
  display: block;
  margin-top: 4px;
  font-size: 18px;
}

.quality-report-list {
  display: grid;
  gap: 10px;
}

.quality-report-item {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
}

.quality-report-item-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.quality-report-item-head strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quality-report-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  margin-top: 8px;
  color: var(--text-muted);
  font-size: 12px;
}

.quality-report-block {
  margin-top: 8px;
  display: grid;
  gap: 3px;
}

.quality-report-block span,
.quality-more {
  color: var(--text-muted);
  font-size: 12px;
}

.quality-report-block p,
.quality-more {
  margin: 0;
}

.table-actions .btn.muted {
  color: var(--text-muted);
  background: rgba(0, 0, 0, 0.03);
  border-color: var(--line);
}

.table-actions .btn.muted:hover {
  color: var(--text-muted);
  border-color: var(--line);
}
</style>
