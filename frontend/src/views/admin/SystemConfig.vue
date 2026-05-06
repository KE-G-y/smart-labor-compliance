<template>
  <AdminLayout :title="t('systemConfigTitle')" :subtitle="t('systemConfigSubtitle')">
    <div class="system-config-container">
      <section class="panel">
        <div class="section-title">
          <h2>{{ t('difyConfig') }}</h2>
          <div class="toolbar">
            <button class="btn" :disabled="loading" @click="fetchConfig">{{ t('refresh') }}</button>
          </div>
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
            <input v-model="form.dify_api_key" class="input" type="password" :placeholder="form.dify_api_key_configured ? t('difyApiKeyConfiguredPlaceholder') : t('difyApiKeyPlaceholder')" />
            <div v-if="form.dify_api_key_configured" class="config-hint">
              <span class="tag success">{{ t('configured') }}</span>
              <span>{{ t('difyApiKeyConfiguredHint') }}</span>
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
            <input v-model="form.ragflow_api_key" class="input" type="password" :placeholder="form.ragflow_api_key_configured ? t('ragflowApiKeyConfiguredPlaceholder') : t('ragflowApiKeyPlaceholder')" />
            <div v-if="form.ragflow_api_key_configured" class="config-hint">
              <span class="tag success">{{ t('configured') }}</span>
              <span>{{ t('ragflowApiKeyConfiguredHint') }}</span>
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
  </AdminLayout>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getSystemConfig, updateSystemConfig } from '@/api'
import { useI18n } from '@/i18n'
import AdminLayout from './AdminLayout.vue'

const { t } = useI18n()
const loading = ref(false)
const saving = ref(false)
const form = ref({
  dify_base_url: '',
  dify_api_key: '',
  dify_api_key_configured: false,
  dify_timeout_seconds: 30,
  ragflow_base_url: '',
  ragflow_web_url: '',
  ragflow_api_key: '',
  ragflow_api_key_configured: false,
  ragflow_timeout_seconds: 10,
})

const fetchConfig = async () => {
  loading.value = true
  try {
    const res = await getSystemConfig()
    if (res.data) {
      form.value.dify_base_url = res.data.dify_base_url || ''
      form.value.dify_api_key = ''
      form.value.dify_api_key_configured = res.data.dify_api_key_configured || false
      form.value.dify_timeout_seconds = res.data.dify_timeout_seconds || 30
      form.value.ragflow_base_url = res.data.ragflow_base_url || ''
      form.value.ragflow_web_url = res.data.ragflow_web_url || ''
      form.value.ragflow_api_key = ''
      form.value.ragflow_api_key_configured = res.data.ragflow_api_key_configured || false
      form.value.ragflow_timeout_seconds = res.data.ragflow_timeout_seconds || 10
    }
  } finally {
    loading.value = false
  }
}

const saveConfig = async () => {
  saving.value = true
  try {
    const payload = {}
    if (form.value.dify_base_url !== undefined) payload.dify_base_url = form.value.dify_base_url
    if (form.value.dify_api_key) payload.dify_api_key = form.value.dify_api_key
    if (form.value.dify_timeout_seconds) payload.dify_timeout_seconds = form.value.dify_timeout_seconds
    if (form.value.ragflow_base_url !== undefined) payload.ragflow_base_url = form.value.ragflow_base_url
    if (form.value.ragflow_web_url !== undefined) payload.ragflow_web_url = form.value.ragflow_web_url
    if (form.value.ragflow_api_key) payload.ragflow_api_key = form.value.ragflow_api_key
    if (form.value.ragflow_timeout_seconds) payload.ragflow_timeout_seconds = form.value.ragflow_timeout_seconds
    await updateSystemConfig(payload)
    alert(t('saveSuccess') || '保存成功')
    fetchConfig()
  } catch (e) {
    alert(t('saveFailed') || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(fetchConfig)
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

.form-group .input::placeholder {
  color: var(--text-muted);
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
}
</style>