<template>
  <AdminLayout :title="t('accountsTitle')" :subtitle="t('accountsSubtitle')">
    <div class="grid">
      <section class="panel">
        <div class="section-title">
          <h2>{{ t('accountList') }}</h2>
          <div class="toolbar">
            <button class="btn primary" @click="openCreateModal">{{ t('createAccount') }}</button>
            <button class="btn" @click="fetchAdmins">{{ t('refresh') }}</button>
          </div>
        </div>
        <AppTable :columns="accountColumns" :rows="admins" :empty-text="t('noAccounts')" :loading="loading" :loading-text="t('loading')" :sequence-start="sequenceStart">
          <template #cell-role="{ row }">
            <EllipsisText :value="roleLabel(row.role, row.role_label)" />
          </template>
          <template #cell-is_active="{ row }">
            <span :class="['tag', row.is_active ? 'success' : 'warning']">{{ row.is_active ? t('statusActive') : t('statusDisabled') }}</span>
          </template>
          <template #cell-action="{ row }">
            <div class="table-actions">
              <button class="btn danger" :disabled="row.role === 'super_admin'" @click="removeAccount(row)">{{ t('delete') }}</button>
            </div>
          </template>
        </AppTable>
        <AppPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @change="fetchAdmins" />
      </section>
    </div>

    <Teleport to="body">
      <div v-if="createModalOpen" class="modal-mask">
        <div class="modal account-modal">
          <form class="modal-form" @submit.prevent="createAccount">
            <div class="section-title modal-header">
              <h2>{{ t('createAccount') }}</h2>
              <button class="btn ghost" type="button" @click="closeCreateModal">×</button>
            </div>
            <div class="modal-body form-grid">
              <div class="form-group"><label>{{ t('username') }}</label><input v-model="form.username" class="input" required /></div>
              <div class="form-group"><label>{{ t('password') }}</label><input v-model="form.password" type="password" class="input" required /></div>
              <div class="form-group"><label>{{ t('displayName') }}</label><input v-model="form.display_name" class="input" /></div>
              <div class="form-group"><label>{{ t('role') }}</label><AppSelect v-model="form.role" :options="roleOptions" /></div>
            </div>
            <div class="modal-actions modal-footer">
              <button class="btn" type="button" @click="closeCreateModal">{{ t('cancelEdit') }}</button>
              <button class="btn primary" type="submit">{{ t('createAccount') }}</button>
            </div>
          </form>
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
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { addAdmin, deleteAdmin, getAdmins, getRoles } from '@/api'
import { useI18n } from '@/i18n'
import { useDialog } from '@/composables/useDialog'
import AppDialog from '@/components/AppDialog.vue'
import AppPagination from '@/components/AppPagination.vue'
import AppSelect from '@/components/AppSelect.vue'
import AppTable from '@/components/AppTable.vue'
import EllipsisText from '@/components/EllipsisText.vue'
import AdminLayout from './AdminLayout.vue'

const { t, roleLabel } = useI18n()
const { messageDialog, confirmDialog, closeMessage, openConfirm, closeConfirm, runConfirm } = useDialog(t)
const admins = ref([])
const roles = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const createModalOpen = ref(false)
const loading = ref(false)
const defaultRole = () => roles.value.find(item => item.value === 'operator')?.value || roles.value[0]?.value || 'operator'
const initialForm = () => ({ username: '', password: '', role: defaultRole(), display_name: '' })
const form = ref(initialForm())
const sequenceStart = computed(() => (page.value - 1) * pageSize.value + 1)
const accountColumns = computed(() => [
  { key: 'sequence', label: t('sequence'), width: '64px' },
  { key: 'tenant_name', label: t('tenant'), width: '34%' },
  { key: 'username', label: t('username'), width: '24%' },
  { key: 'role', label: t('role'), width: '22%' },
  { key: 'is_active', label: t('status'), width: '96px' },
  { key: 'action', label: t('action'), width: '96px' }
])
const roleOptions = computed(() => roles.value.map(role => ({
  value: role.value,
  label: roleLabel(role.value, role.label)
})))

const fetchAdmins = async () => {
  loading.value = true
  try {
    const res = await getAdmins({ page: page.value, page_size: pageSize.value })
    admins.value = res.data?.list || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}
const fetchRoles = async () => {
  const res = await getRoles()
  roles.value = res.data || []
  form.value.role = defaultRole()
}
const openCreateModal = () => {
  form.value = initialForm()
  createModalOpen.value = true
}
const closeCreateModal = () => {
  createModalOpen.value = false
  form.value = initialForm()
}
const createAccount = async () => {
  await addAdmin(form.value)
  closeCreateModal()
  fetchAdmins()
}
const removeAccount = (account) => {
  openConfirm({
    title: t('delete'),
    message: t('deleteAccountConfirm'),
    confirmText: t('delete'),
    variant: 'danger',
    details: [
      { label: t('username'), value: account.username },
      { label: t('role'), value: roleLabel(account.role, account.role_label) }
    ],
    action: async () => {
      await deleteAdmin(account.id)
      await fetchAdmins()
    }
  })
}

onMounted(() => {
  fetchRoles()
  fetchAdmins()
})
</script>

<style scoped>
.account-modal {
  width: min(760px, calc(100vw - 32px));
}

</style>
