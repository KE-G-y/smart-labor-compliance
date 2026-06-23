<template>
  <AdminLayout :title="t('systemConfigTitle')" :subtitle="t('systemConfigSubtitle')">
    <div class="system-config-container">
      <section class="panel">
        <div class="section-title">
          <h2>{{ t('queryStrategyConfig') }}</h2>
          <div class="toolbar">
            <button class="btn" :disabled="loading" @click="fetchConfig">{{ t('refresh') }}</button>
          </div>
        </div>
        <div v-if="loading" class="loading-mask">
          <span>{{ t('loading') }}</span>
        </div>
        <form v-else class="config-form" @submit.prevent="saveConfig">
          <div class="form-group">
            <label>{{ t('queryStrategy') }}</label>
            <select v-model="form.query_strategy" class="input">
              <option v-for="option in queryStrategyOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>
          <div class="config-hint">
            <span class="tag">{{ t('configured') }}</span>
            <span>{{ t(`${form.query_strategy}Hint`) }}</span>
          </div>
        </form>
      </section>

      <section class="panel">
        <div class="section-title">
          <h2>{{ t('langchainConfig') }}</h2>
        </div>
        <div v-if="loading" class="loading-mask">
          <span>{{ t('loading') }}</span>
        </div>
        <form v-else class="config-form" @submit.prevent="saveConfig">
          <div class="form-row">
            <div class="form-group">
              <label>{{ t('langchainBaseUrl') }}</label>
              <input v-model="form.langchain_base_url" class="input" :placeholder="t('langchainBaseUrlPlaceholder')" />
            </div>
            <div class="form-group">
              <label>{{ t('langchainModel') }}</label>
              <input v-model="form.langchain_model" class="input" :placeholder="t('langchainModelPlaceholder')" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>{{ t('langchainEmbeddingModel') }}</label>
              <input v-model="form.langchain_embedding_model" class="input" :placeholder="t('langchainEmbeddingModelPlaceholder')" />
            </div>
            <div class="form-group">
              <label>{{ t('langchainTemperature') }}</label>
              <input v-model.number="form.langchain_temperature" class="input" type="number" min="0" max="2" step="0.1" />
            </div>
          </div>
          <div class="form-group">
            <label>{{ t('langchainTimeout') }}</label>
            <div class="input-group">
              <input v-model.number="form.langchain_timeout_seconds" class="input" type="number" min="5" max="300" />
              <span class="input-addon">{{ t('seconds') }}</span>
            </div>
          </div>
          <div class="form-group">
            <label>{{ t('langchainApiKey') }}</label>
            <div class="secret-row">
              <input
                v-model="form.langchain_api_key"
                class="input"
                type="password"
                :disabled="form.langchain_api_key_clear"
                :placeholder="form.langchain_api_key_configured ? t('langchainApiKeyConfiguredPlaceholder') : t('langchainApiKeyPlaceholder')"
                @input="form.langchain_api_key_clear = false"
              />
              <button v-if="form.langchain_api_key_configured" class="btn" type="button" @click="toggleSecretClear('langchain')">
                {{ form.langchain_api_key_clear ? t('undoClear') : t('clearApiKey') }}
              </button>
            </div>
            <div v-if="form.langchain_api_key_configured || form.langchain_api_key_clear" class="config-hint">
              <span :class="['tag', form.langchain_api_key_clear ? 'warning' : 'success']">
                {{ form.langchain_api_key_clear ? t('willClear') : t('configured') }}
              </span>
              <span>{{ form.langchain_api_key_clear ? t('apiKeyClearHint') : t('langchainApiKeyConfiguredHint') }}</span>
            </div>
          </div>
        </form>
      </section>

      <section class="panel">
        <div class="section-title">
          <h2>{{ t('langsmithConfig') }}</h2>
        </div>
        <div v-if="loading" class="loading-mask">
          <span>{{ t('loading') }}</span>
        </div>
        <form v-else class="config-form" @submit.prevent="saveConfig">
          <div class="toggle-row">
            <label>
              <input v-model="form.langsmith_tracing_enabled" type="checkbox" />
              <span>{{ t('langsmithTracingEnabled') }}</span>
            </label>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>{{ t('langsmithEndpoint') }}</label>
              <input v-model="form.langsmith_endpoint" class="input" :placeholder="t('langsmithEndpointPlaceholder')" />
            </div>
            <div class="form-group">
              <label>{{ t('langsmithProject') }}</label>
              <input v-model="form.langsmith_project" class="input" :placeholder="t('langsmithProjectPlaceholder')" />
            </div>
          </div>
          <div class="form-group">
            <label>{{ t('langsmithApiKey') }}</label>
            <div class="secret-row">
              <input
                v-model="form.langsmith_api_key"
                class="input"
                type="password"
                :disabled="form.langsmith_api_key_clear"
                :placeholder="form.langsmith_api_key_configured ? t('langsmithApiKeyConfiguredPlaceholder') : t('langsmithApiKeyPlaceholder')"
                @input="form.langsmith_api_key_clear = false"
              />
              <button v-if="form.langsmith_api_key_configured" class="btn" type="button" @click="toggleSecretClear('langsmith')">
                {{ form.langsmith_api_key_clear ? t('undoClear') : t('clearApiKey') }}
              </button>
            </div>
            <div v-if="form.langsmith_api_key_configured || form.langsmith_api_key_clear" class="config-hint">
              <span :class="['tag', form.langsmith_api_key_clear ? 'warning' : 'success']">
                {{ form.langsmith_api_key_clear ? t('willClear') : t('configured') }}
              </span>
              <span>{{ form.langsmith_api_key_clear ? t('apiKeyClearHint') : t('langsmithApiKeyConfiguredHint') }}</span>
            </div>
          </div>
          <div class="config-hint">
            <span class="tag">{{ t('langsmithHintTag') }}</span>
            <span>{{ t('langsmithHint') }}</span>
          </div>
        </form>
      </section>

      <section class="panel">
        <div class="section-title">
          <h2>{{ t('milvusConfig') }}</h2>
        </div>
        <div v-if="loading" class="loading-mask">
          <span>{{ t('loading') }}</span>
        </div>
        <form v-else class="config-form" @submit.prevent="saveConfig">
          <div class="form-row">
            <div class="form-group">
              <label>{{ t('milvusUri') }}</label>
              <input v-model="form.milvus_uri" class="input" :placeholder="t('milvusUriPlaceholder')" />
            </div>
            <div class="form-group">
              <label>{{ t('vectorVersion') }}</label>
              <AppSelect
                v-model="form.active_vector_version_id"
                :options="vectorVersionOptions"
                :placeholder="t('vectorVersionSelectPlaceholder')"
                :disabled="vectorVersionsLoading || !vectorVersionOptions.length"
                @change="handleVectorVersionChange"
              />
              <div class="config-hint">
                <span v-if="selectedVectorVersion" :class="['tag', selectedVectorVersion.is_active ? 'success' : 'warning']">
                  {{ selectedVectorVersion?.is_active ? t('vectorVersionActive') : t('pendingActivation') }}
                </span>
                <span>{{ selectedVectorVersionHint }}</span>
              </div>
            </div>
          </div>
          <div class="form-group">
            <label>{{ t('milvusCollection') }}</label>
            <input v-model="form.milvus_collection" class="input readonly-input" readonly :placeholder="t('milvusCollectionPlaceholder')" />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>{{ t('vectorTopK') }}</label>
              <input v-model.number="form.vector_top_k" class="input" type="number" min="1" max="12" />
            </div>
            <div class="form-group">
              <label>{{ t('vectorChunkSize') }}</label>
              <input v-model.number="form.vector_chunk_size" class="input" type="number" min="300" max="5000" />
            </div>
          </div>
          <div class="form-group">
            <label>{{ t('vectorChunkOverlap') }}</label>
            <input v-model.number="form.vector_chunk_overlap" class="input" type="number" min="0" max="1000" />
          </div>
          <div class="form-group">
            <label>{{ t('milvusToken') }}</label>
            <div class="secret-row">
              <input
                v-model="form.milvus_token"
                class="input"
                type="password"
                :disabled="form.milvus_token_clear"
                :placeholder="form.milvus_token_configured ? t('milvusTokenConfiguredPlaceholder') : t('milvusTokenPlaceholder')"
                @input="form.milvus_token_clear = false"
              />
              <button v-if="form.milvus_token_configured" class="btn" type="button" @click="toggleSecretClear('milvus')">
                {{ form.milvus_token_clear ? t('undoClear') : t('clearApiKey') }}
              </button>
            </div>
            <div v-if="form.milvus_token_configured || form.milvus_token_clear" class="config-hint">
              <span :class="['tag', form.milvus_token_clear ? 'warning' : 'success']">
                {{ form.milvus_token_clear ? t('willClear') : t('configured') }}
              </span>
              <span>{{ form.milvus_token_clear ? t('apiKeyClearHint') : t('milvusTokenConfiguredHint') }}</span>
            </div>
          </div>
        </form>
      </section>

      <section class="panel">
        <div class="section-title">
          <h2>{{ t('localModelConfig') }}</h2>
        </div>
        <div v-if="loading" class="loading-mask">
          <span>{{ t('loading') }}</span>
        </div>
        <form v-else class="config-form" @submit.prevent="saveConfig">
          <div class="toggle-row">
            <label>
              <input v-model="form.local_embedding_enabled" type="checkbox" />
              <span>{{ t('localEmbeddingEnabled') }}</span>
            </label>
            <label>
              <input v-model="form.local_reranker_enabled" type="checkbox" />
              <span>{{ t('localRerankerEnabled') }}</span>
            </label>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>{{ t('localEmbeddingModelPath') }}</label>
              <input v-model="form.local_embedding_model_path" class="input" :placeholder="t('localEmbeddingModelPathPlaceholder')" />
            </div>
            <div class="form-group">
              <label>{{ t('localRerankerModelPath') }}</label>
              <input v-model="form.local_reranker_model_path" class="input" :placeholder="t('localRerankerModelPathPlaceholder')" />
            </div>
          </div>
          <div class="form-group">
            <label>{{ t('localFallbackBertModelPath') }}</label>
            <input v-model="form.local_fallback_bert_model_path" class="input" :placeholder="t('localFallbackBertModelPathPlaceholder')" />
          </div>
          <div class="config-hint">
            <span class="tag">{{ t('localModelHintTag') }}</span>
            <span>{{ t('localModelHint') }}</span>
          </div>
        </form>
      </section>

      <section class="panel">
        <div class="section-title">
          <h2>{{ t('difyConfig') }}</h2>
        </div>
        <div v-if="loading" class="loading-mask">
          <span>{{ t('loading') }}</span>
        </div>
        <form v-else class="config-form" @submit.prevent="saveConfig">
          <div class="form-row">
            <div class="form-group">
              <label>{{ t('difyBaseUrl') }}</label>
              <input v-model="form.dify_base_url" class="input" :placeholder="t('difyBaseUrlPlaceholder')" />
            </div>
            <div class="form-group">
              <label>{{ t('difyTimeout') }}</label>
              <div class="input-group">
                <input v-model.number="form.dify_timeout_seconds" class="input" type="number" min="5" max="300" />
                <span class="input-addon">{{ t('seconds') }}</span>
              </div>
            </div>
          </div>
          <div class="form-group">
            <label>{{ t('difyApiKey') }}</label>
            <div class="secret-row">
              <input
                v-model="form.dify_api_key"
                class="input"
                type="password"
                :disabled="form.dify_api_key_clear"
                :placeholder="form.dify_api_key_configured ? t('difyApiKeyConfiguredPlaceholder') : t('difyApiKeyPlaceholder')"
                @input="form.dify_api_key_clear = false"
              />
              <button v-if="form.dify_api_key_configured" class="btn" type="button" @click="toggleSecretClear('dify')">
                {{ form.dify_api_key_clear ? t('undoClear') : t('clearApiKey') }}
              </button>
            </div>
            <div v-if="form.dify_api_key_configured || form.dify_api_key_clear" class="config-hint">
              <span :class="['tag', form.dify_api_key_clear ? 'warning' : 'success']">
                {{ form.dify_api_key_clear ? t('willClear') : t('configured') }}
              </span>
              <span>{{ form.dify_api_key_clear ? t('apiKeyClearHint') : t('difyApiKeyConfiguredHint') }}</span>
            </div>
          </div>
        </form>
      </section>

      <section class="panel">
        <div class="section-title">
          <h2>{{ t('ragflowConfig') }}</h2>
        </div>
        <div v-if="loading" class="loading-mask">
          <span>{{ t('loading') }}</span>
        </div>
        <form v-else class="config-form" @submit.prevent="saveConfig">
          <div class="form-row">
            <div class="form-group">
              <label>{{ t('ragflowBaseUrl') }}</label>
              <input v-model="form.ragflow_base_url" class="input" :placeholder="t('ragflowBaseUrlPlaceholder')" />
            </div>
            <div class="form-group">
              <label>{{ t('ragflowWebUrl') }}</label>
              <input v-model="form.ragflow_web_url" class="input" :placeholder="t('ragflowWebUrlPlaceholder')" />
            </div>
          </div>
          <div class="form-group">
            <label>{{ t('ragflowApiKey') }}</label>
            <div class="secret-row">
              <input
                v-model="form.ragflow_api_key"
                class="input"
                type="password"
                :disabled="form.ragflow_api_key_clear"
                :placeholder="form.ragflow_api_key_configured ? t('ragflowApiKeyConfiguredPlaceholder') : t('ragflowApiKeyPlaceholder')"
                @input="form.ragflow_api_key_clear = false"
              />
              <button v-if="form.ragflow_api_key_configured" class="btn" type="button" @click="toggleSecretClear('ragflow')">
                {{ form.ragflow_api_key_clear ? t('undoClear') : t('clearApiKey') }}
              </button>
            </div>
            <div v-if="form.ragflow_api_key_configured || form.ragflow_api_key_clear" class="config-hint">
              <span :class="['tag', form.ragflow_api_key_clear ? 'warning' : 'success']">
                {{ form.ragflow_api_key_clear ? t('willClear') : t('configured') }}
              </span>
              <span>{{ form.ragflow_api_key_clear ? t('apiKeyClearHint') : t('ragflowApiKeyConfiguredHint') }}</span>
            </div>
          </div>
          <div class="form-group">
            <label>{{ t('ragflowTimeout') }}</label>
            <div class="input-group">
              <input v-model.number="form.ragflow_timeout_seconds" class="input" type="number" min="5" max="120" />
              <span class="input-addon">{{ t('seconds') }}</span>
            </div>
          </div>
        </form>
      </section>

      <section class="panel">
        <div class="form-actions">
          <button type="button" class="btn primary" :disabled="saving || loading" @click="saveConfig">
            {{ saving ? t('saving') : t('saveConfig') }}
          </button>
        </div>
      </section>
    </div>
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
import { activateVectorVersion, getSystemConfig, getVectorVersions, updateSystemConfig } from '@/api'
import { useI18n } from '@/i18n'
import { useDialog } from '@/composables/useDialog'
import AppDialog from '@/components/AppDialog.vue'
import AppSelect from '@/components/AppSelect.vue'
import AdminLayout from './AdminLayout.vue'

