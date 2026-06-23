<template>
  <div class="app-page">
    <AppTopbar :tenant="tenant" />

    <main class="split-workspace">
      <section class="split-workspace-inner">
        <div class="split-pane split-pane-left">
          <div class="split-pane-content">
            <div class="panel">
          <div class="section-title">
            <div>
              <h1>{{ t('chat') }}</h1>
              <p class="page-desc">{{ t('homeIntro') }}</p>
            </div>
            <span class="tag">{{ t('tenant') }}: {{ tenantCode }}</span>
          </div>

          <textarea
            v-model="question"
            class="textarea"
            :placeholder="t('askPlaceholder')"
            :disabled="loading"
            @keydown.ctrl.enter="submitQuestion"
          />
          <div class="file-strip">
            <input ref="fileInput" type="file" class="sr-only" @change="handleFileChange" />
            <button class="btn" type="button" :disabled="loading" @click="openFilePicker">
              {{ t('attachFile') }}
            </button>
            <div v-if="attachedFile" class="file-pill">
              <span>{{ attachedFile.name }}</span>
              <button type="button" :aria-label="t('removeFile')" :disabled="loading" @click="removeFile">×</button>
            </div>
            <span v-else class="muted">{{ t('chatFileHint') }}</span>
          </div>
          <div class="context-panel">
            <button
              class="context-toggle"
              type="button"
              :aria-expanded="contextOpen"
              :disabled="loading"
              @click="contextOpen = !contextOpen"
            >
              <span>{{ t('contextPanelTitle') }}</span>
              <span class="context-toggle-state">{{ contextOpen ? t('contextPanelClose') : t('contextPanelOpen') }}</span>
            </button>
            <div v-show="contextOpen" class="context-grid">
              <label class="context-field">
                <span>{{ t('userGoal') }}</span>
                <AppSelect v-model="userGoal" :options="userGoalOptions" :disabled="loading" />
              </label>
              <label class="context-field">
                <span>{{ t('urgencyLevel') }}</span>
                <AppSelect v-model="urgencyLevel" :options="urgencyOptions" :disabled="loading" />
              </label>
              <label class="context-field">
                <span>{{ t('outputFormat') }}</span>
                <AppSelect v-model="outputFormat" :options="outputFormatOptions" :disabled="loading" />
              </label>
              <label class="context-field">
                <span>{{ t('answerStyle') }}</span>
                <input v-model="answerStyle" class="input" :placeholder="t('answerStylePlaceholder')" :disabled="loading" />
              </label>
              <label class="context-field context-field-wide">
                <span>{{ t('knownFacts') }}</span>
                <textarea v-model="knownFacts" class="textarea context-textarea" :placeholder="t('knownFactsPlaceholder')" :disabled="loading" />
              </label>
              <label class="context-field context-field-wide">
                <span>{{ t('verificationFocus') }}</span>
                <textarea v-model="verificationFocus" class="textarea context-textarea" :placeholder="t('verificationFocusPlaceholder')" :disabled="loading" />
              </label>
            </div>
          </div>
          <div class="split-actions" style="margin-top: 12px">
            <div class="toolbar">
              <input v-model="tenantCode" class="input" style="width: 150px" :placeholder="t('tenantCode')" :disabled="loading" @change="persistTenant" />
              <AppSelect class="context-select role-select" v-model="userRole" :options="userRoleOptions" :disabled="loading" />
              <AppSelect class="context-select region-select" v-model="province" :options="provinceOptions" :disabled="loading" @change="handleProvinceChange" />
              <AppSelect class="context-select region-select" v-model="city" :options="cityOptions" :disabled="loading" />
              <span class="muted">Ctrl + Enter</span>
            </div>
            <button v-if="loading" class="btn danger" type="button" @click="stopGeneration">
              {{ t('stopGenerating') }}
            </button>
            <button v-else class="btn primary" :disabled="!question.trim()" @click="submitQuestion">
              {{ t('ask') }}
            </button>
          </div>

          <div v-if="loading" class="answer-loading" role="status" aria-live="polite">
            <div class="loading-orbit" aria-hidden="true">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <div class="loading-copy">
              <div class="loading-title">
                <span>{{ t('answerLoadingTitle') }}</span>
                <i aria-hidden="true"></i>
              </div>
              <p>{{ t('answerLoadingDesc') }}</p>
              <div class="loading-steps" aria-hidden="true">
                <span>{{ t('answerLoadingStepReview') }}</span>
                <span>{{ t('answerLoadingStepRetrieve') }}</span>
                <span>{{ t('answerLoadingStepCompose') }}</span>
              </div>
            </div>
            <div class="loading-skeleton" aria-hidden="true">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>

          <div v-if="answer" class="answer-block">
            <div class="section-title">
              <h2>{{ t('answer') }}</h2>
              <div class="toolbar">
                <span :class="['tag', riskClass]">{{ t('risk') }}: {{ riskText }}</span>
                <span class="tag">{{ t('provider') }}: {{ provider }}</span>
                <span v-if="responseTime !== null" class="tag">{{ t('responseTime') }}: {{ responseTimeText }}</span>
              </div>
            </div>
            <div class="answer-text markdown-content" v-html="renderedAnswer"></div>

            <div v-if="answerEvaluation" class="subsection quality-section">
              <h3>{{ t('answerQuality') }}</h3>
              <div class="quality-summary">
                <span :class="['tag', qualityClass(answerEvaluation.status)]">
                  {{ t('qualityScore') }}：{{ answerEvaluation.score }} / {{ answerEvaluation.grade }}
                </span>
                <span>{{ qualityStatusText(answerEvaluation.status) }}</span>
              </div>
              <div v-if="answerEvaluation.recommendations?.length" class="quality-list">
                <span v-for="item in answerEvaluation.recommendations.slice(0, 3)" :key="item">{{ item }}</span>
              </div>
            </div>

            <div v-if="sources.length" class="subsection">
              <h3>{{ t('sources') }}</h3>
              <div class="source-list">
                <a v-for="source in sources" :key="source.title" :href="source.url || '#'" target="_blank" rel="noreferrer" class="source-item">
                  <strong>{{ source.title }}</strong>
                  <span>{{ source.snippet }}</span>
                </a>
              </div>
            </div>

            <div v-if="tasks.length" class="subsection">
              <h3>{{ t('tasks') }}</h3>
              <div v-for="task in tasks" :key="task.title" class="task-card">
                <strong>{{ task.title }}</strong>
                <ol>
                  <li v-for="step in task.steps" :key="step">{{ step }}</li>
                </ol>
              </div>
            </div>

            <div v-if="suggestions.length" class="subsection">
              <h3>{{ t('followUp') }}</h3>
              <div class="toolbar">
              <button v-for="item in suggestions" :key="item" class="chip" :disabled="loading" @click="fillQuestion(item)">{{ item }}</button>
              </div>
            </div>

            <div class="feedback-row">
              <span>{{ t('feedback') }}</span>
              <button class="btn" :disabled="feedbackSubmitted" @click="sendFeedback(true)">{{ t('helpful') }}</button>
              <button class="btn danger" :disabled="feedbackSubmitted" @click="showRemark = true">{{ t('notHelpful') }}</button>
            </div>
            <div v-if="showRemark" class="feedback-form">
              <textarea v-model="feedbackRemark" class="textarea" :placeholder="t('feedbackPlaceholder')" />
              <button class="btn primary" @click="sendFeedback(false)">{{ t('submitFeedback') }}</button>
            </div>
          </div>
        </div>
          </div>
        </div>

        <aside class="split-pane split-pane-right">
          <div class="split-pane-content">
            <div class="card">
            <div class="section-title">
              <h2>{{ t('recommendedQuestions') }}</h2>
              <button class="btn" :disabled="loading" @click="loadRecommended">{{ t('refresh') }}</button>
            </div>
            <div class="recommend-list">
              <button v-for="item in recommended" :key="item.id || item.question" class="recommend-item" :disabled="loading" @click="fillQuestion(item.question)">
                <strong>{{ item.question }}</strong>
                <span>{{ item.category }} · {{ riskLabel(item.risk_level) }}</span>
              </button>
            </div>
          </div>
            <div class="card">
            <h2>{{ t('dataSecurity') }}</h2>
            <p class="page-desc">{{ t('dataSecurityText') }}</p>
          </div>
          </div>
        </aside>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { chat, chatWithFile, getRecommendedQuestions, getTenantCode, getTenantPublic, setTenantCode, stopChatGeneration, submitFeedback } from '@/api'
