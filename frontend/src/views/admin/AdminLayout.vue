<template>
  <div class="admin-shell" :class="{ collapsed: sidebarCollapsed }">
    <aside class="admin-sidebar">
      <div class="sidebar-top">
        <button
          v-if="sidebarCollapsed"
          class="collapsed-brand-toggle"
          type="button"
          :title="t('expandSidebar')"
          @click="toggleSidebar"
        >
          <span class="brand-mark brand-mark-logo">S</span>
          <span class="brand-mark brand-mark-action">›</span>
        </button>
        <div v-else class="brand">
          <div class="brand-mark">S</div>
          <div class="brand-copy">
            <h1 class="brand-title">{{ t('platformShort') }}</h1>
            <div class="brand-subtitle">{{ roleLabel }}</div>
          </div>
        </div>
        <button
          v-if="!sidebarCollapsed"
          class="icon-btn collapse-btn"
          type="button"
          :title="sidebarCollapsed ? t('expandSidebar') : t('collapseSidebar')"
          @click="toggleSidebar"
        >
          {{ sidebarCollapsed ? '›' : '‹' }}
        </button>
      </div>
      <nav class="side-nav">
        <router-link
          v-for="item in visibleNavItems"
          :key="item.to"
          :to="item.to"
          :title="item.label"
        >
          <span class="side-icon">{{ item.icon }}</span>
          <span class="side-label">{{ item.label }}</span>
        </router-link>
      </nav>
    </aside>
    <main class="admin-main">
      <header class="admin-header">
        <div>
          <h1 class="brand-title">{{ title || t('adminDefaultTitle') }}</h1>
          <div class="page-desc">{{ subtitle }}</div>
        </div>
        <div class="toolbar">
          <AppSelect
            style="width: 120px"
            :model-value="locale"
            :options="localeOptions"
            @update:model-value="setLocale"
          />
          <button class="theme-toggle" type="button" :title="isDark ? t('switchToLight') : t('switchToDark')" @click="toggleTheme">
            <span class="theme-toggle-knob">{{ isDark ? 'D' : 'L' }}</span>
            <span>{{ isDark ? t('darkMode') : t('lightMode') }}</span>
          </button>
          <span class="tag">{{ tenantName || t('platform') }}</span>
          <div class="account-menu" ref="accountMenuRef">
            <button class="account-button" type="button" @click="accountMenuOpen = !accountMenuOpen">
              <span class="account-avatar">{{ usernameInitial }}</span>
              <span class="account-name">{{ username }}</span>
              <span class="account-caret">⌄</span>
            </button>
            <div v-if="accountMenuOpen" class="account-dropdown">
              <div class="account-meta">
                <strong>{{ username }}</strong>
                <span>{{ roleLabel }}</span>
                <span>{{ tenantName || t('platformAccount') }}</span>
              </div>
              <button type="button" @click="logout">{{ t('logout') }}</button>
            </div>
          </div>
        </div>
      </header>
      <div class="admin-scroll">
        <div class="container">
        <slot />
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from '@/i18n'
import { useTheme } from '@/theme'
import AppSelect from '@/components/AppSelect.vue'

defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' }
})

const router = useRouter()
const { t, locale, setLocale, roleLabel: translateRoleLabel } = useI18n()
const { isDark, toggleTheme, applyTheme } = useTheme()
const username = localStorage.getItem('admin_username') || 'admin'
const role = localStorage.getItem('admin_role') || ''
const roleLabel = computed(() => translateRoleLabel(role, localStorage.getItem('admin_role_label') || t('adminRoleDefault')))
const tenantName = localStorage.getItem('admin_tenant_name') || ''
const permissions = JSON.parse(localStorage.getItem('admin_permissions') || '[]')
const accountMenuRef = ref(null)
const accountMenuOpen = ref(false)
const sidebarCollapsed = ref(localStorage.getItem('admin_sidebar_collapsed') === 'true')
const usernameInitial = computed(() => (username || 'A').slice(0, 1).toUpperCase())
const localeOptions = [
  { value: 'zh-CN', label: '中文' },
  { value: 'en', label: 'English' }
]

const can = (permission) => permissions.includes(permission)
const navIcon = (zh, en) => locale.value === 'en' ? en : zh
const navItems = computed(() => [
  { to: '/admin', label: t('dashboard'), permission: null, icon: navIcon('概', 'D') },
  { to: '/admin/tenants', label: t('tenants'), permission: 'tenants', icon: navIcon('租', 'Tn') },
  { to: '/admin/system-config', label: t('systemConfigTitle'), permission: 'system_config', icon: navIcon('设', 'Cfg') },
  { to: '/admin/logs', label: t('logs'), permission: 'logs', icon: navIcon('问', 'Log') },
  { to: '/admin/feedbacks', label: t('feedbacks'), permission: 'feedbacks', icon: navIcon('馈', 'Fb') },
  { to: '/admin/faqs', label: t('faqs'), permission: 'faqs', icon: navIcon('F', 'FAQ') },
  { to: '/admin/sources', label: t('sourceManage'), permission: 'sources', icon: navIcon('源', 'Src') },
  { to: '/admin/packages', label: t('packages'), permission: 'packages', icon: navIcon('包', 'Pkg') },
  { to: '/admin/tests', label: t('tests'), permission: 'test_questions', icon: navIcon('测', 'Tst') },
  { to: '/admin/accounts', label: t('accounts'), permission: 'admins', icon: navIcon('账', 'Acc') }
])
const visibleNavItems = computed(() => navItems.value.filter(item => !item.permission || can(item.permission)))

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
  localStorage.setItem('admin_sidebar_collapsed', String(sidebarCollapsed.value))
}

const handleDocumentClick = (event) => {
  if (accountMenuRef.value && !accountMenuRef.value.contains(event.target)) {
    accountMenuOpen.value = false
  }
}

const logout = () => {
  ;['admin_token', 'admin_id', 'admin_username', 'admin_role', 'admin_role_label', 'admin_permissions', 'admin_tenant_name', 'admin_tenant_id'].forEach(key => {
    localStorage.removeItem(key)
  })
  router.push('/admin/login')
}

onMounted(() => {
  applyTheme()
  document.addEventListener('click', handleDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
})
</script>
