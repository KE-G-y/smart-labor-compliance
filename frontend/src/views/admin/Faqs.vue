<template>
  <AdminLayout :title="t('faqTitle')" :subtitle="t('faqSubtitle')">
    <div class="grid">
      <section class="panel">
        <div class="section-title">
          <h2>{{ t('faqList') }}</h2>
          <div class="toolbar">
            <input v-model="keyword" class="input" style="width: 240px" :placeholder="t('searchQuestion')" />
            <button class="btn" @click="queryFaqs">{{ t('query') }}</button>
            <button v-if="canExport" class="btn" @click="exportCurrentFaqs">{{ t('exportData') }}</button>
            <button v-if="canExport" class="btn" :disabled="!selectedIds.length" @click="exportSelectedFaqs">{{ t('exportSelected') }}</button>
            <label v-if="canImport" class="btn import-button">
              {{ t('importData') }}
              <input type="file" accept=".csv,text/csv" @change="handleImport" />
            </label>
            <button class="btn primary" @click="openCreateModal">{{ t('addFaq') }}</button>
          </div>
        </div>
        <div v-if="canBatch" class="batch-toolbar">
          <span class="muted">{{ selectedCountText }}</span>
          <button class="btn danger" :disabled="!selectedIds.length" @click="batchDeleteSelected">{{ t('batchDelete') }}</button>
          <button class="btn" :disabled="!selectedIds.length" @click="batchSetRisk('high')">{{ t('batchRiskHigh') }}</button>
          <button class="btn" :disabled="!selectedIds.length" @click="batchSetRisk('medium')">{{ t('batchRiskMedium') }}</button>
          <button class="btn" :disabled="!selectedIds.length" @click="batchSetRisk('low')">{{ t('batchRiskLow') }}</button>
        </div>
        <AppTable :columns="faqColumns" :rows="faqs" :empty-text="t('noFaqs')" :loading="loading" :loading-text="t('loading')" :sequence-start="sequenceStart">
          <template #head-select>
            <input type="checkbox" :aria-label="t('selectAll')" :checked="allSelected" @change="toggleSelectAll" />
          </template>
          <template #cell-select="{ row }">
            <input type="checkbox" :aria-label="t('selectRow')" :checked="selectedIds.includes(row.id)" @change="toggleSelected(row.id)" />
          </template>
          <template #cell-risk_level="{ row }">
            <span :class="['tag', riskClass(row.risk_level)]">{{ riskLabel(row.risk_level) }}</span>
          </template>
          <template #cell-action="{ row }">
            <div class="table-actions">
              <button class="btn" @click="editFaq(row)">{{ t('edit') }}</button>
              <button class="btn danger" @click="removeFaq(row.id)">{{ t('delete') }}</button>
            </div>
          </template>
        </AppTable>
        <AppPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @change="fetchFaqs" />
      </section>
    </div>

    <Teleport to="body">
      <div v-if="faqModalOpen" class="modal-mask">
        <div class="modal faq-modal">
          <form class="modal-form" @submit.prevent="saveFaq">
            <div class="section-title modal-header">
              <h2>{{ editingId ? t('editFaq') : t('addFaq') }}</h2>
              <button class="btn ghost" type="button" @click="closeFaqModal">×</button>
            </div>
            <div class="modal-body form-grid">
              <div class="form-group full"><label>{{ t('question') }}</label><input v-model="form.question" class="input" required /></div>
              <div class="form-group"><label>{{ t('category') }}</label><input v-model="form.category" class="input" /></div>
              <div class="form-group"><label>{{ t('risk') }}</label><AppSelect v-model="form.risk_level" :options="riskOptions" /></div>
              <div class="form-group"><label>{{ t('region') }}</label><input v-model="form.region" class="input" /></div>
              <div class="form-group"><label>{{ t('keywords') }}</label><input v-model="keywordText" class="input" :placeholder="t('commaSeparated')" /></div>
              <div class="form-group full"><label>{{ t('answer') }}</label><textarea v-model="form.answer" class="textarea faq-answer" required /></div>
            </div>
            <div class="modal-actions modal-footer">
              <button class="btn" type="button" @click="closeFaqModal">{{ t('cancelEdit') }}</button>
              <button class="btn primary" type="submit">{{ editingId ? t('saveChanges') : t('addFaq') }}</button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { addFaq, batchFaqs, deleteFaq, exportFaqs, getFaqs, importFaqs, updateFaq } from '@/api'
import { useI18n } from '@/i18n'
import AppPagination from '@/components/AppPagination.vue'
import AppSelect from '@/components/AppSelect.vue'
import AppTable from '@/components/AppTable.vue'
import AdminLayout from './AdminLayout.vue'