import { useI18n } from '@/i18n'
import { renderMarkdown } from '@/utils/markdown'
import { displayedRiskLevel as getDisplayedRiskLevel, normalizeRiskLevel, riskFromAnswer } from '@/utils/risk'
import AppSelect from '@/components/AppSelect.vue'
import AppTopbar from '@/components/AppTopbar.vue'

const { t, locale, riskLabel } = useI18n()
const tenantCode = ref(getTenantCode())
const tenant = ref({})
const question = ref('')
const userRole = ref(localStorage.getItem('chat_user_role') || 'employee')
const province = ref(localStorage.getItem('chat_province') || '陕西省')
const city = ref(localStorage.getItem('chat_city') || '西安市')
const answerStyle = ref(localStorage.getItem('chat_answer_style') || '')
const userGoal = ref(localStorage.getItem('chat_user_goal') || '政策咨询')
const urgencyLevel = ref(localStorage.getItem('chat_urgency_level') || '常规咨询')
const outputFormat = ref(localStorage.getItem('chat_output_format') || '结论 + 依据 + 行动清单')
const knownFacts = ref(localStorage.getItem('chat_known_facts') || '')
const verificationFocus = ref(localStorage.getItem('chat_verification_focus') || '')
const answer = ref('')
const sources = ref([])
const tasks = ref([])
const suggestions = ref([])
const answerEvaluation = ref(null)
const responseTime = ref(null)
const provider = ref('')
const riskLevel = ref('medium')
const questionId = ref(null)
const recommended = ref([])
const loading = ref(false)
const feedbackSubmitted = ref(false)
const showRemark = ref(false)
const feedbackRemark = ref('')
const answeredQuestion = ref('')
const attachedFile = ref(null)
const fileInput = ref(null)
const activeGenerationId = ref('')
const requestController = ref(null)
const stopping = ref(false)
const contextOpen = ref(localStorage.getItem('chat_context_open') === 'true')
const LAST_CHAT_KEY = 'chat_last_state'

