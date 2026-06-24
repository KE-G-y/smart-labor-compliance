<template>
  <AdminLayout :title="t('tenantsTitle')" :subtitle="t('tenantsSubtitle')" content-mode="fixed">
    <div class="grid">
      <section class="panel">
        <div class="section-title">
          <h2>{{ t('tenantList') }}</h2>
          <div class="toolbar">
            <button class="btn primary" @click="openCreateModal">{{ t('createTenant') }}</button>
            <button class="btn" @click="fetchTenants">{{ t('refresh') }}</button>
          </div>
        </div>
        <AppTable :columns="tenantColumns" :rows="tenants" :empty-text="t('noTenants')" :loading="loading" :loading-text="t('loading')" :sequence-start="sequenceStart">
          <template #cell-status="{ row }">
            <span :class="['tag', row.status === 'active' ? 'success' : 'warning']">{{ statusLabel(row.status) || row.status }}</span>
          </template>
          <template #cell-dify_configured="{ row }">
            <span :class="['tag', row.dify_configured ? 'success' : 'warning']">{{ row.dify_configured ? t('configured') : t('notConfigured') }}</span>
          </template>
          <template #cell-created_at="{ row }">
            <EllipsisText :value="formatTime(row.created_at)" />
          </template>
          <template #cell-actions="{ row }">
            <button class="btn small" @click="openEditModal(row)">{{ t('edit') }}</button>
          </template>
        </AppTable>
        <AppPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @change="fetchTenants" />
      </section>
    </div>

    <Teleport to="body">
      <div v-if="createModalOpen" class="modal-mask">
        <div class="modal tenant-modal">
          <form class="modal-form" @submit.prevent="createTenant">
            <div class="section-title modal-header">
              <h2>{{ t('addTenant') }}</h2>
              <button class="btn ghost" type="button" @click="closeCreateModal">×</button>
            </div>
            <div class="modal-body form-grid">
              <div class="form-group"><label>{{ t('tenantCode') }}</label><input v-model="form.code" class="input" required /></div>
              <div class="form-group"><label>{{ t('tenantName') }}</label><input v-model="form.name" class="input" required /></div>
              <div class="form-group"><label>{{ t('industry') }}</label><input v-model="form.industry" class="input" /></div>
              <div class="form-group"><label>{{ t('region') }}</label><input v-model="form.region" class="input" /></div>
              <div class="form-group"><label>{{ t('tenantAdmin') }}</label><input v-model="form.admin_username" class="input" :placeholder="t('optional')" /></div>
              <div class="form-group"><label>{{ t('adminPassword') }}</label><input v-model="form.admin_password" class="input" type="password" :placeholder="t('min8')" /></div>
              <div class="form-group full"><label>{{ t('notes') }}</label><textarea v-model="form.notes" class="textarea tenant-notes" /></div>
            </div>
            <div class="modal-actions modal-footer">
              <button class="btn" type="button" @click="closeCreateModal">{{ t('cancelEdit') }}</button>
              <button class="btn primary" type="submit">{{ t('createTenant') }}</button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="editModalOpen" class="modal-mask">
        <div class="modal tenant-modal">
          <form class="modal-form" @submit.prevent="saveEditTenant">
            <div class="section-title modal-header">
              <h2>{{ t('editTenant') || '编辑租户' }}</h2>
              <button class="btn ghost" type="button" @click="closeEditModal">×</button>
            </div>
            <div class="modal-body form-grid">
              <div class="form-group"><label>{{ t('tenantName') }}</label><input v-model="editForm.name" class="input" required /></div>
              <div class="form-group"><label>{{ t('industry') }}</label><input v-model="editForm.industry" class="input" /></div>
              <div class="form-group"><label>{{ t('region') }}</label><input v-model="editForm.region" class="input" /></div>
              <div class="form-group"><label>{{ t('contactName') || '联系人' }}</label><input v-model="editForm.contact_name" class="input" /></div>
              <div class="form-group"><label>{{ t('contactEmail') || '联系邮箱' }}</label><input v-model="editForm.contact_email" class="input" /></div>
              <div class="form-group"><label>{{ t('contactPhone') || '联系电话' }}</label><input v-model="editForm.contact_phone" class="input" /></div>
              <div class="form-group"><label>{{ t('status') || '状态' }}</label>
                <select v-model="editForm.status" class="input">
                  <option value="active">{{ t('active') || '正常' }}</option>
                  <option value="inactive">{{ t('inactive') || '停用' }}</option>
                </select>
              </div>
              <div class="form-group full">
                <label>{{ t('difyApiKey') || 'Dify API Key' }}</label>
                <div class="secret-row">
                  <input
                    v-model="editForm.dify_api_key"
                    class="input"
                    type="password"
                    :disabled="editForm.dify_api_key_clear"
                    :placeholder="editingTenant?.dify_configured ? t('tenantDifyApiKeyConfiguredPlaceholder') : t('difyApiKeyPlaceholder')"
                    @input="editForm.dify_api_key_clear = false"
                  />
                  <button v-if="editingTenant?.dify_configured" class="btn" type="button" @click="toggleTenantDifyClear">
                    {{ editForm.dify_api_key_clear ? t('undoClear') : t('clearApiKey') }}
                  </button>
                </div>
                <div v-if="editingTenant?.dify_configured || editForm.dify_api_key_clear" class="config-hint">
                  <span :class="['tag', editForm.dify_api_key_clear ? 'warning' : 'success']">
                    {{ editForm.dify_api_key_clear ? t('willClear') : t('configured') }}
                  </span>
                  <span>{{ editForm.dify_api_key_clear ? t('apiKeyClearHint') : t('tenantDifyApiKeyConfiguredHint') }}</span>
                </div>
              </div>
              <div class="form-group full"><label>{{ t('notes') }}</label><textarea v-model="editForm.notes" class="textarea tenant-notes" /></div>
            </div>
            <div class="modal-actions modal-footer">
              <button class="btn" type="button" @click="closeEditModal">{{ t('cancelEdit') }}</button>
              <button class="btn primary" type="submit">{{ t('save') || '保存' }}</button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { addTenant, getTenants, updateTenant } from '@/api'
