<template>
  <AdminLayout :title="t('sourcesTitle')" :subtitle="t('sourcesSubtitle')">
    <div class="grid">
      <section class="panel">
        <div class="section-title">
          <h2>{{ t('sourceList') }}</h2>
          <div class="toolbar">
            <button v-if="canExport" class="btn" @click="exportCurrentSources">{{ t('exportData') }}</button>
            <button v-if="canExport" class="btn" :disabled="!selectedIds.length" @click="exportSelectedSources">{{ t('exportSelected') }}</button>
            <label v-if="canImport" class="btn import-button">
              {{ t('importData') }}
              <input type="file" accept=".csv,text/csv" @change="handleImport" />
            </label>
            <button class="btn primary" @click="openCreateModal">{{ t('addSource') }}</button>
            <button class="btn" @click="fetchSources">{{ t('refresh') }}</button>
          </div>
        </div>
        <div v-if="canBatch" class="batch-toolbar">
          <span class="muted">{{ selectedCountText }}</span>
          <button class="btn primary" :disabled="!selectedIds.length" @click="batchMarkReviewed">{{ t('batchMarkReviewed') }}</button>
          <button class="btn" :disabled="!selectedIds.length" @click="batchMarkPending">{{ t('batchMarkPending') }}</button>
          <button class="btn danger" :disabled="!selectedIds.length" @click="batchDeleteSelected">{{ t('batchDelete') }}</button>
        </div>
        <AppTable :columns="sourceColumns" :rows="sources" :empty-text="t('noSources')" :loading="loading" :loading-text="t('loading')" :sequence-start="sequenceStart">
          <template #head-select>
            <input type="checkbox" :aria-label="t('selectAll')" :checked="allSelected" @change="toggleSelectAll" />
          </template>
          <template #cell-select="{ row }">
            <input type="checkbox" :aria-label="t('selectRow')" :checked="selectedIds.includes(row.id)" @change="toggleSelected(row.id)" />
          </template>
          <template #cell-title="{ row }">
            <a v-if="row.url" :href="row.url" target="_blank" rel="noreferrer">
              <EllipsisText :value="row.title" as-link />
            </a>
            <div v-else class="source-title-cell">
              <EllipsisText :value="row.title" />
              <span v-if="row.local_file" class="tag">{{ t('sourceByFile') }}</span>
            </div>
          </template>
          <template #cell-review_status="{ row }">
            <span :class="['tag', isReviewed(row.review_status) ? 'success' : 'warning']">{{ reviewLabel(row.review_status) }}</span>
          </template>
          <template #cell-action="{ row }">
            <div class="table-actions">
              <button
                :class="['btn', isReviewed(row.review_status) ? '' : 'primary']"
                @click="toggleReview(row)"
              >
                {{ isReviewed(row.review_status) ? t('markPendingReview') : t('markReviewed') }}
              </button>
              <button v-if="isReviewed(row.review_status)" class="btn" @click="openSourceDetail(row)">{{ t('detail') }}</button>
              <button v-else class="btn" @click="editSource(row)">{{ t('edit') }}</button>
              <button class="btn danger" @click="removeSource(row.id)">{{ t('delete') }}</button>
            </div>
          </template>
        </AppTable>
        <AppPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @change="fetchSources" />
      </section>
    </div>

    <Teleport to="body">
      <div v-if="sourceModalOpen" class="modal-mask">
        <div class="modal source-modal">
          <form class="modal-form" @submit.prevent="saveSource">
            <div class="section-title modal-header">
              <h2>{{ editingId ? t('editSource') : t('addSource') }}</h2>
              <button class="btn ghost" type="button" @click="closeSourceModal">×</button>
            </div>
            <div class="modal-body form-grid">
              <div class="form-group">
                <label>{{ t('title') }} <span class="required-mark">*</span></label>
                <input v-model.trim="form.title" class="input" required />
              </div>
              <div class="form-group">
                <label>{{ t('docType') }}</label>
                <AppSelect v-model="form.doc_type" :options="docTypeOptions" :placeholder="t('docTypePlaceholder')" />
              </div>
              <div class="form-group"><label>{{ t('issuer') }}</label><input v-model="form.issuer" class="input" /></div>
              <div class="form-group">
                <label>{{ t('region') }}</label>
                <AppSelect v-model="form.region" :options="regionOptions" :placeholder="t('regionPlaceholder')" />
              </div>
              <div class="form-group full">
                <label>{{ t('sourcePath') }}</label>
                <div class="source-path-tabs">
                  <button
                    type="button"
                    :class="['chip', sourceMode === 'link' ? 'active' : '']"
                    @click="switchSourceMode('link')"
                  >
                    {{ t('sourceByLink') }}
                  </button>
                  <button
                    type="button"
                    :class="['chip', sourceMode === 'file' ? 'active' : '']"
                    @click="switchSourceMode('file')"
                  >
                    {{ t('sourceByFile') }}
                  </button>
                </div>
              </div>
              <div v-if="sourceMode === 'link'" class="form-group full">
                <label>{{ t('link') }}</label>
                <input v-model.trim="form.url" class="input" />
                <div class="form-hint">{{ t('sourcePathRequired') }}</div>
              </div>
              <div v-else class="form-group full">
                <label>{{ t('uploadFile') }}</label>
                <div class="source-upload-box">
                  <div class="source-upload-main">
                    <span class="source-upload-icon">↑</span>
                    <div class="source-upload-copy">
                      <strong>{{ selectedFile?.name || uploadedFileName || t('noFileSelected') }}</strong>
                      <span>{{ uploadStatusText }}</span>
                    </div>
                  </div>
                  <div class="source-upload-actions">
                    <label class="btn source-file-picker">
                      {{ t('selectFile') }}
                      <input type="file" @change="handleFileChange" />
                    </label>
                    <button class="btn primary" type="button" :disabled="!selectedFile || uploading" @click="uploadSelectedFile">
                      {{ uploading ? t('loading') : t('uploadFile') }}
                    </button>
                  </div>
                </div>
                <div class="form-hint">{{ t('sourcePathRequired') }}</div>
              </div>
              <div v-if="formError" class="form-group full form-error">{{ formError }}</div>
              <div class="form-group full"><label>{{ t('description') }}</label><textarea v-model="form.description" class="textarea source-description" /></div>
            </div>
            <div class="modal-actions modal-footer">
              <button class="btn" type="button" @click="closeSourceModal">{{ t('cancelEdit') }}</button>
              <button class="btn primary" type="submit">{{ editingId ? t('saveChanges') : t('addSource') }}</button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="detailModalOpen" class="modal-mask">
        <div class="modal source-detail-modal">
          <div class="section-title modal-header">
            <h2>{{ t('sourceDetail') }}</h2>
            <button class="btn ghost" type="button" @click="closeSourceDetail">×</button>
          </div>
          <template v-if="selectedSource">
          <div class="modal-body source-detail">
            <div class="detail-grid">
              <div>
                <span>{{ t('reviewStatus') }}</span>
                <strong>{{ reviewLabel(selectedSource.review_status) }}</strong>
              </div>
              <div>
                <span>{{ t('reviewedAt') }}</span>
                <strong>{{ formatTime(selectedSource.reviewed_at) || '-' }}</strong>
              </div>
              <div>
                <span>{{ t('reviewedBy') }}</span>
                <strong>{{ selectedSource.reviewed_by || '-' }}</strong>
              </div>
              <div>
                <span>{{ t('docType') }}</span>
                <strong>{{ selectedSource.doc_type || '-' }}</strong>
              </div>
              <div>
                <span>{{ t('issuer') }}</span>
                <strong>{{ selectedSource.issuer || '-' }}</strong>
              </div>
              <div>
                <span>{{ t('region') }}</span>
                <strong>{{ selectedSource.region || '-' }}</strong>
              </div>
            </div>
            <section>
              <h3>{{ t('title') }}</h3>
              <p>{{ selectedSource.title || '-' }}</p>
            </section>
            <section>
              <h3>{{ t('sourcePath') }}</h3>
              <a
                v-if="selectedSource.url"
                :href="selectedSource.url"
                target="_blank"
                rel="noreferrer"
                class="detail-link"
              >
                {{ selectedSource.url }}
              </a>
              <p v-else>{{ selectedSource.local_file || '-' }}</p>
            </section>
            <section>
              <h3>{{ t('description') }}</h3>
              <p class="preline">{{ selectedSource.description || '-' }}</p>
            </section>
          </div>
          <div class="modal-actions modal-footer">
            <button class="btn primary" type="button" @click="closeSourceDetail">{{ t('close') }}</button>
          </div>
          </template>
        </div>
      </div>
    </Teleport>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { addSource, batchSources, deleteSource, exportSources, getSources, importSources, reviewSource, updateSource, uploadSourceFile } from '@/api'