const displayedRiskLevel = computed(() => getDisplayedRiskLevel({ answer: answer.value, risk_level: riskLevel.value }))
const renderedAnswer = computed(() => renderMarkdown(answer.value))
const riskText = computed(() => riskLabel(displayedRiskLevel.value))
const riskClass = computed(() => displayedRiskLevel.value === 'high' ? 'danger' : displayedRiskLevel.value === 'medium' ? 'warning' : 'success')
const responseTimeText = computed(() => {
  if (responseTime.value === null) return '-'
  if (responseTime.value < 1000) return `${responseTime.value}ms`
  const seconds = responseTime.value / 1000
  return `${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds)}s`
})
const userRoleOptions = computed(() => [
  { value: 'enterprise_hr', label: t('roleEnterpriseHr') },
  { value: 'administrator_staff', label: t('roleAdministrativeStaff') },
  { value: 'legal_staff', label: t('roleLegalStaff') },
  { value: 'employee', label: t('roleEmployee') },
  { value: 'admin_user', label: t('roleAdminUser') }
])
const userGoalOptions = computed(() => [
  { value: '政策咨询', label: t('goalPolicyQuery') },
  { value: '风险评估', label: t('goalRiskAssessment') },
  { value: '材料核验', label: t('goalDocumentReview') },
  { value: '处理方案', label: t('goalActionPlan') }
])
const urgencyOptions = computed(() => [
  { value: '常规咨询', label: t('urgencyNormal') },
  { value: '今天需要处理', label: t('urgencyToday') },
  { value: '高风险待复核', label: t('urgencyHighRisk') },
  { value: '对外回复前确认', label: t('urgencyBeforeReply') }
])
const outputFormatOptions = computed(() => [
  { value: '结论 + 依据 + 行动清单', label: t('formatConclusionAction') },
  { value: '表格 + 风险等级 + 待核验项', label: t('formatTableRisk') },
  { value: '给员工的简明回复', label: t('formatEmployeeReply') },
  { value: '给 HR/法务的复核清单', label: t('formatReviewChecklist') }
])
const regionTree = {
  '北京市': ['北京市'],
  '天津市': ['天津市'],
  '河北省': ['石家庄市', '唐山市', '保定市', '邯郸市'],
  '山西省': ['太原市', '大同市', '临汾市', '运城市'],
  '内蒙古自治区': ['呼和浩特市', '包头市', '鄂尔多斯市'],
  '辽宁省': ['沈阳市', '大连市', '鞍山市'],
  '吉林省': ['长春市', '吉林市'],
  '黑龙江省': ['哈尔滨市', '齐齐哈尔市'],
  '上海市': ['上海市'],
  '江苏省': ['南京市', '苏州市', '无锡市', '常州市'],
  '浙江省': ['杭州市', '宁波市', '温州市', '绍兴市'],
  '安徽省': ['合肥市', '芜湖市', '蚌埠市'],
  '福建省': ['福州市', '厦门市', '泉州市'],
  '江西省': ['南昌市', '九江市', '赣州市'],
  '山东省': ['济南市', '青岛市', '烟台市', '潍坊市'],
  '河南省': ['郑州市', '洛阳市', '开封市'],
  '湖北省': ['武汉市', '宜昌市', '襄阳市'],
  '湖南省': ['长沙市', '株洲市', '岳阳市'],
  '广东省': ['广州市', '深圳市', '佛山市', '东莞市'],
  '广西壮族自治区': ['南宁市', '柳州市', '桂林市'],
  '海南省': ['海口市', '三亚市'],
  '重庆市': ['重庆市'],
  '四川省': ['成都市', '绵阳市', '德阳市'],
  '贵州省': ['贵阳市', '遵义市'],
  '云南省': ['昆明市', '曲靖市'],
  '西藏自治区': ['拉萨市'],
  '陕西省': ['西安市', '咸阳市', '宝鸡市', '渭南市', '延安市', '汉中市', '榆林市'],
  '甘肃省': ['兰州市', '天水市'],
  '青海省': ['西宁市'],
  '宁夏回族自治区': ['银川市'],
  '新疆维吾尔自治区': ['乌鲁木齐市']
}
const provinceOptions = computed(() => Object.keys(regionTree))
const cityOptions = computed(() => regionTree[province.value] || [])

