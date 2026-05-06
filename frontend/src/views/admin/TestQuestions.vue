<template>
  <AdminLayout :title="t('testsTitle')" :subtitle="t('testsSubtitle')">
    <section class="panel">
      <div class="section-title">
        <h2>{{ t('testData') }}</h2>
        <button class="btn" @click="fetchTests">{{ t('refresh') }}</button>
      </div>
      <AppTable :columns="testColumns" :rows="tests" :empty-text="t('noTests')" :loading="loading" :loading-text="t('loading')" :sequence-start="sequenceStart">
        <template #cell-difficulty="{ row }">
          <span class="tag">{{ difficultyLabel(row.difficulty) }}</span>
        </template>
        <template #cell-expected_points="{ row }">
          <EllipsisText :value="(row.expected_points || []).join(' / ')" />
        </template>
      </AppTable>
      <AppPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @change="fetchTests" />
    </section>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getTestQuestions } from '@/api'
import { useI18n } from '@/i18n'
import AppPagination from '@/components/AppPagination.vue'
import AppTable from '@/components/AppTable.vue'
import EllipsisText from '@/components/EllipsisText.vue'
import AdminLayout from './AdminLayout.vue'

const { t, difficultyLabel } = useI18n()
const tests = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const sequenceStart = computed(() => (page.value - 1) * pageSize.value + 1)
const testColumns = computed(() => [
  { key: 'sequence', label: t('sequence'), width: '64px' },
  { key: 'question', label: t('question'), width: '38%' },
  { key: 'category', label: t('category'), width: '112px' },
  { key: 'difficulty', label: t('difficulty'), width: '96px' },
  { key: 'expected_points', label: t('expectedPoints'), width: '40%' }
])
const fetchTests = async () => {
  loading.value = true
  try {
    const res = await getTestQuestions({ page: page.value, page_size: pageSize.value })
    tests.value = res.data?.list || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}
onMounted(fetchTests)
</script>
