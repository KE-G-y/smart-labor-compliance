import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const apiSource = readFileSync(resolve(root, 'src/api/index.js'), 'utf8')
const routerSource = readFileSync(resolve(root, 'src/router/index.js'), 'utf8')

const requiredApiContracts = [
  ['chat', "api.post('/chat'"],
  ['chatWithFile', "api.post('/chat-with-file'"],
  ['stopChatGeneration', "api.post('/chat/stop'"],
  ['getHistory', "api.get('/history'"],
  ['exportHistory', "exportCsv('/history/export'"],
  ['clearHistory', "api.delete('/history'"],
  ['submitFeedback', "api.post('/feedback'"],
  ['getRecommendedQuestions', "api.get('/recommended-questions'"],
  ['getTenantPublic', "api.get('/tenant-public'"],
  ['adminLogin', "api.post('/admin/login'"],
  ['verifyToken', "api.get('/admin/verify-token'"],
  ['getStatistics', "api.get('/admin/statistics'"],
  ['getServiceStatus', "api.get('/admin/service-status'"],
  ['getTenants', "api.get('/admin/tenants'"],
  ['getLogs', "api.get('/admin/logs'"],
  ['getFeedbacks', "api.get('/admin/feedbacks'"],
  ['getFaqs', "api.get('/admin/faqs'"],
  ['importFaqs', "uploadCsv('/admin/faqs/import'"],
  ['exportFaqs', "exportCsv('/admin/faqs/export'"],
  ['batchFaqs', "api.post('/admin/faqs/batch'"],
  ['getSources', "api.get('/admin/sources'"],
  ['uploadSourceFile', "api.post('/admin/sources/upload'"],
  ['importSources', "uploadCsv('/admin/sources/import'"],
  ['exportSources', "exportCsv('/admin/sources/export'"],
  ['batchSources', "api.post('/admin/sources/batch'"],
  ['getKnowledgePackages', "api.get('/admin/knowledge-packages'"],
  ['updatePackageStatus', '/admin/knowledge-packages/${id}/status'],
  ['getTestQuestions', "api.get('/admin/test-questions'"],
  ['getRoles', "api.get('/admin/roles'"],
  ['getAdmins', "api.get('/admin/admins'"],
  ['getSystemConfig', "api.get('/admin/system-config'"],
  ['updateSystemConfig', "api.put('/admin/system-config'"],
]

const requiredRoutes = [
  "path: '/'",
  "path: '/history'",
  "path: '/admin/login'",
  "path: '/admin'",
  "path: '/admin/tenants'",
  "path: '/admin/logs'",
  "path: '/admin/feedbacks'",
  "path: '/admin/faqs'",
  "path: '/admin/sources'",
  "path: '/admin/packages'",
  "path: '/admin/tests'",
  "path: '/admin/accounts'",
  "path: '/admin/system-config'"
]

const failures = []

for (const [name, needle] of requiredApiContracts) {
  if (!apiSource.includes(needle)) {
    failures.push(`Missing API contract: ${name} -> ${needle}`)
  }
}

for (const needle of requiredRoutes) {
  if (!routerSource.includes(needle)) {
    failures.push(`Missing route contract: ${needle}`)
  }
}

if (!apiSource.includes("config.headers['X-Tenant-Code'] = getTenantCode()")) {
  failures.push('Missing tenant header request interceptor')
}

if (!apiSource.includes('localStorage.removeItem') || !apiSource.includes("error.response?.status === 401")) {
  failures.push('Missing 401 authentication cleanup interceptor')
}

if (failures.length) {
  console.error(failures.join('\n'))
  process.exit(1)
}

console.log(`Contract check passed: ${requiredApiContracts.length} API wrappers, ${requiredRoutes.length} routes.`)