import { useI18n } from '@/i18n'
import AppPagination from '@/components/AppPagination.vue'
import AppSelect from '@/components/AppSelect.vue'
import AppTable from '@/components/AppTable.vue'
import EllipsisText from '@/components/EllipsisText.vue'
import AdminLayout from './AdminLayout.vue'

const { t, formatDateTime } = useI18n()
const sources = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const editingId = ref(null)
const sourceModalOpen = ref(false)
const detailModalOpen = ref(false)
const selectedSource = ref(null)
const selectedIds = ref([])
const permissions = JSON.parse(localStorage.getItem('admin_permissions') || '[]')
const sourceMode = ref('link')
const selectedFile = ref(null)
const uploadedFileName = ref('')
const uploading = ref(false)
const loading = ref(false)
const formError = ref('')
const initialForm = () => ({ title: '', url: '', local_file: '', doc_type: '', issuer: '', region: t('defaultRegion'), description: '', validity_status: '有效', review_status: '待人工复核' })
const form = ref(initialForm())
const withCurrentOption = (options, value) => {
  const current = (value || '').trim()
  if (!current || options.includes(current)) return options
  return [...options, current]
}
const docTypeOptions = computed(() => withCurrentOption([
  '国家法律法规',
  '行政法规',
  '部门规章',
  '地方性法规',
  '地方政策',
  '地方政策/办事信息',
  '办事指南',
  '办事说明',
  '经办规程',
  '政策解读',
  '其他'
], form.value.doc_type))
const regionOptions = computed(() => withCurrentOption([
  '全国',
  t('defaultRegion'),
  '西安',
  '陕西/西安',
  '全国/陕西',
  '其他'
], form.value.region))
const sequenceStart = computed(() => (page.value - 1) * pageSize.value + 1)
const hasPermission = (permission, fallback) => permissions.includes(permission) || permissions.includes(fallback)
const canImport = computed(() => hasPermission('sources_import', 'sources'))
const canExport = computed(() => hasPermission('sources_export', 'sources'))
const canBatch = computed(() => hasPermission('sources_batch', 'sources'))
const allSelected = computed(() => sources.value.length > 0 && sources.value.every(item => selectedIds.value.includes(item.id)))
const selectedCountText = computed(() => t('selectedCount').replace('{count}', selectedIds.value.length))
const sourceColumns = computed(() => [
  { key: 'select', label: '', width: '44px', align: 'center' },
  { key: 'sequence', label: t('sequence'), width: '64px' },
  { key: 'title', label: t('title'), width: '36%' },
  { key: 'doc_type', label: t('docType'), width: '120px' },
  { key: 'issuer', label: t('issuer'), width: '24%' },
  { key: 'region', label: t('region'), width: '88px' },
  { key: 'review_status', label: t('review'), width: '96px' },
  { key: 'action', label: t('action'), width: '246px' }
])
const hasLink = computed(() => Boolean((form.value.url || '').trim()))
const hasUploadedFile = computed(() => Boolean((form.value.local_file || '').trim()))
const uploadStatusText = computed(() => {
  if (uploading.value) return t('uploadingFile')
  if (uploadedFileName.value) return t('fileUploaded')
  if (selectedFile.value) return t('fileReadyToUpload')
  return t('fileUploadHint')
})

