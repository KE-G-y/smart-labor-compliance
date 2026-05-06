<template>
  <AdminLayout :title="t('tenantsTitle')" :subtitle="t('tenantsSubtitle')">
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
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { addTenant, getTenants } from '@/api'
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
const loading = ref(false)
const sequenceStart = computed(() => (page.value - 1) * pageSize.value + 1)
const tenantColumns = computed(() => [
  { key: 'sequence', label: t('sequence'), width: '64px' },
  { key: 'code', label: t('code'), width: '16%' },
  { key: 'name', label: t('name'), width: '34%' },
  { key: 'region', label: t('region'), width: '88px' },
  { key: 'status', label: t('status'), width: '96px' },
  { key: 'dify_configured', label: 'Dify', width: '104px' },
  { key: 'created_at', label: t('createdAt'), width: '156px' }
])
const initialForm = () => ({ code: '', name: '', industry: '', region: t('defaultRegion'), admin_username: '', admin_password: '', notes: '' })
const form = ref(initialForm())

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

</style>