const { t } = useI18n()
const { messageDialog, showMessage, closeMessage } = useDialog(t)
const loading = ref(false)
const saving = ref(false)
const vectorVersionsLoading = ref(false)
const vectorVersions = ref([])
const originalActiveVectorVersionId = ref('')
const queryStrategyOptions = [
  // 管理员在这里决定用户问答优先走哪条链路；后端会按同名策略排序调用 provider。
  { value: 'langchain_first', label: t('langchainFirst') },
  { value: 'dify_first', label: t('difyFirst') },
  { value: 'langchain_only', label: t('langchainOnly') },
  { value: 'dify_only', label: t('difyOnly') },
  { value: 'vector_only', label: t('vectorOnly') },
]
const form = ref({
  query_strategy: 'langchain_first',
  langchain_base_url: '',
  langchain_api_key: '',
  langchain_api_key_configured: false,
  langchain_api_key_clear: false,
  langchain_model: 'gpt-4o-mini',
  langchain_embedding_model: 'bge-m3',
  langchain_temperature: 0.2,
  langchain_timeout_seconds: 45,
  langsmith_tracing_enabled: false,
  langsmith_endpoint: 'https://api.smith.langchain.com',
  langsmith_api_key: '',
  langsmith_api_key_configured: false,
  langsmith_api_key_clear: false,
  langsmith_project: 'smart-labor-compliance',
  milvus_uri: '',
  milvus_token: '',
  milvus_token_configured: false,
  milvus_token_clear: false,
  milvus_collection: 'slc_compliance_docs',
  active_vector_version_id: '',
  vector_top_k: 4,
  vector_chunk_size: 1000,
  vector_chunk_overlap: 150,
  local_embedding_enabled: true,
  local_embedding_model_path: 'models/bge-m3',
  local_reranker_enabled: true,
  local_reranker_model_path: 'models/bge-reranker-large',
  local_fallback_bert_model_path: 'models/bert-base-chinese',
  dify_base_url: '',
  dify_api_key: '',
  dify_api_key_configured: false,
  dify_api_key_clear: false,
  dify_timeout_seconds: 30,
  ragflow_base_url: '',
  ragflow_web_url: '',
  ragflow_api_key: '',
  ragflow_api_key_configured: false,
  ragflow_api_key_clear: false,
  ragflow_timeout_seconds: 10,
})

