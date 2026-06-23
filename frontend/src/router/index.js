import { createRouter, createWebHistory } from 'vue-router'

const Home = () => import('@/views/Home.vue')
const History = () => import('@/views/History.vue')
const Docs = () => import('@/views/Docs.vue')
const AdminLogin = () => import('@/views/admin/Login.vue')
const AdminDashboard = () => import('@/views/admin/Dashboard.vue')
const AdminLogs = () => import('@/views/admin/Logs.vue')
const AdminFeedbacks = () => import('@/views/admin/Feedbacks.vue')
const AdminSources = () => import('@/views/admin/Sources.vue')
const AdminPackages = () => import('@/views/admin/Packages.vue')
const AdminAccounts = () => import('@/views/admin/Accounts.vue')
const AdminTenants = () => import('@/views/admin/Tenants.vue')
const AdminTests = () => import('@/views/admin/TestQuestions.vue')
const AdminSystemConfig = () => import('@/views/admin/SystemConfig.vue')
const AdminVectorVersions = () => import('@/views/admin/VectorVersions.vue')

const routes = [
  { path: '/', name: 'Home', component: Home },
  { path: '/history', name: 'History', component: History },
  { path: '/project-docs', name: 'Docs', component: Docs },
  { path: '/docs', redirect: '/project-docs' },
  { path: '/admin/login', name: 'AdminLogin', component: AdminLogin },
  { path: '/admin', name: 'AdminDashboard', component: AdminDashboard, meta: { requiresAuth: true } },
  { path: '/admin/tenants', name: 'AdminTenants', component: AdminTenants, meta: { requiresAuth: true, permissions: ['tenants'] } },
  { path: '/admin/logs', name: 'AdminLogs', component: AdminLogs, meta: { requiresAuth: true, permissions: ['logs'] } },
  { path: '/admin/feedbacks', name: 'AdminFeedbacks', component: AdminFeedbacks, meta: { requiresAuth: true, permissions: ['feedbacks'] } },
  { path: '/admin/sources', name: 'AdminSources', component: AdminSources, meta: { requiresAuth: true, permissions: ['sources'] } },
  { path: '/admin/vector-versions', name: 'AdminVectorVersions', component: AdminVectorVersions, meta: { requiresAuth: true, permissions: ['vector_versions'] } },
  { path: '/admin/packages', name: 'AdminPackages', component: AdminPackages, meta: { requiresAuth: true, permissions: ['packages'] } },
  { path: '/admin/tests', name: 'AdminTests', component: AdminTests, meta: { requiresAuth: true, permissions: ['test_questions'] } },
  { path: '/admin/accounts', name: 'AdminAccounts', component: AdminAccounts, meta: { requiresAuth: true, permissions: ['admins'] } },
  { path: '/admin/system-config', name: 'AdminSystemConfig', component: AdminSystemConfig, meta: { requiresAuth: true, permissions: ['system_config'] } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('admin_token')
  const permissions = JSON.parse(localStorage.getItem('admin_permissions') || '[]')

  if (to.meta.requiresAuth && !token) {
    next('/admin/login')
    return
  }

  if (to.name === 'AdminLogin' && token) {
    next('/admin')
    return
  }

  const required = to.meta.permissions || []
  if (required.length && !required.some(item => permissions.includes(item))) {
    next('/admin')
    return
  }

  next()
})

export default router