const fetchSources = async () => {
  loading.value = true
  try {
    const res = await getSources({ page: page.value, page_size: pageSize.value })
    sources.value = res.data?.list || []
    total.value = res.data?.total || 0
    selectedIds.value = selectedIds.value.filter(id => sources.value.some(item => item.id === id))
  } finally {
    loading.value = false
  }
}
const openCreateModal = () => {
  resetForm()
  sourceModalOpen.value = true
}
const closeSourceModal = () => {
  sourceModalOpen.value = false
  resetForm()
}
const saveSource = async () => {
  formError.value = ''
  form.value.title = (form.value.title || '').trim()
  form.value.url = (form.value.url || '').trim()
  if (!form.value.title) {
    formError.value = t('titleRequired')
    return
  }
  if (!hasLink.value && !hasUploadedFile.value) {
    formError.value = t('sourcePathRequired')
    return
  }
  try {
    if (editingId.value) await updateSource(editingId.value, form.value)
    else await addSource(form.value)
    resetForm()
    sourceModalOpen.value = false
    fetchSources()
  } catch (error) {
    formError.value = error.response?.data?.message || error.response?.data?.detail || t('saveFailed')
  }
}
const editSource = (item) => {
  if (isReviewed(item.review_status)) {
    openSourceDetail(item)
    return
  }
  editingId.value = item.id
  sourceMode.value = item.local_file && !item.url ? 'file' : 'link'
  uploadedFileName.value = item.local_file || ''
  selectedFile.value = null
  form.value = { title: item.title, url: item.url || '', local_file: item.local_file || '', doc_type: item.doc_type || '', issuer: item.issuer || '', region: item.region || t('defaultRegion'), description: item.description || '', validity_status: item.validity_status || '有效', review_status: item.review_status || '待人工复核' }
  sourceModalOpen.value = true
}
const openSourceDetail = (item) => {
  selectedSource.value = item
  detailModalOpen.value = true
}
const closeSourceDetail = () => {
  detailModalOpen.value = false
  selectedSource.value = null
}
const switchSourceMode = (mode) => {
  sourceMode.value = mode
  formError.value = ''
}
const removeSource = async (id) => {
  if (!confirm(t('deleteSourceConfirm'))) return
  await deleteSource(id)
  fetchSources()
}
const toggleReview = async (item) => {
  const nextStatus = isReviewed(item.review_status) ? '待人工复核' : '已复核'
  await reviewSource(item.id, nextStatus)
  fetchSources()
}
const toggleSelected = (id) => {
  selectedIds.value = selectedIds.value.includes(id)
    ? selectedIds.value.filter(item => item !== id)
    : [...selectedIds.value, id]
}
const toggleSelectAll = () => {
  selectedIds.value = allSelected.value ? [] : sources.value.map(item => item.id)
}
const selectedExportParams = () => ({ ids: selectedIds.value.join(',') })
const exportCurrentSources = () => exportSources({})
const exportSelectedSources = () => {
  if (!selectedIds.value.length) {
    alert(t('noSelection'))
    return
  }
  exportSources(selectedExportParams())
}
const handleImport = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  const res = await importSources(file)
  alert(`${t('importFinished')}：${res.data?.imported || 0}/${res.data?.updated || 0}/${res.data?.skipped || 0}`)
  fetchSources()
}
const batchMarkReviewed = async () => {
  if (!selectedIds.value.length) return alert(t('noSelection'))
  await batchSources({ action: 'mark_reviewed', ids: selectedIds.value })
  fetchSources()
}
const batchMarkPending = async () => {
  if (!selectedIds.value.length) return alert(t('noSelection'))
  await batchSources({ action: 'mark_pending', ids: selectedIds.value })
  fetchSources()
}
const batchDeleteSelected = async () => {
  if (!selectedIds.value.length) return alert(t('noSelection'))
  if (!confirm(t('deleteSourceConfirm'))) return
  await batchSources({ action: 'delete', ids: selectedIds.value })
  selectedIds.value = []
  fetchSources()
}
const resetForm = () => {
  editingId.value = null
  sourceMode.value = 'link'
  selectedFile.value = null
  uploadedFileName.value = ''
  uploading.value = false
  formError.value = ''
  form.value = initialForm()
}
const handleFileChange = (event) => {
  selectedFile.value = event.target.files?.[0] || null
  formError.value = ''
}
const uploadSelectedFile = async () => {
  if (!selectedFile.value) return
  uploading.value = true
  try {
    const res = await uploadSourceFile(selectedFile.value)
    form.value.local_file = res.data?.local_file || ''
    form.value.url = ''
    uploadedFileName.value = res.data?.filename || selectedFile.value.name
    if (!form.value.title) form.value.title = selectedFile.value.name.replace(/\.[^.]+$/, '')
    formError.value = ''
  } finally {
    uploading.value = false
  }
}