const cleanSecret = (value) => (value || '').trim()
const normalizeId = (value) => (value === undefined || value === null ? '' : String(value))
const usableVectorVersions = computed(() => vectorVersions.value.filter(item => ['ready', 'active'].includes(item.status) || item.is_active))
const selectedVectorVersion = computed(() => {
  const selectedId = normalizeId(form.value.active_vector_version_id)
  return usableVectorVersions.value.find(item => normalizeId(item.id) === selectedId) || null
})
const vectorVersionOptions = computed(() => usableVectorVersions.value.map(item => ({
  value: normalizeId(item.id),
  label: vectorVersionLabel(item)
})))
const selectedVectorVersionHint = computed(() => {
  if (vectorVersionsLoading.value) return t('loading')
  if (!usableVectorVersions.value.length) return t('noUsableVectorVersionsHint')
  if (!selectedVectorVersion.value) return t('vectorVersionSelectHint')
  return `${selectedVectorVersion.value.collection_name} · ${selectedVectorVersion.value.chunk_count || 0} ${t('vectorChunks')}`
})

const vectorVersionLabel = (item) => {
  const status = item.is_active ? t('vectorVersionActive') : (item.status === 'ready' ? t('vectorVersionReady') : item.status)
  const chunks = item.chunk_count || 0
  return `${item.version || item.collection_name} · ${status} · ${chunks} ${t('vectorChunks')}`
}

