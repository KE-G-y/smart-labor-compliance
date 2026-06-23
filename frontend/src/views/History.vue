<template>
  <div class="app-page">
    <AppTopbar :tenant="tenant" />

    <main class="fixed-workspace">
      <div class="fixed-workspace-inner">
        <section class="fixed-panel">
          <div class="fixed-panel-header compact history-header">
            <div class="section-title history-title">
              <div>
                <h1>{{ t('history') }}</h1>
                <p class="page-desc">{{ t('historyDesc') }}</p>
              </div>
              <div class="toolbar history-actions">
                <button class="btn" :disabled="!total" @click="exportCurrent">{{ t('exportData') }}</button>
                <button class="btn" :disabled="!selectedIds.length" @click="exportSelected">{{ t('exportSelected') }}</button>
                <button class="btn danger" :disabled="!total" @click="clearAll">{{ t('clear') }}</button>
              </div>
            </div>

            <div class="history-toolbar">
              <input
                v-model="keyword"
                class="input history-search"
                :placeholder="t('historySearchPlaceholder')"
                @keyup.enter="queryHistory"
              />
              <AppSelect v-model="status" class="history-filter" :options="statusOptions" />
              <AppSelect v-model="provider" class="history-filter" :options="providerOptions" />
              <button class="btn primary" @click="queryHistory">{{ t('query') }}</button>
              <button class="btn" :disabled="!hasFilters" @click="resetFilters">{{ t('resetFilters') }}</button>
              <button class="btn" :class="{ primary: allItems }" :disabled="!total && !allItems" @click="toggleAllItems">
                {{ allItems ? t('paginatedView') : t('showAll') }}
              </button>
            </div>
          </div>

          <div class="fixed-panel-body history-panel-body">
            <div v-if="loading" class="loading">{{ t('loading') }}</div>
            <div v-else-if="!items.length" class="empty">{{ t('noHistory') }}</div>
            <template v-else>
              <div class="history-batch-bar">
                <label class="history-select-all">
                  <input type="checkbox" :checked="allSelected" @change="toggleSelectAll" />
                  <span>{{ t('selectAllVisible') }}</span>
                </label>
                <span class="muted">{{ selectedCountText }}</span>
                <span class="muted">{{ visibleRangeText }}</span>
              </div>

              <div class="history-list">
                <article v-for="item in items" :key="item.id" class="history-card">
                  <div class="history-card-top">
                    <input
                      class="history-card-check"
                      type="checkbox"
                      :aria-label="t('selectRow')"
                      :checked="selectedIds.includes(item.id)"
                      @change="toggleSelected(item.id)"
                    />
                    <div class="history-card-main">
                      <div class="history-card-title-row">
                        <strong class="history-question">{{ item.question }}</strong>
                        <span class="tag">{{ item.provider }} · {{ item.response_time || 0 }}ms</span>
                      </div>
                      <p class="preline history-answer-preview">{{ item.answer || '-' }}</p>
                    </div>
                  </div>
                  <div class="history-card-footer">
                    <span class="muted">{{ formatTime(item.created_at) }}</span>
                    <div class="history-card-actions">
                      <button class="btn" @click="openDetail(item)">{{ t('viewDetail') }}</button>
                      <button class="btn" @click="exportOne(item)">{{ t('exportSingle') }}</button>
                    </div>
                  </div>
                </article>
              </div>

              <AppPagination
                v-if="!allItems"
                v-model:page="page"
                v-model:page-size="pageSize"
                :total="total"
                :page-size-options="[5, 10, 20, 50, 100]"
                @change="fetchHistory"
              />
            </template>
          </div>
        </section>
      </div>
    </main>

    <Teleport to="body">
      <div v-if="detailModalOpen" class="modal-mask">
        <div class="modal history-detail-modal">
          <div class="section-title modal-header">
            <h2>{{ t('historyDetail') }}</h2>
            <button class="btn ghost" type="button" @click="closeDetail">×</button>
          </div>
          <template v-if="selectedItem">
            <div class="modal-body history-detail">
              <div class="detail-grid">
                <div>
                  <span>{{ t('engine') }}</span>
                  <strong>{{ selectedItem.provider || '-' }}</strong>
                </div>
                <div>
                  <span>{{ t('risk') }}</span>
                  <strong>{{ riskLabel(displayedRiskLevel(selectedItem)) || '-' }}</strong>
                </div>
                <div>
                  <span>{{ t('status') }}</span>
                  <strong>{{ statusLabel(selectedItem.status) || selectedItem.status || '-' }}</strong>
                </div>
                <div>
                  <span>{{ t('response') }}</span>
                  <strong>{{ selectedItem.response_time ?? '-' }}ms</strong>
                </div>
                <div>
                  <span>{{ t('userId') }}</span>
                  <strong>{{ selectedItem.user_id || '-' }}</strong>
                </div>
                <div>
                  <span>{{ t('time') }}</span>
                  <strong>{{ formatTime(selectedItem.created_at) || '-' }}</strong>
                </div>
              </div>

              <section>
                <h3>{{ t('question') }}</h3>
                <p class="preline">{{ selectedItem.question }}</p>
              </section>
              <section>
                <h3>{{ t('answer') }}</h3>
                <div class="markdown-box markdown-content" v-html="renderMarkdown(selectedItem.answer || '-')"></div>
              </section>
              <section v-if="sourceList.length">
                <h3>{{ t('sourcesInfo') }}</h3>
                <div class="history-sources">
                  <template v-for="(source, index) in sourceList" :key="`${source.title || ''}-${source.url || ''}-${index}`">
                    <a v-if="validSourceUrl(source.url)" :href="source.url" target="_blank" rel="noreferrer">
                      <strong>{{ source.title || source.url || '-' }}</strong>
                      <span>{{ source.snippet || source.url || '' }}</span>
                    </a>
                    <div v-else class="history-source-card">
                      <strong>{{ source.title || '-' }}</strong>
                      <span>{{ source.snippet || source.url || '' }}</span>
                    </div>
                  </template>
                </div>
              </section>
              <section v-if="taskList.length">
                <h3>{{ t('tasks') }}</h3>
                <div class="history-tasks">
                  <div v-for="(task, taskIndex) in taskList" :key="`${task.title || ''}-${taskIndex}`" class="history-task-card">
                    <strong>{{ task.title || '-' }}</strong>
                    <ol>
                      <li v-for="(step, stepIndex) in task.steps || []" :key="`${step}-${stepIndex}`">{{ step }}</li>
                    </ol>
                  </div>
                </div>
              </section>
            </div>
            <div class="modal-actions modal-footer">
              <button class="btn" type="button" @click="exportOne(selectedItem)">{{ t('exportSingle') }}</button>
              <button class="btn primary" type="button" @click="closeDetail">{{ t('close') }}</button>
            </div>
          </template>
        </div>
      </div>
    </Teleport>
    <AppDialog
      :open="confirmDialog.open"
      mode="confirm"
      :variant="confirmDialog.variant"
      :title="confirmDialog.title"
      :message="confirmDialog.message"
      :confirm-text="confirmDialog.confirmText"
      :cancel-text="confirmDialog.cancelText"
      :loading-text="t('processing')"
      :loading="confirmDialog.loading"
      :details="confirmDialog.details"
      @confirm="runConfirm"
      @cancel="closeConfirm"
    />
    <AppDialog
      :open="messageDialog.open"
      mode="message"
      :variant="messageDialog.variant"
      :title="messageDialog.title"
      :message="messageDialog.message"
      :close-text="t('close')"
      :details="messageDialog.details"
      @confirm="closeMessage"
      @cancel="closeMessage"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { clearHistory, exportHistory, getHistory, getTenantPublic } from '@/api'
