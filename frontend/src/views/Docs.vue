<template>
  <div class="app-page">
    <main class="docs-page">
      <section class="docs-shell">
        <aside class="docs-sidebar">
          <div class="section-title docs-sidebar-title">
            <div>
              <h1>{{ t('docCatalog') }}</h1>
              <p class="page-desc">{{ docCountText }}</p>
            </div>
          </div>

          <input
            v-model="keyword"
            class="input docs-search"
            :placeholder="t('docSearchPlaceholder')"
          />

          <div class="docs-category-list">
            <button
              type="button"
              :class="['docs-category-button', { active: !activeCategory }]"
              @click="activeCategory = ''"
            >
              <span>{{ t('docAllCategories') }}</span>
              <strong>{{ docs.length }}</strong>
            </button>
            <button
              v-for="category in categories"
              :key="category"
              type="button"
              :class="['docs-category-button', { active: activeCategory === category }]"
              @click="activeCategory = category"
            >
              <span>{{ category }}</span>
              <strong>{{ categoryCounts[category] || 0 }}</strong>
            </button>
          </div>
        </aside>

        <section class="docs-main">
          <div class="docs-header">
            <div>
              <h1>{{ t('documentationCenter') }}</h1>
              <p class="page-desc">{{ t('documentationSubtitle') }}</p>
            </div>
            <span class="tag">{{ selectedDoc?.category || t('documentation') }}</span>
          </div>

          <div class="docs-body">
            <div class="docs-list-panel">
              <div v-if="loading" class="loading">{{ t('loading') }}</div>
              <div v-else-if="!filteredDocs.length" class="empty">{{ t('docNoMatch') }}</div>
              <template v-else>
                <button
                  v-for="doc in filteredDocs"
                  :key="doc.id"
                  type="button"
                  :class="['docs-list-item', { active: selectedDocId === doc.id }]"
                  @click="selectDoc(doc.id)"
                >
                  <span class="docs-list-title">{{ doc.title }}</span>
                  <span class="docs-list-summary">{{ doc.summary }}</span>
                  <span class="docs-list-path">{{ doc.path }}</span>
                </button>
              </template>
            </div>

            <article class="docs-preview-panel">
              <div v-if="docLoading" class="loading">{{ t('loading') }}</div>
              <div v-else-if="docError" class="empty">{{ docError }}</div>
              <template v-else-if="selectedDoc">
                <div class="docs-preview-header">
                  <div>
                    <h2>{{ selectedDoc.title }}</h2>
                    <p>{{ selectedDoc.summary }}</p>
                  </div>
                  <span :class="['tag', isHistoricalDoc(selectedDoc) ? 'warning' : 'success']">
                    {{ selectedDoc.accuracy_status }}
                  </span>
                </div>

                <div class="docs-meta-grid">
                  <div>
                    <span>{{ t('docPath') }}</span>
                    <strong>{{ selectedDoc.path }}</strong>
                  </div>
                  <div>
                    <span>{{ t('docAudience') }}</span>
                    <strong>{{ selectedDoc.audience || '-' }}</strong>
                  </div>
                  <div>
                    <span>{{ t('docLastReviewed') }}</span>
                    <strong>{{ selectedDoc.last_reviewed || '-' }}</strong>
                  </div>
                  <div>
                    <span>{{ t('docUpdatedAt') }}</span>
                    <strong>{{ formatDateTime(selectedDoc.updated_at) || '-' }}</strong>
                  </div>
                </div>

                <p class="docs-note">{{ t('docCenterNote') }}</p>
                <div class="docs-markdown markdown-content" v-html="renderedContent"></div>
              </template>
            </article>
          </div>
        </section>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getProjectDoc, getProjectDocs } from '@/api'
import { useI18n } from '@/i18n'
import { renderMarkdown } from '@/utils/markdown'

const route = useRoute()
const router = useRouter()
const { t, formatDateTime } = useI18n()

const docs = ref([])
const selectedDoc = ref(null)
const selectedDocId = ref('')
const activeCategory = ref('')
const keyword = ref('')
const loading = ref(false)
const docLoading = ref(false)
const docError = ref('')

const categories = computed(() => [...new Set(docs.value.map(doc => doc.category).filter(Boolean))])
const categoryCounts = computed(() => docs.value.reduce((counts, doc) => {
  counts[doc.category] = (counts[doc.category] || 0) + 1
  return counts
}, {}))
const docCountText = computed(() => t('docCount').replace('{count}', docs.value.length))
const filteredDocs = computed(() => {
  const term = keyword.value.trim().toLowerCase()
  return docs.value.filter((doc) => {
    const matchesCategory = !activeCategory.value || doc.category === activeCategory.value
    const haystack = [doc.title, doc.path, doc.summary, doc.category, doc.accuracy_status].join(' ').toLowerCase()
    return matchesCategory && (!term || haystack.includes(term))
  })
})
const renderedContent = computed(() => renderMarkdown(selectedDoc.value?.content || ''))
const isHistoricalDoc = (doc) => {
  const status = doc?.accuracy_status || ''
  return status.includes('历史记录') || status.toLowerCase().includes('historical')
}

const selectDoc = async (id, replace = false) => {
  if (!id) return
  selectedDocId.value = id
  docLoading.value = true
  docError.value = ''
  try {
    const res = await getProjectDoc(id)
    selectedDoc.value = res.data
    const nextQuery = { ...route.query, doc: id }
    if (replace) {
      router.replace({ path: '/project-docs', query: nextQuery })
    } else {
      router.push({ path: '/project-docs', query: nextQuery })
    }
  } catch (error) {
    docError.value = error.response?.data?.message || error.response?.data?.detail || t('docLoadFailed')
  } finally {
    docLoading.value = false
  }
}

const loadDocs = async () => {
  loading.value = true
  try {
    const res = await getProjectDocs()
    docs.value = res.data?.list || []
    const routeDoc = String(route.query.doc || '')
    const initialDoc = docs.value.find(doc => doc.id === routeDoc)?.id || docs.value[0]?.id
    if (initialDoc) {
      await selectDoc(initialDoc, true)
    }
  } finally {
    loading.value = false
  }
}

watch(() => route.query.doc, (nextDoc) => {
  const id = String(nextDoc || '')
  if (id && id !== selectedDocId.value && docs.value.some(doc => doc.id === id)) {
    selectDoc(id, true)
  }
})

onMounted(loadDocs)
</script>