const fetchVectorVersions = async () => {
  vectorVersionsLoading.value = true
  try {
    const res = await getVectorVersions({ page: 1, page_size: 100 })
    vectorVersions.value = res.data?.list || []
    syncSelectedVectorVersion()
  } finally {
    vectorVersionsLoading.value = false
  }
}

const syncSelectedVectorVersion = () => {
  const activeId = normalizeId(form.value.active_vector_version_id)
  if (activeId && usableVectorVersions.value.some(item => normalizeId(item.id) === activeId)) {
    return
  }
  const byCollection = usableVectorVersions.value.find(item => item.collection_name === form.value.milvus_collection)
  if (byCollection) {
    form.value.active_vector_version_id = normalizeId(byCollection.id)
    return
  }
  const active = usableVectorVersions.value.find(item => item.is_active)
  if (active) {
    form.value.active_vector_version_id = normalizeId(active.id)
    if (!form.value.milvus_collection) form.value.milvus_collection = active.collection_name
  }
}

const handleVectorVersionChange = (_value, option) => {
  const version = usableVectorVersions.value.find(item => normalizeId(item.id) === normalizeId(option?.value || form.value.active_vector_version_id))
  if (version) {
    form.value.milvus_collection = version.collection_name
  }
}

const fetchConfig = async () => {
  loading.value = true
  try {
    const res = await getSystemConfig()
    if (res.data) {
      form.value.query_strategy = res.data.query_strategy || 'langchain_first'
      // 后端不会把真实密钥回传给前端，只返回 *_configured 标记。
      // 因此前端密码框保持空值，用占位符告诉管理员“已配置”。
      form.value.langchain_base_url = res.data.langchain_base_url || ''
      form.value.langchain_api_key = ''
      form.value.langchain_api_key_configured = res.data.langchain_api_key_configured || false
      form.value.langchain_api_key_clear = false
      form.value.langchain_model = res.data.langchain_model || 'gpt-4o-mini'
      form.value.langchain_embedding_model = res.data.langchain_embedding_model || 'bge-m3'
      form.value.langchain_temperature = res.data.langchain_temperature ?? 0.2
      form.value.langchain_timeout_seconds = res.data.langchain_timeout_seconds || 45
      form.value.langsmith_tracing_enabled = res.data.langsmith_tracing_enabled ?? false
      form.value.langsmith_endpoint = res.data.langsmith_endpoint || 'https://api.smith.langchain.com'
      form.value.langsmith_api_key = ''
      form.value.langsmith_api_key_configured = res.data.langsmith_api_key_configured || false
      form.value.langsmith_api_key_clear = false
      form.value.langsmith_project = res.data.langsmith_project || 'smart-labor-compliance'
      form.value.milvus_uri = res.data.milvus_uri || ''
      form.value.milvus_token = ''
      form.value.milvus_token_configured = res.data.milvus_token_configured || false
      form.value.milvus_token_clear = false
      form.value.milvus_collection = res.data.milvus_collection || 'slc_compliance_docs'
      form.value.active_vector_version_id = normalizeId(res.data.active_vector_version_id)
      originalActiveVectorVersionId.value = normalizeId(res.data.active_vector_version_id)
      form.value.vector_top_k = res.data.vector_top_k || 4
      form.value.vector_chunk_size = res.data.vector_chunk_size || 1000
      form.value.vector_chunk_overlap = res.data.vector_chunk_overlap ?? 150
      form.value.local_embedding_enabled = res.data.local_embedding_enabled ?? true
      form.value.local_embedding_model_path = res.data.local_embedding_model_path || 'models/bge-m3'
      form.value.local_reranker_enabled = res.data.local_reranker_enabled ?? true
      form.value.local_reranker_model_path = res.data.local_reranker_model_path || 'models/bge-reranker-large'
      form.value.local_fallback_bert_model_path = res.data.local_fallback_bert_model_path || 'models/bert-base-chinese'
      form.value.dify_base_url = res.data.dify_base_url || ''
      form.value.dify_api_key = ''
      form.value.dify_api_key_configured = res.data.dify_api_key_configured || false
      form.value.dify_api_key_clear = false
      form.value.dify_timeout_seconds = res.data.dify_timeout_seconds || 30
      form.value.ragflow_base_url = res.data.ragflow_base_url || ''
      form.value.ragflow_web_url = res.data.ragflow_web_url || ''
      form.value.ragflow_api_key = ''
      form.value.ragflow_api_key_configured = res.data.ragflow_api_key_configured || false
      form.value.ragflow_api_key_clear = false
      form.value.ragflow_timeout_seconds = res.data.ragflow_timeout_seconds || 10
      syncSelectedVectorVersion()
    }
  } finally {
    loading.value = false
  }
}