const clearAnswer = () => {
  answer.value = ''
  sources.value = []
  tasks.value = []
  suggestions.value = []
  answerEvaluation.value = null
  responseTime.value = null
  provider.value = ''
  riskLevel.value = 'medium'
  questionId.value = null
  feedbackSubmitted.value = false
  showRemark.value = false
  feedbackRemark.value = ''
}

const saveLastChat = () => {
  if (!answer.value) return
  localStorage.setItem(LAST_CHAT_KEY, JSON.stringify({
    question: answeredQuestion.value || question.value,
    answer: answer.value,
    sources: sources.value,
    tasks: tasks.value,
    suggestions: suggestions.value,
    evaluation: answerEvaluation.value,
    responseTime: responseTime.value,
    provider: provider.value,
    riskLevel: displayedRiskLevel.value,
    questionId: questionId.value
  }))
}

const restoreLastChat = () => {
  try {
    const raw = localStorage.getItem(LAST_CHAT_KEY)
    if (!raw) return
    const data = JSON.parse(raw)
    question.value = data.question || ''
    answeredQuestion.value = data.question || ''
    answer.value = data.answer || ''
    sources.value = data.sources || []
    tasks.value = data.tasks || []
    suggestions.value = data.suggestions || []
    answerEvaluation.value = data.evaluation || null
    responseTime.value = normalizeResponseTime(data.responseTime ?? data.response_time ?? data.evaluation?.metrics?.response_time_ms)
    provider.value = data.provider || ''
    riskLevel.value = riskFromAnswer(data.answer) || normalizeRiskLevel(data.riskLevel) || 'medium'
    questionId.value = data.questionId || null
  } catch (error) {
    localStorage.removeItem(LAST_CHAT_KEY)
  }
}