const isReviewed = (value) => value === '已复核' || value === 'reviewed'
const reviewLabel = (value) => isReviewed(value) ? t('reviewed') : t('pendingManualReview')
const formatTime = (time) => formatDateTime(time)

onMounted(fetchSources)
</script>

<style scoped>
.source-modal {
  width: min(860px, calc(100vw - 32px));
}

.source-description {
  min-height: 130px;
}

.source-detail-modal {
  width: min(860px, calc(100vw - 32px));
}

.batch-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin: -2px 0 12px;
}

.import-button {
  position: relative;
  overflow: hidden;
}

.import-button input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.source-detail {
  display: grid;
  gap: 16px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.detail-grid > div {
  display: grid;
  gap: 4px;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-soft);
  min-width: 0;
}

.detail-grid span {
  color: var(--muted);
}

.detail-grid strong {
  min-width: 0;
  overflow-wrap: anywhere;
}

.source-detail h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.source-detail p,
.detail-link {
  margin: 0;
  display: block;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-soft);
  overflow-wrap: anywhere;
}

.detail-link:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.source-path-tabs,
.source-upload-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.required-mark {
  color: var(--danger);
}

.form-hint {
  color: var(--muted);
  font-size: 13px;
}

.form-error {
  min-height: 38px;
  border: 1px solid rgba(201, 54, 54, 0.28);
  border-radius: 8px;
  padding: 8px 12px;
  background: rgba(201, 54, 54, 0.08);
  color: var(--danger);
  font-weight: 600;
}

.source-upload-box {
  min-height: 96px;
  border: 1px dashed var(--line);
  border-radius: 8px;
  padding: 14px;
  background: var(--surface-soft);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.source-upload-main {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.source-upload-icon {
  width: 42px;
  height: 42px;
  border-radius: 8px;
  background: rgba(23, 105, 224, 0.12);
  color: var(--primary);
  display: grid;
  place-items: center;
  font-size: 24px;
  font-weight: 800;
  flex: 0 0 auto;
}

.source-upload-copy {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.source-upload-copy strong,
.source-upload-copy span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-upload-copy span {
  color: var(--muted);
  font-size: 13px;
}

.source-file-picker {
  position: relative;
  overflow: hidden;
}

.source-file-picker input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.source-file-picker:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(23, 105, 224, 0.12);
}

.source-title-cell {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.source-title-cell .tag {
  flex: 0 0 auto;
}

@media (max-width: 720px) {
  .source-upload-box {
    align-items: stretch;
    flex-direction: column;
  }

  .source-upload-actions {
    width: 100%;
  }

  .source-upload-actions .btn {
    flex: 1 1 160px;
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