const toggleSecretClear = (provider) => {
  const clearKey = provider === 'milvus' ? 'milvus_token_clear' : `${provider}_api_key_clear`
  const secretKey = provider === 'milvus' ? 'milvus_token' : `${provider}_api_key`
  form.value[clearKey] = !form.value[clearKey]
  if (form.value[clearKey]) {
    form.value[secretKey] = ''
  }
}

const saveConfig = async () => {
  saving.value = true
  try {
    const payload = {}
    // 只提交管理员实际可编辑的运行时配置。密钥为空时不覆盖旧值；
    // 点击“清除”才显式传 null 给后端删除密钥。
    if (form.value.query_strategy !== undefined) payload.query_strategy = form.value.query_strategy
    if (form.value.langchain_base_url !== undefined) payload.langchain_base_url = form.value.langchain_base_url
    if (form.value.langchain_api_key_clear) {
      payload.langchain_api_key = null
    } else if (cleanSecret(form.value.langchain_api_key)) {
      payload.langchain_api_key = cleanSecret(form.value.langchain_api_key)
    }
    if (form.value.langchain_model !== undefined) payload.langchain_model = form.value.langchain_model
    if (form.value.langchain_embedding_model !== undefined) payload.langchain_embedding_model = form.value.langchain_embedding_model
    if (form.value.langchain_temperature !== undefined && form.value.langchain_temperature !== '') payload.langchain_temperature = form.value.langchain_temperature
    if (form.value.langchain_timeout_seconds !== undefined && form.value.langchain_timeout_seconds !== '') payload.langchain_timeout_seconds = form.value.langchain_timeout_seconds
    payload.langsmith_tracing_enabled = Boolean(form.value.langsmith_tracing_enabled)
    if (form.value.langsmith_endpoint !== undefined) payload.langsmith_endpoint = form.value.langsmith_endpoint
    if (form.value.langsmith_api_key_clear) {
      payload.langsmith_api_key = null
    } else if (cleanSecret(form.value.langsmith_api_key)) {
      payload.langsmith_api_key = cleanSecret(form.value.langsmith_api_key)
    }
    if (form.value.langsmith_project !== undefined) payload.langsmith_project = form.value.langsmith_project
    if (form.value.milvus_uri !== undefined) payload.milvus_uri = form.value.milvus_uri
    if (form.value.milvus_token_clear) {
      payload.milvus_token = null
    } else if (cleanSecret(form.value.milvus_token)) {
      payload.milvus_token = cleanSecret(form.value.milvus_token)
    }
    if (form.value.vector_top_k !== undefined && form.value.vector_top_k !== '') payload.vector_top_k = form.value.vector_top_k
    if (form.value.vector_chunk_size !== undefined && form.value.vector_chunk_size !== '') payload.vector_chunk_size = form.value.vector_chunk_size
    if (form.value.vector_chunk_overlap !== undefined && form.value.vector_chunk_overlap !== '') payload.vector_chunk_overlap = form.value.vector_chunk_overlap
    payload.local_embedding_enabled = Boolean(form.value.local_embedding_enabled)
    if (form.value.local_embedding_model_path !== undefined) payload.local_embedding_model_path = form.value.local_embedding_model_path
    payload.local_reranker_enabled = Boolean(form.value.local_reranker_enabled)
    if (form.value.local_reranker_model_path !== undefined) payload.local_reranker_model_path = form.value.local_reranker_model_path
    if (form.value.local_fallback_bert_model_path !== undefined) payload.local_fallback_bert_model_path = form.value.local_fallback_bert_model_path
    if (form.value.dify_base_url !== undefined) payload.dify_base_url = form.value.dify_base_url
    if (form.value.dify_api_key_clear) {
      payload.dify_api_key = null
    } else if (cleanSecret(form.value.dify_api_key)) {
      payload.dify_api_key = cleanSecret(form.value.dify_api_key)
    }
    if (form.value.dify_timeout_seconds !== undefined && form.value.dify_timeout_seconds !== '') payload.dify_timeout_seconds = form.value.dify_timeout_seconds
    if (form.value.ragflow_base_url !== undefined) payload.ragflow_base_url = form.value.ragflow_base_url
    if (form.value.ragflow_web_url !== undefined) payload.ragflow_web_url = form.value.ragflow_web_url
    if (form.value.ragflow_api_key_clear) {
      payload.ragflow_api_key = null
    } else if (cleanSecret(form.value.ragflow_api_key)) {
      payload.ragflow_api_key = cleanSecret(form.value.ragflow_api_key)
    }
    if (form.value.ragflow_timeout_seconds !== undefined && form.value.ragflow_timeout_seconds !== '') payload.ragflow_timeout_seconds = form.value.ragflow_timeout_seconds
    await updateSystemConfig(payload)
    const selectedId = normalizeId(form.value.active_vector_version_id)
    if (selectedId && selectedId !== originalActiveVectorVersionId.value) {
      const version = selectedVectorVersion.value
      await activateVectorVersion(selectedId, version?.tenant_id ? { tenant_id: version.tenant_id } : {})
    }
    showMessage(t('saveSuccess') || '保存成功', {
      title: t('operationSuccess'),
      variant: 'success'
    })
    await fetchConfig()
    await fetchVectorVersions()
  } catch (e) {
    const errorMessage = e.response?.data?.message || e.response?.data?.detail || e.message || t('saveFailed') || '保存失败'
    showMessage(errorMessage, {
      title: t('operationFailed'),
      variant: 'danger'
    })
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await Promise.all([fetchConfig(), fetchVectorVersions()])
})
</script>

