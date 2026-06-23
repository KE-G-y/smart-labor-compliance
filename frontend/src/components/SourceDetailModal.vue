<template>
  <Teleport to="body">
    <div v-if="open && source" class="modal-mask source-detail-mask" @click.self="close">
      <div class="modal source-detail-modal" role="dialog" aria-modal="true" aria-labelledby="source-detail-title">
        <div class="section-title modal-header">
          <div>
            <h2 id="source-detail-title">{{ t('sourceDetail') }}</h2>
            <p class="page-desc">{{ t('sourceDetailHint') }}</p>
          </div>
          <button class="btn ghost" type="button" @click="close">×</button>
        </div>

        <div class="modal-body source-detail-body">
          <section class="source-detail-card">
            <span>{{ t('parentSourceDocument') }}</span>
            <strong>{{ source.title || '-' }}</strong>
          </section>

          <div class="source-detail-meta">
            <span class="tag">{{ sourceTypeText }}</span>
            <span v-if="source.document_id" class="tag">{{ t('documentId') }}：{{ source.document_id }}</span>
            <span v-if="source.local_file" class="tag">{{ t('sourceFile') }}：{{ source.local_file }}</span>
          </div>

          <section>
            <h3>{{ t('matchedChunks') }}</h3>
            <div class="source-chunk-list">
              <article v-for="(chunk, index) in chunks" :key="`${chunk.title || chunk.snippet || ''}-${index}`" class="source-chunk-card">
                <p class="preline">{{ chunk.content || chunk.snippet || t('noSnippet') }}</p>
              </article>
            </div>
          </section>
        </div>

        <div class="modal-actions modal-footer">
          <a v-if="validSourceUrl(source.url)" class="btn" :href="source.url" target="_blank" rel="noreferrer">
            {{ t('openExternalLink') }}
          </a>
          <button class="btn primary" type="button" @click="close">{{ t('close') }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from '@/i18n'

const props = defineProps({
  open: { type: Boolean, default: false },
  source: { type: Object, default: null }
})

const emit = defineEmits(['close'])
const { t } = useI18n()

const chunks = computed(() => {
  const sourceChunks = props.source?.chunks
  return Array.isArray(sourceChunks) && sourceChunks.length ? sourceChunks : props.source ? [props.source] : []
})

const sourceTypeText = computed(() => {
  const type = props.source?.source_type
  if (type === 'faq' || String(props.source?.title || '').startsWith('[FAQ]')) return t('faqSource')
  return t('documentSource')
})

const validSourceUrl = (url) => /^https?:\/\//i.test(url || '')

const close = () => emit('close')
</script>

<style scoped>
.source-detail-mask {
  z-index: 80;
}

.source-detail-modal {
  width: min(760px, calc(100vw - 32px));
}

.source-detail-body {
  display: grid;
  gap: 14px;
}

.source-detail-card {
  display: grid;
  gap: 6px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-soft);
}

.source-detail-card span {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.source-detail-card strong {
  overflow-wrap: anywhere;
}

.source-detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.source-detail-meta .tag {
  max-width: 100%;
  overflow-wrap: anywhere;
  white-space: normal;
}

.source-detail-body h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.source-chunk-list {
  display: grid;
  gap: 10px;
}

.source-chunk-card {
  display: grid;
  gap: 0;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
}

.source-chunk-card p {
  margin: 0;
  color: var(--text);
  line-height: 1.7;
}
</style>
