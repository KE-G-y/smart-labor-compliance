<template>
  <span
    ref="textRef"
    class="ellipsis-text"
    :class="{ 'is-link': asLink }"
    tabindex="0"
    @mouseenter="showTooltip"
    @mouseleave="hideTooltip"
    @focus="showTooltip"
    @blur="hideTooltip"
    @keydown.esc="hideTooltip"
  >
    <slot>{{ text }}</slot>
  </span>

  <Teleport to="body">
    <div
      v-if="visible && tooltipText"
      class="app-tooltip"
      data-app-tooltip="true"
      :style="tooltipStyle"
    >
      {{ tooltipText }}
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'

const props = defineProps({
  value: {
    type: [String, Number],
    default: ''
  },
  asLink: {
    type: Boolean,
    default: false
  },
  tooltipMaxLength: {
    type: Number,
    default: 220
  }
})

const textRef = ref(null)
const visible = ref(false)
const tooltipStyle = ref({})
const text = computed(() => props.value === null || props.value === undefined ? '' : String(props.value))
const normalizedTooltipMaxLength = computed(() => {
  const value = Number(props.tooltipMaxLength)
  return Number.isFinite(value) && value > 0 ? value : 220
})
const tooltipText = computed(() => {
  if (text.value.length <= normalizedTooltipMaxLength.value) return text.value
  return `${text.value.slice(0, normalizedTooltipMaxLength.value).trimEnd()}...`
})

const showTooltip = async () => {
  if (!text.value || !textRef.value) return
  const el = textRef.value
  if (el.scrollWidth <= el.clientWidth && el.scrollHeight <= el.clientHeight) return
  const rect = el.getBoundingClientRect()
  const viewportPadding = 12
  const gap = 8
  const maxWidth = Math.min(420, window.innerWidth - viewportPadding * 2)
  const preferredWidth = Math.min(maxWidth, Math.max(120, Math.min(tooltipText.value.length * 12 + 28, maxWidth)))

  tooltipStyle.value = {
    position: 'fixed',
    top: '0px',
    left: '0px',
    maxWidth: `${maxWidth}px`,
    width: `${preferredWidth}px`,
    zIndex: 1200,
    visibility: 'hidden'
  }
  visible.value = true
  await nextTick()

  const tooltip = document.querySelector('[data-app-tooltip="true"]')
  const tooltipRect = tooltip?.getBoundingClientRect()
  const tooltipWidth = tooltipRect?.width || preferredWidth
  const tooltipHeight = tooltipRect?.height || 44
  const openUpward = rect.bottom + gap + tooltipHeight > window.innerHeight - viewportPadding
  const top = openUpward
    ? rect.top - tooltipHeight - gap
    : rect.bottom + gap
  const left = rect.left + rect.width / 2 - tooltipWidth / 2

  tooltipStyle.value = {
    position: 'fixed',
    top: `${Math.max(viewportPadding, Math.min(top, window.innerHeight - tooltipHeight - viewportPadding))}px`,
    left: `${Math.max(viewportPadding, Math.min(left, window.innerWidth - tooltipWidth - viewportPadding))}px`,
    maxWidth: `${maxWidth}px`,
    width: `${preferredWidth}px`,
    zIndex: 1200
  }
}

const hideTooltip = () => {
  visible.value = false
  tooltipStyle.value = {}
}
</script>