import { useI18n } from '@/i18n'
import { useDialog } from '@/composables/useDialog'
import { renderMarkdown } from '@/utils/markdown'
import { displayedRiskLevel } from '@/utils/risk'
import AppDialog from '@/components/AppDialog.vue'
import AppPagination from '@/components/AppPagination.vue'
import AppSelect from '@/components/AppSelect.vue'
import AppTopbar from '@/components/AppTopbar.vue'

const { t, formatDateTime, riskLabel, statusLabel } = useI18n()
const { messageDialog, confirmDialog, showMessage, closeMessage, openConfirm, closeConfirm, runConfirm } = useDialog(t)
const tenant = ref({})
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const loading = ref(false)
const keyword = ref('')
const status = ref('')
const provider = ref('')
const allItems = ref(false)
const selectedIds = ref([])
const selectedItem = ref(null)
const detailModalOpen = ref(false)

const userId = computed(() => localStorage.getItem('user_id') || 'demo-user')
const hasFilters = computed(() => Boolean(keyword.value.trim() || status.value || provider.value))
const allSelected = computed(() => items.value.length > 0 && items.value.every(item => selectedIds.value.includes(item.id)))
const selectedCountText = computed(() => t('selectedCount').replace('{count}', selectedIds.value.length))
const sourceList = computed(() => Array.isArray(selectedItem.value?.sources) ? selectedItem.value.sources : [])
const taskList = computed(() => Array.isArray(selectedItem.value?.related_tasks) ? selectedItem.value.related_tasks : [])
const visibleRangeText = computed(() => {
  if (!total.value) return t('paginationTotal').replace('{total}', 0)
  if (allItems.value) return t('showingAllCount').replace('{count}', items.value.length).replace('{total}', total.value)
  const start = (page.value - 1) * pageSize.value + 1
  const end = Math.min(total.value, start + items.value.length - 1)
  return t('historyVisibleRange')
    .replace('{start}', start)
    .replace('{end}', end)
    .replace('{total}', total.value)
})
const statusOptions = computed(() => [
  { value: '', label: t('allStatus') },
  { value: 'success', label: t('statusSuccess') },
  { value: 'failed', label: t('statusFailed') }
])
const providerOptions = computed(() => [
  { value: '', label: t('allProviders') },
  { value: 'langchain', label: 'LangChain' },
  { value: 'dify', label: 'Dify' },
  { value: 'local_faq', label: t('localFaq') },
  { value: 'precheck', label: t('precheckProvider') },
  { value: 'kb_no_match', label: t('knowledgeBaseNoMatch') },
  { value: 'langchain_unavailable', label: t('langchainUnavailable') },
  { value: 'dify_unavailable', label: t('difyUnavailable') },
  { value: 'provider_disabled', label: t('providerDisabled') },
  { value: 'knowledge_package_disabled', label: t('knowledgePackageDisabled') }
])

