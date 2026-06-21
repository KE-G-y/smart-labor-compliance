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
          <template #cell-build_finished_at="{ row }">
            {{ formatDateTime(row.build_finished_at || row.created_at) || '-' }}
          </template>
          <template #cell-action="{ row }">
            <div class="table-actions">
              <button
                class="btn primary"
                type="button"
                :disabled="row.is_active || !canActivate(row) || actionId === row.id"
                @click="activate(row)"
              >
                {{ t('activateVectorVersion') }}
              </button>
              <button
                class="btn danger"
                type="button"
                :disabled="row.is_active || row.status === 'archived' || actionId === row.id"
                @click="archive(row)"
              >
                {{ t('archiveVectorVersion') }}
              </button>
            </div>
          </template>
        </AppTable>
        <AppPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @change="fetchVersions" />
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

const sequenceStart = computed(() => (page.value - 1) * pageSize.value + 1)
const statusOptions = computed(() => [
  { value: '', label: t('allStatus') },
  { value: 'active', label: t('vectorVersionActive') },
  { value: 'ready', label: t('vectorVersionReady') },
  { value: 'building', label: t('vectorVersionBuilding') },
  { value: 'failed', label: t('vectorVersionFailed') },
  { value: 'archived', label: t('vectorVersionArchived') }
])
const versionColumns = computed(() => [
  { key: 'sequence', label: t('sequence'), width: '64px' },
  { key: 'tenant_name', label: t('tenant'), width: '140px' },
  { key: 'version', label: t('vectorVersion'), width: '180px' },
  { key: 'collection_name', label: t('milvusCollection'), width: '220px' },
  { key: 'status', label: t('status'), width: '112px' },
  { key: 'indexed_count', label: t('vectorIndexedDocs'), width: '120px' },
  { key: 'chunk_count', label: t('vectorChunks'), width: '96px' },
  { key: 'embedding_model', label: t('langchainEmbeddingModel'), width: '170px' },
  { key: 'build_finished_at', label: t('buildFinishedAt'), width: '170px' },
  { key: 'action', label: t('action'), width: '210px' }
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

const canActivate = (row) => ['ready', 'active'].includes(row.status)

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
  } finally {
    loading.value = false
  }
}

const queryVersions = () => {
  page.value = 1
  fetchVersions()
}

const activate = async (row) => {
  if (!confirm(t('activateVectorVersionConfirm'))) return
  actionId.value = row.id
  try {
    // 激活版本会让后端把当前租户的 milvus_collection 切换到该 collection。
    await activateVectorVersion(row.id, { tenant_id: row.tenant_id })
    await fetchVersions()
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
</style>