import { useI18n } from '@/i18n'
import AppPagination from '@/components/AppPagination.vue'
import AppTable from '@/components/AppTable.vue'
import EllipsisText from '@/components/EllipsisText.vue'
import AdminLayout from './AdminLayout.vue'

const { t, formatDateTime, statusLabel } = useI18n()
const tenants = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const createModalOpen = ref(false)
const editModalOpen = ref(false)
const editingTenant = ref(null)
const loading = ref(false)
const sequenceStart = computed(() => (page.value - 1) * pageSize.value + 1)
const tenantColumns = computed(() => [
  { key: 'sequence', label: t('sequence'), width: '64px' },
  { key: 'code', label: t('code'), width: '16%' },
  { key: 'name', label: t('name'), width: '34%' },
  { key: 'region', label: t('region'), width: '88px' },
  { key: 'status', label: t('status'), width: '96px' },
  { key: 'dify_configured', label: 'Dify', width: '104px' },
  { key: 'created_at', label: t('createdAt'), width: '156px' },
  { key: 'actions', label: t('actions'), width: '80px' }
])
const initialForm = () => ({ code: '', name: '', industry: '', region: t('defaultRegion'), admin_username: '', admin_password: '', notes: '' })
const editInitialForm = () => ({ name: '', industry: '', region: '', contact_name: '', contact_email: '', contact_phone: '', status: 'active', notes: '', dify_api_key: '', dify_api_key_clear: false })
const form = ref(initialForm())
const editForm = ref(editInitialForm())

const fetchTenants = async () => {
  loading.value = true
  try {
    const res = await getTenants({ page: page.value, page_size: pageSize.value })
    tenants.value = res.data?.list || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

const openCreateModal = () => {
  form.value = initialForm()
  createModalOpen.value = true
}

const closeCreateModal = () => {
  createModalOpen.value = false
}

const createTenant = async () => {
  await addTenant(form.value)
  form.value = initialForm()
  closeCreateModal()
  fetchTenants()
}

const openEditModal = (tenant) => {
  editingTenant.value = tenant
  editForm.value = {
    name: tenant.name || '',
    industry: tenant.industry || '',
    region: tenant.region || '',
    contact_name: tenant.contact_name || '',
    contact_email: tenant.contact_email || '',
    contact_phone: tenant.contact_phone || '',
    status: tenant.status || 'active',
    notes: tenant.notes || '',
    dify_api_key: '',
    dify_api_key_clear: false
  }
  editModalOpen.value = true
}

const closeEditModal = () => {
  editModalOpen.value = false
  editingTenant.value = null
  editForm.value = editInitialForm()
}

const saveEditTenant = async () => {
  const payload = { ...editForm.value }
  const difyKey = (payload.dify_api_key || '').trim()
  if (payload.dify_api_key_clear) {
    payload.dify_api_key = null
  } else if (difyKey) {
    payload.dify_api_key = difyKey
  } else {
    delete payload.dify_api_key
  }
  delete payload.dify_api_key_clear
  await updateTenant(editingTenant.value.id, payload)
  closeEditModal()
  fetchTenants()
}

const toggleTenantDifyClear = () => {
  editForm.value.dify_api_key_clear = !editForm.value.dify_api_key_clear
  if (editForm.value.dify_api_key_clear) {
    editForm.value.dify_api_key = ''
  }
}

const formatTime = (time) => formatDateTime(time)

onMounted(fetchTenants)
</script>

<style scoped>
.tenant-modal {
  width: min(820px, calc(100vw - 32px));
}

.tenant-notes {
  min-height: 100px;
}

.secret-row {
  display: flex;
  gap: 8px;
  align-items: stretch;
}

.secret-row .input {
  min-width: 0;
  flex: 1;
}

.secret-row .btn {
  flex: 0 0 auto;
  white-space: nowrap;
}

.config-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-muted);
}

</style>
