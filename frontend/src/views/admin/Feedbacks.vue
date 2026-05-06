<template>
  <AdminLayout :title="t('feedbacksTitle')" :subtitle="t('feedbacksSubtitle')">
    <section class="panel">
      <div class="toolbar" style="margin-bottom: 14px">
        <AppSelect v-model="status" style="width: 150px" :options="statusOptions" />
        <button class="btn primary" @click="queryFeedbacks">{{ t('query') }}</button>
      </div>
      <AppTable :columns="feedbackColumns" :rows="feedbacks" :empty-text="t('noFeedbacks')" :loading="loading" :loading-text="t('loading')" :sequence-start="sequenceStart">
        <template #cell-is_helpful="{ row }">
          <span :class="['tag', row.is_helpful ? 'success' : 'danger']">{{ row.is_helpful ? t('helpful') : t('notHelpful') }}</span>
        </template>
        <template #cell-status="{ row }">
          <AppSelect v-model="row.status" :options="feedbackStatusOptions" @change="changeStatus(row)" />
        </template>
        <template #cell-created_at="{ row }">
          <EllipsisText :value="formatTime(row.created_at)" />
        </template>
      </AppTable>
      <AppPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @change="fetchFeedbacks" />
    </section>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getFeedbacks, updateFeedbackStatus } from '@/api'
import { useI18n } from '@/i18n'
import AppPagination from '@/components/AppPagination.vue'
import AppSelect from '@/components/AppSelect.vue'
import AppTable from '@/components/AppTable.vue'
import EllipsisText from '@/components/EllipsisText.vue'
import AdminLayout from './AdminLayout.vue'

const { t, formatDateTime } = useI18n()
const feedbacks = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const status = ref('')
const loading = ref(false)
const sequenceStart = computed(() => (page.value - 1) * pageSize.value + 1)
const feedbackColumns = computed(() => [
  { key: 'sequence', label: t('sequence'), width: '64px' },
  { key: 'question', label: t('question'), width: '36%' },
  { key: 'is_helpful', label: t('type'), width: '96px' },
  { key: 'remark', label: t('remark'), width: '30%' },
  { key: 'status', label: t('status'), width: '136px' },
  { key: 'created_at', label: t('time'), width: '156px' }
])
const feedbackStatusOptions = computed(() => [
  { value: 'pending', label: t('statusPending') },
  { value: 'processing', label: t('statusProcessing') },
  { value: 'resolved', label: t('statusResolved') },
  { value: 'ignored', label: t('statusIgnored') }
])
const statusOptions = computed(() => [
  { value: '', label: t('allStatus') },
  ...feedbackStatusOptions.value
])

const fetchFeedbacks = async () => {
  loading.value = true
  try {
    const res = await getFeedbacks({ status: status.value, page: page.value, page_size: pageSize.value })
    feedbacks.value = res.data?.list || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}
const queryFeedbacks = () => {
  page.value = 1
  fetchFeedbacks()
}
const changeStatus = async (item) => {
  await updateFeedbackStatus(item.id, { status: item.status })
}
const formatTime = (time) => formatDateTime(time)

onMounted(fetchFeedbacks)
</script>
