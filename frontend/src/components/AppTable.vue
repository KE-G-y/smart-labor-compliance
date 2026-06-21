<template>
  <div class="app-table-wrap" :class="wrapClass">
    <table class="app-table" :class="tableClass" :style="tableStyle">
      <colgroup>
        <col
          v-for="column in resolvedColumns"
          :key="column.key"
          :style="{ width: column.width || undefined }"
        />
      </colgroup>
      <thead>
        <tr>
          <th
            v-for="column in resolvedColumns"
            :key="column.key"
            :class="cellClass(column, 'head')"
            :style="stickyStyle(column)"
          >
            <div class="app-table-head-cell">
              <slot :name="`head-${column.key}`" :column="column">
                <EllipsisText :value="column.label" />
              </slot>
            </div>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading">
          <td class="app-table-empty" :colspan="resolvedColumns.length">
            <div class="app-table-loading" role="status" aria-live="polite">
              <span class="app-table-spinner" aria-hidden="true"></span>
              <span>{{ loadingText }}</span>
            </div>
          </td>
        </tr>
        <tr v-else-if="!rows.length">
          <td class="app-table-empty" :colspan="resolvedColumns.length">{{ emptyText }}</td>
        </tr>
        <template v-else>
          <tr v-for="(row, index) in rows" :key="getRowKey(row, index)">
            <td
              v-for="column in resolvedColumns"
              :key="column.key"
              :class="cellClass(column, 'body')"
              :style="stickyStyle(column)"
            >
              <div class="app-table-cell" :class="alignClass(column.align)">
                <slot
                  :name="`cell-${column.key}`"
                  :row="row"
                  :value="getCellValue(row, column, index)"
                  :index="index"
                  :column="column"
                >
                  <EllipsisText :value="formatValue(getCellValue(row, column, index))" />
                </slot>
              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import EllipsisText from '@/components/EllipsisText.vue'

const props = defineProps({
  columns: {
    type: Array,
    required: true
  },
  rows: {
    type: Array,
    default: () => []
  },
  rowKey: {
    type: [String, Function],
    default: 'id'
  },
  emptyText: {
    type: String,
    default: ''
  },
  loading: {
    type: Boolean,
    default: false
  },
  loadingText: {
    type: String,
    default: ''
  },
  minWidth: {
    type: String,
    default: ''
  },
  dense: {
    type: Boolean,
    default: false
  },
  sequenceStart: {
    type: Number,
    default: 1
  }
})

const parseWidth = (width) => {
  if (typeof width === 'number') return width
  const match = String(width || '').match(/^(\d+(?:\.\d+)?)px$/)
  return match ? Number(match[1]) : 0
}

const resolvedColumns = computed(() => {
  let left = 0
  return props.columns.map((column) => {
    const resolved = { ...column, stickyLeft: column.sticky ? left : null }
    if (column.sticky) left += parseWidth(column.width)
    return resolved
  })
})
const wrapClass = computed(() => [
  props.dense ? 'app-table-wrap-dense' : ''
])
const tableClass = computed(() => [
  props.dense ? 'app-table-dense' : ''
])
const tableStyle = computed(() => props.minWidth ? { minWidth: props.minWidth } : null)

const getValue = (row, key) => String(key).split('.').reduce((value, part) => value?.[part], row)

const getCellValue = (row, column, index) => {
  if (typeof column.value === 'function') return column.value(row, index)
  if (column.key === 'sequence') return props.sequenceStart + index
  return getValue(row, column.key)
}

const getRowKey = (row, index) => {
  if (typeof props.rowKey === 'function') return props.rowKey(row, index)
  return getValue(row, props.rowKey) ?? index
}

const formatValue = (value) => {
  if (Array.isArray(value)) return value.join(' / ')
  if (value === null || value === undefined) return ''
  return value
}

const alignClass = (align = 'left') => `align-${align}`

const stickyStyle = (column) => column.sticky
  ? { left: `${column.stickyLeft}px` }
  : null

const cellClass = (column, area) => [
  column.cellClass,
  column.sticky ? 'is-sticky' : '',
  column.sticky ? `sticky-${area}` : ''
]
</script>