const persistTenant = () => {
  setTenantCode(tenantCode.value)
  loadTenant()
  loadRecommended()
}

const handleProvinceChange = (value) => {
  const cities = regionTree[value] || []
  city.value = cities[0] || ''
}

const loadTenant = async () => {
  try {
    const res = await getTenantPublic()
    tenant.value = res.data || {}
  } catch (error) {
    tenant.value = { name: t('defaultTenantName'), region: t('defaultRegion') }
  }
}

const loadRecommended = async () => {
  try {
    const res = await getRecommendedQuestions()
    recommended.value = res.data || []
  } catch (error) {
    recommended.value = [
      { question: '陕西产假多少天？', category: '假期', risk_level: 'medium' },
      { question: '试用期工资可以低于最低工资吗？', category: '工资', risk_level: 'high' }
    ]
  }
}

const fillQuestion = (value) => {
  if (loading.value) return
  question.value = value
}

const openFilePicker = () => {
  fileInput.value?.click()
}

const handleFileChange = (event) => {
  attachedFile.value = event.target.files?.[0] || null
}

const removeFile = () => {
  attachedFile.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

const setContextStorage = (key, value) => {
  if (value) localStorage.setItem(key, value)
  else localStorage.removeItem(key)
}

const normalizeResponseTime = (value) => {
  if (value === null || value === undefined || value === '') return null
  const numeric = Number(value)
  return Number.isFinite(numeric) && numeric >= 0 ? Math.round(numeric) : null
}

const submitQuestion = async () => {
  if (!question.value.trim() || loading.value) return
  const submittedQuestion = question.value
  const generationId = `${Date.now()}-${Math.random().toString(36).slice(2)}`
  clearAnswer()
  answeredQuestion.value = ''
  activeGenerationId.value = generationId
  requestController.value = new AbortController()
  stopping.value = false
  loading.value = true
  try {
    const payload = {
      question: question.value,
      generation_id: generationId,
      user_id: localStorage.getItem('user_id') || 'demo-user',
      tenant_code: tenantCode.value,
      language: locale.value,
      user_role: userRole.value,
      province: province.value,
      city: city.value,
      answer_style: answerStyle.value,
      user_goal: userGoal.value,
      urgency_level: urgencyLevel.value,
      output_format: outputFormat.value,
      known_facts: knownFacts.value,
      verification_focus: verificationFocus.value
    }
    const res = attachedFile.value
      ? await chatWithFile(payload, attachedFile.value, { signal: requestController.value.signal })
      : await chat(payload, { signal: requestController.value.signal })
    const data = res.data || {}
    answer.value = data.answer || ''
    sources.value = data.sources || []
    tasks.value = data.related_tasks || []
    suggestions.value = data.suggestions || []
    answerEvaluation.value = data.evaluation || null
    responseTime.value = normalizeResponseTime(data.response_time ?? data.evaluation?.metrics?.response_time_ms)
    provider.value = data.provider || 'kb_no_match'
    fallbackReason.value = data.fallback_reason || ''
    riskLevel.value = riskFromAnswer(data.answer) || normalizeRiskLevel(data.risk_level) || 'medium'
    questionId.value = data.question_id
    answeredQuestion.value = submittedQuestion
    saveLastChat()
  } catch (error) {
    answer.value = stopping.value || error.name === 'CanceledError' || error.code === 'ERR_CANCELED'
      ? t('generationStopped')
      : error.code === 'ECONNABORTED'
        ? t('requestTimeout')
        : error.response?.data?.message || t('systemError')
    sources.value = []
    tasks.value = []
    answerEvaluation.value = null
    responseTime.value = null
    answeredQuestion.value = submittedQuestion
  } finally {
    loading.value = false
    activeGenerationId.value = ''
    requestController.value = null
    stopping.value = false
  }
}

const stopGeneration = async () => {
  if (!loading.value) return
  stopping.value = true
  const generationId = activeGenerationId.value
  requestController.value?.abort()
  loading.value = false
  answer.value = t('generationStopped')
  sources.value = []
  tasks.value = []
  suggestions.value = []
  answerEvaluation.value = null
  responseTime.value = null
  provider.value = ''
  if (generationId) {
    try {
      await stopChatGeneration({
        generation_id: generationId,
        tenant_code: tenantCode.value,
        user_id: localStorage.getItem('user_id') || 'demo-user'
      })
    } catch (error) {
      // The local request has already been cancelled; backend stop is best effort.
    }
  }
}

const sendFeedback = async (isHelpful) => {
  if (!questionId.value || feedbackSubmitted.value) return
  await submitFeedback({
    tenant_code: tenantCode.value,
    question_id: questionId.value,
    user_id: localStorage.getItem('user_id') || 'demo-user',
    is_helpful: isHelpful,
    remark: isHelpful ? '' : feedbackRemark.value
  })
  feedbackSubmitted.value = true
  showRemark.value = false
}

const qualityClass = (status) => status === 'pass' ? 'success' : status === 'warning' ? 'warning' : 'danger'
const qualityStatusText = (status) => {
  if (status === 'pass') return t('qualityPass')
  if (status === 'warning') return t('qualityWarning')
  return t('qualityFail')
}

onMounted(() => {
  restoreLastChat()
  loadTenant()
  loadRecommended()
})

watch(question, (value) => {
  if (loading.value || !answeredQuestion.value) return
  if (value !== answeredQuestion.value) {
    clearAnswer()
    answeredQuestion.value = ''
  }
})

watch(userRole, (value) => {
  localStorage.setItem('chat_user_role', value)
})

watch(province, (value) => {
  localStorage.setItem('chat_province', value)
})

watch(city, (value) => {
  localStorage.setItem('chat_city', value)
})

watch(answerStyle, (value) => {
  setContextStorage('chat_answer_style', value)
})

watch(userGoal, (value) => {
  setContextStorage('chat_user_goal', value)
})

watch(urgencyLevel, (value) => {
  setContextStorage('chat_urgency_level', value)
})

watch(outputFormat, (value) => {
  setContextStorage('chat_output_format', value)
})

watch(knownFacts, (value) => {
  setContextStorage('chat_known_facts', value)
})

watch(verificationFocus, (value) => {
  setContextStorage('chat_verification_focus', value)
})

watch(contextOpen, (value) => {
  localStorage.setItem('chat_context_open', value ? 'true' : 'false')
})
</script>

<style scoped>
.context-select {
  width: 132px;
}

.role-select {
  width: 150px;
}

.region-select {
  width: 124px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.file-strip {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.file-pill {
  min-height: 34px;
  max-width: min(100%, 420px);
  padding: 6px 8px 6px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-soft);
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.file-pill span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-pill button {
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
}

.file-pill button:hover {
  color: var(--danger);
  background: rgba(201, 54, 54, 0.08);
}

.engine-alert {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin: 0 0 14px;
  padding: 10px 12px;
  border: 1px solid rgba(201, 54, 54, 0.24);
  border-radius: 8px;
  background: rgba(201, 54, 54, 0.08);
  color: var(--danger);
  font-size: 13px;
  line-height: 1.5;
}

.engine-alert strong {
  color: var(--danger);
}

.context-panel {
  margin-top: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-soft);
  overflow: hidden;
}

.context-toggle {
  width: 100%;
  min-height: 40px;
  border: 0;
  padding: 10px 12px;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-weight: 800;
}

.context-toggle:hover {
  color: var(--primary);
}

.context-toggle:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.context-toggle-state {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.context-grid {
  padding: 0 12px 12px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.context-field {
  min-width: 0;
  display: grid;
  gap: 6px;
}

.context-field span {
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}

.context-field-wide {
  grid-column: 1 / -1;
}

.context-textarea {
  min-height: 72px;
}

.answer-block {
  margin-top: 18px;
  border-top: 1px solid var(--line);
  padding-top: 18px;
}

.answer-loading {
  position: relative;
  overflow: hidden;
  margin-top: 18px;
  min-height: 132px;
  padding: 18px;
  border: 1px solid rgba(23, 105, 224, 0.18);
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgba(23, 105, 224, 0.08), rgba(22, 133, 95, 0.06)),
    var(--surface-soft);
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 16px;
  align-items: center;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.48);
}

.answer-loading::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(110deg, transparent 0%, rgba(255, 255, 255, 0.48) 42%, transparent 72%);
  transform: translateX(-100%);
  animation: loading-sheen 2.4s ease-in-out infinite;
}

.loading-orbit,
.loading-copy,
.loading-skeleton {
  position: relative;
  z-index: 1;
}

.loading-orbit {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  background: rgba(23, 105, 224, 0.08);
}

.loading-orbit::before {
  content: "";
  position: absolute;
  inset: 5px;
  border-radius: inherit;
  border: 2px solid rgba(23, 105, 224, 0.18);
  border-top-color: var(--primary);
  animation: loading-spin 1.05s linear infinite;
}

.loading-orbit span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary);
  animation: loading-dot 1.1s ease-in-out infinite;
}