const requestParams = (extra = {}) => ({
  user_id: userId.value,
  keyword: keyword.value.trim() || undefined,
  status: status.value || undefined,
  provider: provider.value || undefined,
  ...extra
})

const fetchHistory = async () => {
  loading.value = true
  try {
    const res = await getHistory(requestParams({
      page: page.value,
      page_size: pageSize.value,
      all_items: allItems.value
    }))
    items.value = res.data?.list || []
    total.value = res.data?.total || 0
    selectedIds.value = selectedIds.value.filter(id => items.value.some(item => item.id === id))
  } finally {
    loading.value = false
  }
}

const queryHistory = () => {
  page.value = 1
  selectedIds.value = []
  fetchHistory()
}

const resetFilters = () => {
  keyword.value = ''
  status.value = ''
  provider.value = ''
  queryHistory()
}

const toggleAllItems = () => {
  allItems.value = !allItems.value
  page.value = 1
  selectedIds.value = []
  fetchHistory()
}

const toggleSelected = (id) => {
  selectedIds.value = selectedIds.value.includes(id)
    ? selectedIds.value.filter(item => item !== id)
    : [...selectedIds.value, id]
}

const toggleSelectAll = () => {
  selectedIds.value = allSelected.value ? [] : items.value.map(item => item.id)
}