<style scoped>
.system-config-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-bottom: 16px;
}

.system-config-container > .panel {
  flex-shrink: 0;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 20px;
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
}

.toggle-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.toggle-row label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  color: var(--text);
}

.section-title h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}

.config-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

.form-group .input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.form-group .input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(23, 105, 224, 0.12);
}

.form-group .input:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.form-group .readonly-input {
  color: var(--text-secondary);
  background: rgba(0, 0, 0, 0.02);
}

.form-group .input::placeholder {
  color: var(--text-muted);
  font-style: italic;
  opacity: 0.6;
}

.form-group .input.default-value {
  color: var(--text-muted);
  background: rgba(0, 0, 0, 0.02);
  border-color: rgba(0, 0, 0, 0.1);
}

.form-group .input.default-value::placeholder {
  opacity: 0.4;
}

.input-group {
  display: flex;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.input-group:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(23, 105, 224, 0.12);
}

.input-group .input {
  border: none;
  border-radius: 0;
  padding-right: 8px;
}

.input-addon {
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.05);
  color: var(--text-muted);
  font-size: 13px;
  white-space: nowrap;
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

.loading-mask {
  padding: 40px;
  text-align: center;
  color: var(--text-muted);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}

.form-actions .btn {
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 8px;
}

.form-actions .btn.primary {
  background: var(--primary);
  color: white;
  border: none;
}

.form-actions .btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .form-row {
    grid-template-columns: 1fr;
  }

  .secret-row {
    flex-direction: column;
  }
}
</style>
