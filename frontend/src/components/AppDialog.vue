<template>
  <Teleport to="body">
    <div v-if="open" class="modal-mask app-dialog-mask" @click.self="handleCancel">
      <div class="modal app-dialog" role="dialog" aria-modal="true" :aria-labelledby="titleId">
        <div class="app-dialog-header">
          <span :class="['app-dialog-icon', variant]">{{ iconText }}</span>
          <div>
            <h2 :id="titleId">{{ title }}</h2>
            <p v-if="message">{{ message }}</p>
          </div>
        </div>

        <div v-if="details.length" class="app-dialog-details">
          <div v-for="item in details" :key="item.label" class="app-dialog-detail">
            <span>{{ item.label }}</span>
            <strong>{{ item.value || '-' }}</strong>
          </div>
        </div>

        <div class="modal-actions app-dialog-actions">
          <button v-if="mode === 'confirm'" class="btn" type="button" :disabled="loading" @click="handleCancel">
            {{ cancelText }}
          </button>
          <button
            :class="['btn', actionButtonClass]"
            type="button"
            :disabled="loading"
            @click="handleConfirm"
          >
            {{ loading ? loadingText : primaryText }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  mode: { type: String, default: 'message' },
  variant: { type: String, default: 'success' },
  title: { type: String, default: '' },
  message: { type: String, default: '' },
  confirmText: { type: String, default: '' },
  cancelText: { type: String, default: '' },
  closeText: { type: String, default: '' },
  loadingText: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  details: { type: Array, default: () => [] },
  titleId: { type: String, default: 'app-dialog-title' }
})

const emit = defineEmits(['confirm', 'cancel'])

const iconText = computed(() => {
  if (props.variant === 'danger') return '!'
  if (props.variant === 'warning') return '!'
  return 'i'
})
const actionButtonClass = computed(() => props.variant === 'danger' ? 'danger' : 'primary')
const primaryText = computed(() => props.mode === 'confirm' ? props.confirmText : props.closeText)

const handleConfirm = () => emit('confirm')
const handleCancel = () => {
  if (!props.loading) emit('cancel')
}
</script>

<style scoped>
.app-dialog-mask {
  z-index: 90;
}

.app-dialog {
  width: min(560px, calc(100vw - 32px));
  padding: 22px;
  gap: 18px;
}

.app-dialog-header {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.app-dialog-header h2 {
  margin: 0 0 8px;
  font-size: 20px;
  line-height: 1.25;
}

.app-dialog-header p {
  margin: 0;
  color: var(--muted);
  line-height: 1.7;
}

.app-dialog-icon {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: rgba(37, 99, 235, 0.12);
  color: var(--primary);
  font-weight: 900;
}

.app-dialog-icon.danger {
  background: rgba(220, 38, 38, 0.12);
  color: var(--danger);
}

.app-dialog-icon.warning {
  background: rgba(183, 110, 0, 0.12);
  color: var(--warning);
}

.app-dialog-icon.success {
  background: rgba(22, 133, 95, 0.12);
  color: var(--success);
}

.app-dialog-details {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-soft);
}

.app-dialog-detail {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.app-dialog-detail span {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.app-dialog-detail strong {
  min-width: 0;
  overflow-wrap: anywhere;
}

.app-dialog-actions {
  padding-top: 4px;
}

@media (max-width: 560px) {
  .app-dialog {
    padding: 18px;
  }

  .app-dialog-header {
    grid-template-columns: 36px minmax(0, 1fr);
    gap: 12px;
  }

  .app-dialog-icon {
    width: 36px;
    height: 36px;
  }
}
</style>