.loading-orbit span:nth-child(2) {
  animation-delay: 0.16s;
}

.loading-orbit span:nth-child(3) {
  animation-delay: 0.32s;
}

.loading-copy {
  min-width: 0;
  display: grid;
  gap: 8px;
}

.loading-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 800;
}

.loading-title i {
  width: 34px;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--primary), rgba(22, 133, 95, 0.3));
  animation: loading-pulse 1.2s ease-in-out infinite;
}

.loading-copy p {
  margin: 0;
  color: var(--muted);
  font-weight: 600;
}

.loading-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.loading-steps span {
  min-height: 24px;
  padding: 3px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--primary);
  font-size: 12px;
  font-weight: 800;
}

.loading-skeleton {
  grid-column: 1 / -1;
  display: grid;
  gap: 8px;
}

.loading-skeleton span {
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(23, 105, 224, 0.1), rgba(23, 105, 224, 0.2), rgba(23, 105, 224, 0.1));
  background-size: 240% 100%;
  animation: loading-skeleton 1.5s ease-in-out infinite;
}

.loading-skeleton span:nth-child(2) {
  width: 82%;
  animation-delay: 0.1s;
}

.loading-skeleton span:nth-child(3) {
  width: 58%;
  animation-delay: 0.2s;
}

.answer-text {
  padding: 16px;
  background: var(--surface-soft);
  border: 1px solid var(--line);
  border-radius: 8px;
}