const { t, riskLabel } = useI18n()
const faqs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const keywordText = ref('')
const editingId = ref(null)
const faqModalOpen = ref(false)
const selectedIds = ref([])
const loading = ref(false)
const permissions = JSON.parse(localStorage.getItem('admin_permissions') || '[]')
const initialForm = () => ({ question: '', answer: '', category: '', region: t('defaultRegion'), risk_level: 'medium', keywords: [] })
const form = ref(initialForm())
const sequenceStart = computed(() => (page.value - 1) * pageSize.value + 1)
const hasPermission = (permission, fallback) => permissions.includes(permission) || permissions.includes(fallback)
const canImport = computed(() => hasPermission('faqs_import', 'faqs'))
const canExport = computed(() => hasPermission('faqs_export', 'faqs'))
const canBatch = computed(() => hasPermission('faqs_batch', 'faqs'))
const allSelected = computed(() => faqs.value.length > 0 && faqs.value.every(item => selectedIds.value.includes(item.id)))
const selectedCountText = computed(() => t('selectedCount').replace('{count}', selectedIds.value.length))
const faqColumns = computed(() => [
  { key: 'select', label: '', width: '44px', align: 'center' },
  { key: 'sequence', label: t('sequence'), width: '64px' },
  { key: 'question', label: t('question'), width: '30%' },
  { key: 'category', label: t('category'), width: '104px' },
  { key: 'risk_level', label: t('risk'), width: '96px' },
  { key: 'answer', label: t('answerSummary'), width: '42%' },
  { key: 'action', label: t('action'), width: '128px' }
])
const riskOptions = computed(() => [
  { value: 'low', label: t('riskLow') },
  { value: 'medium', label: t('riskMedium') },
  { value: 'high', label: t('riskHigh') }
])

const fetchFaqs = async () => {
  loading.value = true
  try {
    const res = await getFaqs({ keyword: keyword.value, page: page.value, page_size: pageSize.value })
    faqs.value = res.data?.list || []
    total.value = res.data?.total || 0
    selectedIds.value = selectedIds.value.filter(id => faqs.value.some(item => item.id === id))
  } finally {
    loading.value = false
  }
}
const queryFaqs = () => {
  page.value = 1
  fetchFaqs()
}
const openCreateModal = () => {
  resetForm()
  faqModalOpen.value = true
}
const closeFaqModal = () => {
  faqModalOpen.value = false
  resetForm()
}
const saveFaq = async () => {
  const payload = { ...form.value, keywords: keywordText.value.split(/[,，]/).map(v => v.trim()).filter(Boolean) }
  if (editingId.value) await updateFaq(editingId.value, payload)
  else await addFaq(payload)
  resetForm()
  faqModalOpen.value = false
  fetchFaqs()
}
const editFaq = (item) => {
  editingId.value = item.id
  form.value = { question: item.question, answer: item.answer, category: item.category || '', region: item.region || t('defaultRegion'), risk_level: item.risk_level || 'medium', keywords: item.keywords || [] }
  keywordText.value = (item.keywords || []).join(', ')
  faqModalOpen.value = true
}
const removeFaq = async (id) => {
  if (!confirm(t('deleteFaqConfirm'))) return
  await deleteFaq(id)
  fetchFaqs()
}
const toggleSelected = (id) => {
  selectedIds.value = selectedIds.value.includes(id)
    ? selectedIds.value.filter(item => item !== id)
    : [...selectedIds.value, id]
}
const toggleSelectAll = () => {
  selectedIds.value = allSelected.value ? [] : faqs.value.map(item => item.id)
}
const selectedExportParams = () => ({ ids: selectedIds.value.join(',') })
const exportCurrentFaqs = () => exportFaqs({ keyword: keyword.value })
const exportSelectedFaqs = () => {
  if (!selectedIds.value.length) {
    alert(t('noSelection'))
    return
  }
  exportFaqs(selectedExportParams())
}
const handleImport = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  const res = await importFaqs(file)
  alert(`${t('importFinished')}：${res.data?.imported || 0}/${res.data?.updated || 0}/${res.data?.skipped || 0}`)
  fetchFaqs()
}
const batchDeleteSelected = async () => {
  if (!selectedIds.value.length) return alert(t('noSelection'))
  if (!confirm(t('deleteFaqConfirm'))) return
  await batchFaqs({ action: 'delete', ids: selectedIds.value })
  selectedIds.value = []
  fetchFaqs()
}
const batchSetRisk = async (riskLevel) => {
  if (!selectedIds.value.length) return alert(t('noSelection'))
  await batchFaqs({ action: 'set_risk', ids: selectedIds.value, risk_level: riskLevel })
  fetchFaqs()
}
const resetForm = () => {
  editingId.value = null
  form.value = initialForm()
  keywordText.value = ''
}
const riskClass = (risk) => risk === 'high' ? 'danger' : risk === 'medium' ? 'warning' : 'success'

onMounted(fetchFaqs)
</script>

<style scoped>
.faq-modal {
  width: min(860px, calc(100vw - 32px));
}

.faq-answer {
  min-height: 130px;
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

</style>