const exportCurrent = () => exportHistory(requestParams())

const exportSelected = () => {
  if (!selectedIds.value.length) {
    showMessage(t('noSelection'), { variant: 'warning' })
    return
  }
  exportHistory({ user_id: userId.value, ids: selectedIds.value.join(',') })
}

const exportOne = (item) => {
  if (!item?.id) return
  exportHistory({ user_id: userId.value, ids: String(item.id) })
}

const clearAll = async () => {
  openConfirm({
    title: t('clear'),
    message: t('clearHistoryConfirm'),
    confirmText: t('clear'),
    variant: 'danger',
    successMessage: t('clearHistorySuccess'),
    action: async () => {
      await clearHistory(userId.value)
      items.value = []
      total.value = 0
      selectedIds.value = []
      closeDetail()
    }
  })
}

const openDetail = (item) => {
  selectedItem.value = item
  detailModalOpen.value = true
}

const closeDetail = () => {
  detailModalOpen.value = false
  selectedItem.value = null
}

const formatTime = (time) => formatDateTime(time)
const validSourceUrl = (url) => /^https?:\/\//i.test(url || '')

const loadTenant = async () => {
  try {
    const res = await getTenantPublic()
    tenant.value = res.data || {}
  } catch (error) {
    tenant.value = { name: t('defaultTenantName'), region: t('defaultRegion') }
  }
}

onMounted(() => {
  loadTenant()
  fetchHistory()
})
</script>

<style scoped>
.history-header {
  display: grid;
  gap: 12px;
}

.history-title {
  margin-bottom: 0;
}

.history-actions {
  justify-content: flex-end;
}

.history-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.history-search {
  max-width: 360px;
  flex: 1 1 260px;
}

.history-filter {
  width: 168px;
}

.history-panel-body {
  padding-top: 12px;
}

.history-batch-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  padding: 0 0 12px;
}

.history-select-all {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
}

.history-list {
  display: grid;
  gap: 12px;
}

.history-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
  background: var(--surface);
  display: grid;
  gap: 12px;
}

.history-card-top {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.history-card-check {
  flex: 0 0 auto;
  margin-top: 5px;
}

.history-card-main {
  min-width: 0;
  display: grid;
  gap: 10px;
  flex: 1 1 auto;
}

.history-card-title-row {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.history-question {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-answer-preview {
  margin: 0;
  color: var(--text);
  line-height: 1.7;
  max-height: 118px;
  overflow: hidden;
}

.history-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-left: 28px;
}

.history-card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.history-card-actions .btn {
  min-height: 34px;
  padding: 6px 10px;
}

.history-detail-modal {
  width: min(980px, calc(100vw - 32px));
  max-height: min(760px, calc(100vh - 32px));
}

.history-detail {
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
}

.detail-grid span,
.history-sources span {
  color: var(--muted);
}

.history-detail h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.history-detail p,
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

.history-sources,
.history-tasks {
  display: grid;
  gap: 8px;
}

.history-sources a,
.history-source-card,
.history-task-card {
  display: grid;
  gap: 4px;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  text-decoration: none;
}

.history-sources a:hover {
  border-color: var(--primary);
}

.history-task-card ol {
  margin: 0;
  padding-left: 20px;
}

@media (max-width: 760px) {
  .history-card-title-row,
  .history-card-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .history-card-footer {
    padding-left: 0;
  }

  .history-filter,
  .history-search,
  .history-toolbar .btn {
    width: 100%;
    max-width: none;
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }

  .history-detail-modal {
    width: calc(100vw - 24px);
    max-height: calc(100vh - 24px);
  }
}
</style>