.answer-text.markdown-content {
  display: grid;
  gap: 10px;
  white-space: normal;
  overflow-wrap: anywhere;
}

.subsection {
  margin-top: 18px;
}

.quality-section {
  display: grid;
  gap: 10px;
}

.quality-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  color: var(--text-secondary);
  font-size: 13px;
}

.quality-list {
  display: grid;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 13px;
}

.quality-list span {
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-soft);
}

.source-list,
.recommend-list {
  display: grid;
  gap: 10px;
}

.source-item,
.recommend-item {
  display: grid;
  gap: 4px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  text-align: left;
  text-decoration: none;
  cursor: pointer;
  color: var(--text);
}

.recommend-item:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.source-item span,
.recommend-item span {
  color: var(--muted);
  font-size: 13px;
}

.task-card {
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-soft);
}

.feedback-row {
  margin-top: 18px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.feedback-form {
  margin-top: 12px;
  display: grid;
  gap: 10px;
}

@keyframes loading-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes loading-dot {
  0%,
  80%,
  100% {
    transform: translateY(4px);
    opacity: 0.36;
  }

  40% {
    transform: translateY(-4px);
    opacity: 1;
  }
}

@keyframes loading-sheen {
  45%,
  100% {
    transform: translateX(100%);
  }
}

@keyframes loading-pulse {
  0%,
  100% {
    transform: scaleX(0.72);
    opacity: 0.42;
  }

  50% {
    transform: scaleX(1);
    opacity: 1;
  }
}

@keyframes loading-skeleton {
  0% {
    background-position: 100% 0;
  }

  100% {
    background-position: -100% 0;
  }
}

@media (max-width: 640px) {
  .context-grid {
    grid-template-columns: 1fr;
  }

  .answer-loading {
    grid-template-columns: 1fr;
  }

  .loading-orbit {
    width: 46px;
    height: 46px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .answer-loading::before,
  .loading-orbit::before,
  .loading-orbit span,
  .loading-title i,
  .loading-skeleton span {
    animation: none;
  }
}
</style>
