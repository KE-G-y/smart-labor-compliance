<template>
  <AdminLayout :title="t('packagesTitle')" :subtitle="t('packagesSubtitle')">
    <section class="panel">
      <div class="section-title">
        <h2>{{ t('packageList') }}</h2>
        <div class="toolbar">
          <button v-if="canExport" class="btn" @click="exportCurrentPackages">{{ t('exportData') }}</button>
          <button v-if="canExport" class="btn" :disabled="!selectedIds.length" @click="exportSelectedPackages">{{ t('exportSelected') }}</button>
          <label v-if="canImport" class="btn import-button">
            {{ t('importData') }}
            <input type="file" accept=".csv,text/csv" @change="handleImport" />
          </label>
          <button class="btn" @click="fetchPackages">{{ t('refresh') }}</button>
        </div>
      </div>
      <div v-if="canBatch" class="batch-toolbar">
        <span class="muted">{{ selectedCountText }}</span>
        <button class="btn primary" :disabled="!selectedIds.length" @click="batchSetStatus('active')">{{ t('batchEnable') }}</button>
        <button class="btn" :disabled="!selectedIds.length" @click="batchSetStatus('disabled')">{{ t('batchDisable') }}</button>
        <button class="btn danger" :disabled="!selectedIds.length" @click="batchDeleteSelected">{{ t('batchDelete') }}</button>
      </div>
      <AppTable :columns="packageColumns" :rows="packages" :empty-text="t('noPackages')" :loading="loading" :loading-text="t('loading')" :sequence-start="sequenceStart">
        <template #head-select>
          <input type="checkbox" :aria-label="t('selectAll')" :checked="allSelected" @change="toggleSelectAll" />
        </template>
        <template #cell-select="{ row }">
          <input type="checkbox" :aria-label="t('selectRow')" :checked="selectedIds.includes(row.id)" @change="toggleSelected(row.id)" />
        </template>
        <template #cell-status="{ row }">
          <span :class="['tag', row.status === 'active' ? 'success' : 'warning']">{{ statusLabel(row.status) || row.status }}</span>
        </template>
        <template #cell-action="{ row }">
          <div class="table-actions">
            <button class="btn" @click="toggle(row)">{{ row.status === 'active' ? t('disable') : t('enable') }}</button>
          </div>
        </template>
      </AppTable>
      <AppPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @change="fetchPackages" />
    </section>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { batchKnowledgePackages, exportKnowledgePackages, getKnowledgePackages, importKnowledgePackages, updatePackageStatus } from '@/api'
import { useI18n } from '@/i18n'
import AppPagination from '@/components/AppPagination.vue'
import AppTable from '@/components/AppTable.vue'
import AdminLayout from './AdminLayout.vue'

const { t, statusLabel } = useI18n()
const packages = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const selectedIds = ref([])
const loading = ref(false)
const permissions = JSON.parse(localStorage.getItem('admin_permissions') || '[]')
const sequenceStart = computed(() => (page.value - 1) * pageSize.value + 1)
const hasPermission = (permission, fallback) => permissions.includes(permission) || permissions.includes(fallback)
const canImport = computed(() => hasPermission('packages_import', 'packages'))
const canExport = computed(() => hasPermission('packages_export', 'packages'))
const canBatch = computed(() => hasPermission('packages_batch', 'packages'))
const allSelected = computed(() => packages.value.length > 0 && packages.value.every(item => selectedIds.value.includes(item.id)))
const selectedCountText = computed(() => t('selectedCount').replace('{count}', selectedIds.value.length))
const packageColumns = computed(() => [
  { key: 'select', label: '', width: '44px', align: 'center' },
  { key: 'sequence', label: t('sequence'), width: '64px' },
  { key: 'tenant_name', label: t('tenant'), width: '27%' },
  { key: 'name', label: t('name'), width: '29%' },
  { key: 'region', label: t('region'), width: '88px' },
  { key: 'version', label: t('version'), width: '80px' },
  { key: 'faq_count', label: 'FAQ', width: '64px' },
  { key: 'doc_count', label: t('sourceCount'), width: '80px' },
  { key: 'status', label: t('status'), width: '96px' },
  { key: 'action', label: t('action'), width: '88px' }
])
const fetchPackages = async () => {
  loading.value = true
  try {
    const res = await getKnowledgePackages({ page: page.value, page_size: pageSize.value })
    packages.value = res.data?.list || []
    total.value = res.data?.total || 0
    selectedIds.value = selectedIds.value.filter(id => packages.value.some(item => item.id === id))
  } finally {
    loading.value = false
  }
}
const toggle = async (item) => {
  await updatePackageStatus(item.id, { status: item.status === 'active' ? 'disabled' : 'active' })
  fetchPackages()
}
const toggleSelected = (id) => {
  selectedIds.value = selectedIds.value.includes(id)
    ? selectedIds.value.filter(item => item !== id)
    : [...selectedIds.value, id]
}
const toggleSelectAll = () => {
  selectedIds.value = allSelected.value ? [] : packages.value.map(item => item.id)
}
const exportCurrentPackages = () => exportKnowledgePackages({})
const exportSelectedPackages = () => {
  if (!selectedIds.value.length) {
    alert(t('noSelection'))
    return
  }
  exportKnowledgePackages({ ids: selectedIds.value.join(',') })
}
const handleImport = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  const res = await importKnowledgePackages(file)
  alert(`${t('importFinished')}：${res.data?.imported || 0}/${res.data?.updated || 0}/${res.data?.skipped || 0}`)
  fetchPackages()
}
const batchSetStatus = async (status) => {
  if (!selectedIds.value.length) return alert(t('noSelection'))
  await batchKnowledgePackages({ action: 'set_status', status, ids: selectedIds.value })
  fetchPackages()
}
const batchDeleteSelected = async () => {
  if (!selectedIds.value.length) return alert(t('noSelection'))
  if (!confirm(t('batchDelete'))) return
  await batchKnowledgePackages({ action: 'delete', ids: selectedIds.value })
  selectedIds.value = []
  fetchPackages()
}
onMounted(fetchPackages)
</script>

<style scoped>
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
