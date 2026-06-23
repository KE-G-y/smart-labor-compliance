import { ref } from 'vue'

const errorMessage = (error, fallback) => {
  return error?.response?.data?.message || error?.response?.data?.detail || error?.message || fallback
}

export const useDialog = (t) => {
  const messageDialog = ref({
    open: false,
    title: '',
    message: '',
    variant: 'success',
    details: []
  })
  const confirmDialog = ref({
    open: false,
    title: '',
    message: '',
    confirmText: '',
    cancelText: '',
    variant: 'primary',
    details: [],
    loading: false,
    action: null,
    successMessage: '',
    errorFallback: ''
  })

  const showMessage = (message, options = {}) => {
    messageDialog.value = {
      open: true,
      title: options.title || (options.variant === 'danger' ? t('operationFailed') : t('operationTip')),
      message,
      variant: options.variant || 'success',
      details: options.details || []
    }
  }

  const closeMessage = () => {
    messageDialog.value.open = false
  }

  const openConfirm = (options) => {
    confirmDialog.value = {
      open: true,
      title: options.title || t('confirm'),
      message: options.message || '',
      confirmText: options.confirmText || t('confirm'),
      cancelText: options.cancelText || t('cancel'),
      variant: options.variant || 'primary',
      details: options.details || [],
      loading: false,
      action: options.action || null,
      successMessage: options.successMessage || '',
      errorFallback: options.errorFallback || t('operationFailed')
    }
  }

  const closeConfirm = () => {
    if (confirmDialog.value.loading) return
    confirmDialog.value.open = false
  }

  const runConfirm = async () => {
    const action = confirmDialog.value.action
    if (!action || confirmDialog.value.loading) return
    confirmDialog.value.loading = true
    try {
      await action()
      const successMessage = confirmDialog.value.successMessage
      confirmDialog.value.open = false
      if (successMessage) {
        showMessage(successMessage, {
          title: t('operationSuccess'),
          variant: 'success'
        })
      }
    } catch (error) {
      const fallback = confirmDialog.value.errorFallback
      confirmDialog.value.open = false
      showMessage(errorMessage(error, fallback), {
        title: t('operationFailed'),
        variant: 'danger'
      })
    } finally {
      confirmDialog.value.loading = false
    }
  }

  return {
    messageDialog,
    confirmDialog,
    showMessage,
    closeMessage,
    openConfirm,
    closeConfirm,
    runConfirm
  }
}
