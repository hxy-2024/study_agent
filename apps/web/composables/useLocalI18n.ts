type Locale = 'en-US' | 'zh-CN'

type TranslationKey =
  | 'app.globalNavigation'
  | 'app.openNavigation'
  | 'app.localRuntime'
  | 'app.localUserProfile'
  | 'app.navigate'
  | 'app.workspace'
  | 'app.closeNavigation'
  | 'app.localSettings'
  | 'app.settings'
  | 'app.localModelDefaults'
  | 'app.closeSettings'
  | 'app.provider'
  | 'app.baseUrl'
  | 'app.apiKey'
  | 'app.defaultModel'
  | 'app.answerStyle'
  | 'app.webSearchDefault'
  | 'app.webSearchProvider'
  | 'app.tavilyApiKey'
  | 'app.loadingSettings'
  | 'app.settingsNote'
  | 'app.saving'
  | 'app.save'
  | 'app.saved'
  | 'app.runtime'
  | 'app.localStatus'
  | 'app.closeRuntime'
  | 'app.checkingServices'
  | 'app.runtimeUnavailable'
  | 'nav.home'
  | 'nav.library'
  | 'nav.reviews'
  | 'nav.progress'
  | 'nav.settings'
  | 'common.back'
  | 'common.cancel'
  | 'common.delete'
  | 'common.restore'
  | 'common.close'
  | 'common.loading'
  | 'common.new'
  | 'common.save'
  | 'common.saving'
  | 'common.search'
  | 'common.confirm'
  | 'common.generating'
  | 'dashboard.studySpaces'
  | 'dashboard.searchSpaces'
  | 'dashboard.loadingSpaces'
  | 'dashboard.startHere'
  | 'dashboard.createFirstSpace'
  | 'dashboard.createFirstSpaceBody'
  | 'dashboard.newStudySpace'
  | 'dashboard.continueStudy'
  | 'dashboard.deleteSpace'
  | 'dashboard.noSearchMatch'
  | 'dashboard.home'
  | 'dashboard.homeBody'
  | 'dashboard.mainAgent'
  | 'dashboard.continue'
  | 'dashboard.prepareRoute'
  | 'dashboard.currentProgress'
  | 'dashboard.minSuggested'
  | 'dashboard.routeFoundation'
  | 'dashboard.targetDays'
  | 'dashboard.dataSafety'
  | 'dashboard.exportCurrentSpace'
  | 'dashboard.exportBody'
  | 'dashboard.noActiveSpace'
  | 'dashboard.ready'
  | 'dashboard.readyBody'
  | 'dashboard.today'
  | 'dashboard.studyQueue'
  | 'dashboard.loadingDashboard'
  | 'dashboard.pendingAction'
  | 'dashboard.pendingActions'
  | 'dashboard.supervisionRefresh'
  | 'dashboard.supervisionRefreshes'
  | 'dashboard.aiMentor'
  | 'dashboard.recentRuntime'
  | 'dashboard.readyForSources'
  | 'dashboard.sourcesBody'
  | 'dashboard.reviewPlanner'
  | 'dashboard.nextSignals'
  | 'dashboard.archived'
  | 'dashboard.archivedSpaces'
  | 'dashboard.calendar'
  | 'dashboard.addDiary'
  | 'dashboard.addEvent'
  | 'dashboard.diary'
  | 'dashboard.event'
  | 'dashboard.addDiaryTitle'
  | 'dashboard.addEventTitle'
  | 'dashboard.entryTitle'
  | 'dashboard.entryBody'
  | 'dashboard.entryTitlePlaceholder'
  | 'dashboard.diaryBodyPlaceholder'
  | 'dashboard.eventBodyPlaceholder'
  | 'dashboard.saveEntry'
  | 'dashboard.noCalendarEntries'
  | 'dashboard.selectedDay'
  | 'dashboard.learningStatus'
  | 'dashboard.notesAndEvents'
  | 'dashboard.dayStudyQueue'
  | 'dashboard.noDayEntries'
  | 'dashboard.noDayQueue'
  | 'dashboard.openMainAgent'
  | 'dashboard.mainAgentConversation'
  | 'dashboard.planToday'
  | 'dashboard.closeMainAgent'
  | 'dashboard.mainAgentScope'
  | 'dashboard.mainAgentThinking'
  | 'dashboard.promptReview'
  | 'dashboard.promptNewMaterial'
  | 'dashboard.promptQuiz'
  | 'dashboard.inputPlaceholder'
  | 'dashboard.send'
  | 'dashboard.agentIntro'
  | 'dashboard.agentUpdated'
  | 'dashboard.requestFailed'
  | 'dashboard.archiveConfirm'
  | 'create.newLearningSpace'
  | 'create.title'
  | 'create.subtitle'
  | 'create.step1'
  | 'create.spaceGoal'
  | 'create.spaceName'
  | 'create.learningGoal'
  | 'create.targetDays'
  | 'create.step2'
  | 'create.materialRag'
  | 'create.viewChunks'
  | 'create.upload'
  | 'create.pasteMaterial'
  | 'create.pastePlaceholder'
  | 'create.embeddingPreset'
  | 'create.localChunkEmbeddings'
  | 'create.currentDefaultModel'
  | 'create.runIngestion'
  | 'create.runningIngestion'
  | 'create.step3'
  | 'create.routeOutline'
  | 'create.generateRoute'
  | 'create.generatingRoute'
  | 'create.editableRoute'
  | 'create.emptyRoute'
  | 'create.days'
  | 'create.generateDetails'
  | 'create.generatingDetails'
  | 'create.ragPreview'
  | 'create.embeddedChunks'
  | 'create.chunk'
  | 'create.chapters'
  | 'create.chapterDetail'
  | 'create.entering'
  | 'create.confirmEnter'
  | 'create.fillRoute'
  | 'create.fillRag'
  | 'create.duplicateName'
  | 'create.routeFailed'
  | 'create.ragFailed'
  | 'create.notReady'
  | 'create.enterFailed'
  | 'settings.localRuntime'
  | 'settings.title'
  | 'settings.subtitle'
  | 'settings.general'
  | 'settings.appearance'
  | 'settings.configuration'
  | 'settings.refreshModels'
  | 'settings.refreshingModels'
  | 'settings.webSearchDefault'
  | 'settings.webSearchProvider'
  | 'settings.language'
  | 'settings.answerStyle'
  | 'settings.mainAgentPrompt'
  | 'settings.sessionTutorPrompt'
  | 'settings.chapterMentorPrompt'
  | 'settings.loading'
  | 'settings.note'

const translations: Record<Locale, Record<TranslationKey, string>> = {
  'en-US': {
    'app.globalNavigation': 'Global navigation',
    'app.openNavigation': 'Open navigation',
    'app.localRuntime': 'Local runtime',
    'app.localUserProfile': 'Local user profile',
    'app.navigate': 'Navigate',
    'app.workspace': 'Workspace',
    'app.closeNavigation': 'Close navigation',
    'app.localSettings': 'Local settings',
    'app.settings': 'Settings',
    'app.localModelDefaults': 'Local model defaults',
    'app.closeSettings': 'Close settings',
    'app.provider': 'Provider',
    'app.baseUrl': 'Base URL',
    'app.apiKey': 'API key',
    'app.defaultModel': 'Default model',
    'app.answerStyle': 'Answer style',
    'app.webSearchDefault': 'Web search default',
    'app.webSearchProvider': 'Web search provider',
    'app.tavilyApiKey': 'Tavily API key',
    'app.loadingSettings': 'Loading local AI settings...',
    'app.settingsNote': 'These defaults are stored locally for this personal runtime.',
    'app.saving': 'Saving...',
    'app.save': 'Save',
    'app.saved': 'Saved',
    'app.runtime': 'Runtime',
    'app.localStatus': 'Local status',
    'app.closeRuntime': 'Close runtime status',
    'app.checkingServices': 'Checking local services...',
    'app.runtimeUnavailable': 'Runtime status is unavailable.',
    'nav.home': 'Home',
    'nav.library': 'Library',
    'nav.reviews': 'Reviews',
    'nav.progress': 'Progress',
    'nav.settings': 'Settings',
    'common.back': 'Back',
    'common.cancel': 'Cancel',
    'common.delete': 'Delete',
    'common.restore': 'Restore',
    'common.close': 'Close',
    'common.loading': 'Loading...',
    'common.new': 'New',
    'common.save': 'Save',
    'common.saving': 'Saving...',
    'common.search': 'Search',
    'common.confirm': 'Confirm',
    'common.generating': 'Generating...',
    'dashboard.studySpaces': 'Study spaces',
    'dashboard.searchSpaces': 'Search spaces',
    'dashboard.loadingSpaces': 'Loading study spaces',
    'dashboard.startHere': 'Start here',
    'dashboard.createFirstSpace': 'Create your first study space',
    'dashboard.createFirstSpaceBody': 'Set a goal, upload material, and let the workspace organize a route.',
    'dashboard.newStudySpace': 'New Study Space',
    'dashboard.continueStudy': 'Continue study',
    'dashboard.deleteSpace': 'Delete space',
    'dashboard.noSearchMatch': 'No spaces match this search.',
    'dashboard.home': 'Home',
    'dashboard.homeBody': 'Main Agent keeps the next useful learning move visible and reversible.',
    'dashboard.mainAgent': 'Main Agent',
    'dashboard.continue': 'Continue',
    'dashboard.prepareRoute': 'Prepare route',
    'dashboard.currentProgress': 'Current space progress',
    'dashboard.minSuggested': 'min suggested',
    'dashboard.routeFoundation': 'route foundation prepared',
    'dashboard.targetDays': 'target days',
    'dashboard.dataSafety': 'Data safety',
    'dashboard.exportCurrentSpace': 'Export current space',
    'dashboard.exportBody': 'Download a local snapshot before large edits or cleanup.',
    'dashboard.noActiveSpace': 'No active space',
    'dashboard.ready': 'Your dashboard is ready',
    'dashboard.readyBody': 'Create a study space to start the local learning loop.',
    'dashboard.today': 'Today',
    'dashboard.studyQueue': 'Study queue',
    'dashboard.loadingDashboard': 'Loading local dashboard...',
    'dashboard.pendingAction': 'pending action',
    'dashboard.pendingActions': 'pending actions',
    'dashboard.supervisionRefresh': 'supervision refresh',
    'dashboard.supervisionRefreshes': 'supervision refreshes',
    'dashboard.aiMentor': 'AI Mentor',
    'dashboard.recentRuntime': 'Recent runtime',
    'dashboard.readyForSources': 'Ready for sources',
    'dashboard.sourcesBody': 'Upload text or Markdown in a study space to prepare retrieval and route generation.',
    'dashboard.reviewPlanner': 'Review Planner',
    'dashboard.nextSignals': 'Next learning signals',
    'dashboard.archived': 'Archived',
    'dashboard.archivedSpaces': 'Archived spaces',
    'dashboard.calendar': 'Calendar',
    'dashboard.addDiary': 'Add diary',
    'dashboard.addEvent': 'Add event',
    'dashboard.diary': 'Diary',
    'dashboard.event': 'Event',
    'dashboard.addDiaryTitle': 'Add diary',
    'dashboard.addEventTitle': 'Add event',
    'dashboard.entryTitle': 'Title',
    'dashboard.entryBody': 'Content',
    'dashboard.entryTitlePlaceholder': 'Optional short title',
    'dashboard.diaryBodyPlaceholder': 'What did you learn, notice, or want to remember today?',
    'dashboard.eventBodyPlaceholder': 'What needs to happen, and when?',
    'dashboard.saveEntry': 'Save',
    'dashboard.noCalendarEntries': 'No diary or event yet.',
    'dashboard.selectedDay': 'Selected day',
    'dashboard.learningStatus': 'Learning status',
    'dashboard.notesAndEvents': 'Notes and events',
    'dashboard.dayStudyQueue': 'Study queue',
    'dashboard.noDayEntries': 'No notes or events for this day.',
    'dashboard.noDayQueue': 'No study queue for this day.',
    'dashboard.openMainAgent': 'Open Main Agent',
    'dashboard.mainAgentConversation': 'Main Agent conversation',
    'dashboard.planToday': "Plan today's study",
    'dashboard.closeMainAgent': 'Close Main Agent',
    'dashboard.mainAgentScope': 'Reads learning state, updates dashboard recommendations, and opens approved study actions.',
    'dashboard.mainAgentThinking': "Thinking through today's best next step...",
    'dashboard.promptReview': '15 min review',
    'dashboard.promptNewMaterial': 'New material',
    'dashboard.promptQuiz': 'Quiz me',
    'dashboard.inputPlaceholder': 'Tell Main Agent what you need today...',
    'dashboard.send': 'Send',
    'dashboard.agentIntro': "Tell me what kind of session you want. I can adjust today's plan around your time, energy, and study intent.",
    'dashboard.agentUpdated': "I updated today's plan based on your request.",
    'dashboard.requestFailed': 'Unable to load recommendation:',
    'dashboard.archiveConfirm': 'This will archive the space.',
    'create.newLearningSpace': 'New learning space',
    'create.title': 'Create learning space',
    'create.subtitle': 'Set the goal, upload material, run ingestion, review the AI route, and enter chapter study.',
    'create.step1': 'Step 1',
    'create.spaceGoal': 'Space and learning goal',
    'create.spaceName': 'Space name',
    'create.learningGoal': 'Learning goal',
    'create.targetDays': 'Target days',
    'create.step2': 'Step 2',
    'create.materialRag': 'Material and RAG ingestion',
    'create.viewChunks': 'View chunks',
    'create.upload': 'Upload Markdown or text',
    'create.pasteMaterial': 'Or paste material',
    'create.pastePlaceholder': 'Paste course notes, Markdown, or article text...',
    'create.embeddingPreset': 'Embedding preset',
    'create.localChunkEmbeddings': 'Local chunk embeddings',
    'create.currentDefaultModel': 'Current default model',
    'create.runIngestion': 'Run ingestion',
    'create.runningIngestion': 'Running ingestion...',
    'create.step3': 'Step 3',
    'create.routeOutline': 'Learning route outline',
    'create.generateRoute': 'Generate route',
    'create.generatingRoute': 'Generating route...',
    'create.editableRoute': 'Editable route outline',
    'create.emptyRoute': 'After ingestion, the AI-generated route appears here. You can also render a draft first.',
    'create.days': 'days',
    'create.generateDetails': 'Generate chapter study details',
    'create.generatingDetails': 'Generating, please wait...',
    'create.ragPreview': 'RAG preview',
    'create.embeddedChunks': 'Embedded chunks',
    'create.chunk': 'Chunk',
    'create.chapters': 'Chapters',
    'create.chapterDetail': 'Chapter detail',
    'create.entering': 'Entering...',
    'create.confirmEnter': 'Confirm and enter chapter study',
    'create.fillRoute': 'Fill in the space name and learning goal before generating a route.',
    'create.fillRag': 'Fill in the space name, learning goal, and material before running ingestion.',
    'create.duplicateName': 'A study space with this name already exists.',
    'create.routeFailed': 'Unable to generate route',
    'create.ragFailed': 'RAG processing failed',
    'create.notReady': 'Chapters are not ready yet. Run RAG or generate a route first.',
    'create.enterFailed': 'Unable to enter chapter study',
    'settings.localRuntime': 'Local runtime',
    'settings.title': 'Settings',
    'settings.subtitle': 'Manage the local personal runtime model, language, and agent behavior.',
    'settings.general': 'General',
    'settings.appearance': 'Appearance',
    'settings.configuration': 'Configuration',
    'settings.refreshModels': 'Refresh models',
    'settings.refreshingModels': 'Refreshing...',
    'settings.webSearchDefault': 'Enable web supplement by default',
    'settings.webSearchProvider': 'Web search provider',
    'settings.language': 'Language',
    'settings.answerStyle': 'Answer style',
    'settings.mainAgentPrompt': 'Layer 1 main agent system prompt',
    'settings.sessionTutorPrompt': 'Layer 2 session tutor system prompt',
    'settings.chapterMentorPrompt': 'Layer 3 chapter mentor system prompt',
    'settings.loading': 'Loading local settings...',
    'settings.note': 'Settings are stored in local .local/settings.json and are not uploaded.'
  },
  'zh-CN': {
    'app.globalNavigation': '全局导航',
    'app.openNavigation': '打开导航',
    'app.localRuntime': '本地运行',
    'app.localUserProfile': '本地用户',
    'app.navigate': '导航',
    'app.workspace': '工作区',
    'app.closeNavigation': '关闭导航',
    'app.localSettings': '本地设置',
    'app.settings': '设置',
    'app.localModelDefaults': '本地模型默认值',
    'app.closeSettings': '关闭设置',
    'app.provider': '服务商',
    'app.baseUrl': 'Base URL',
    'app.apiKey': 'API key',
    'app.defaultModel': '默认模型',
    'app.answerStyle': '回答风格',
    'app.webSearchDefault': '默认开启联网补充',
    'app.webSearchProvider': '联网服务',
    'app.tavilyApiKey': 'Tavily API key',
    'app.loadingSettings': '正在读取本地 AI 设置...',
    'app.settingsNote': '这些默认值保存在本机个人运行时中。',
    'app.saving': '保存中...',
    'app.save': '保存',
    'app.saved': '配置成功',
    'app.runtime': '运行时',
    'app.localStatus': '本地状态',
    'app.closeRuntime': '关闭运行状态',
    'app.checkingServices': '正在检查本地服务...',
    'app.runtimeUnavailable': '无法读取运行状态。',
    'nav.home': '主页',
    'nav.library': '资料库',
    'nav.reviews': '复习',
    'nav.progress': '进度',
    'nav.settings': '设置',
    'common.back': '返回',
    'common.cancel': '取消',
    'common.delete': '删除',
    'common.restore': '恢复',
    'common.close': '关闭',
    'common.loading': '加载中...',
    'common.new': '新建',
    'common.save': '保存',
    'common.saving': '保存中...',
    'common.search': '搜索',
    'common.confirm': '确认',
    'common.generating': '生成中...',
    'dashboard.studySpaces': '学习空间',
    'dashboard.searchSpaces': '搜索学习空间',
    'dashboard.loadingSpaces': '正在加载学习空间',
    'dashboard.startHere': '从这里开始',
    'dashboard.createFirstSpace': '创建第一个学习空间',
    'dashboard.createFirstSpaceBody': '设定目标、上传资料，让工作区组织学习路线。',
    'dashboard.newStudySpace': '新建学习空间',
    'dashboard.continueStudy': '继续学习',
    'dashboard.deleteSpace': '删除学习空间',
    'dashboard.noSearchMatch': '没有匹配的学习空间。',
    'dashboard.home': '主页',
    'dashboard.homeBody': '主 Agent 会把下一步最有价值的学习动作放到你面前，并且可调整。',
    'dashboard.mainAgent': '主 Agent',
    'dashboard.continue': '继续',
    'dashboard.prepareRoute': '准备路线',
    'dashboard.currentProgress': '当前学习空间进度',
    'dashboard.minSuggested': '分钟建议',
    'dashboard.routeFoundation': '路线基础已准备',
    'dashboard.targetDays': '目标天数',
    'dashboard.dataSafety': '数据安全',
    'dashboard.exportCurrentSpace': '导出当前学习空间',
    'dashboard.exportBody': '在大幅修改或清理前下载一份本地快照。',
    'dashboard.noActiveSpace': '没有活跃学习空间',
    'dashboard.ready': '你的主页已准备好',
    'dashboard.readyBody': '创建一个学习空间，开始本地学习闭环。',
    'dashboard.today': '今天',
    'dashboard.studyQueue': '学习队列',
    'dashboard.loadingDashboard': '正在加载本地主页...',
    'dashboard.pendingAction': '个待处理动作',
    'dashboard.pendingActions': '个待处理动作',
    'dashboard.supervisionRefresh': '次监督刷新',
    'dashboard.supervisionRefreshes': '次监督刷新',
    'dashboard.aiMentor': 'AI 导师',
    'dashboard.recentRuntime': '最近运行',
    'dashboard.readyForSources': '等待资料',
    'dashboard.sourcesBody': '在学习空间上传文本或 Markdown，用于准备检索与路线生成。',
    'dashboard.reviewPlanner': '复习规划器',
    'dashboard.nextSignals': '下一批学习信号',
    'dashboard.archived': '已归档',
    'dashboard.archivedSpaces': '已归档学习空间',
    'dashboard.calendar': '日历',
    'dashboard.addDiary': '添加日记',
    'dashboard.addEvent': '添加事件',
    'dashboard.diary': '日记',
    'dashboard.event': '事件',
    'dashboard.addDiaryTitle': '添加日记',
    'dashboard.addEventTitle': '添加事件',
    'dashboard.entryTitle': '标题',
    'dashboard.entryBody': '内容',
    'dashboard.entryTitlePlaceholder': '可选的简短标题',
    'dashboard.diaryBodyPlaceholder': '今天学到了什么、注意到什么，或者想记住什么？',
    'dashboard.eventBodyPlaceholder': '需要安排什么？什么时候做？',
    'dashboard.saveEntry': '保存',
    'dashboard.noCalendarEntries': '还没有日记或事件。',
    'dashboard.selectedDay': '选中日期',
    'dashboard.learningStatus': '学习状态',
    'dashboard.notesAndEvents': '笔记与事件',
    'dashboard.dayStudyQueue': '学习队列',
    'dashboard.noDayEntries': '这一天还没有笔记或事件。',
    'dashboard.noDayQueue': '这一天还没有学习队列。',
    'dashboard.openMainAgent': '打开主 Agent',
    'dashboard.mainAgentConversation': '主 Agent 对话',
    'dashboard.planToday': '规划今天的学习',
    'dashboard.closeMainAgent': '关闭主 Agent',
    'dashboard.mainAgentScope': '读取学习状态，更新主页建议，并打开你确认过的学习动作。',
    'dashboard.mainAgentThinking': '正在思考今天最合适的下一步...',
    'dashboard.promptReview': '15 分钟复习',
    'dashboard.promptNewMaterial': '学习新内容',
    'dashboard.promptQuiz': '今天测验我',
    'dashboard.inputPlaceholder': '告诉主 Agent 你今天需要什么...',
    'dashboard.send': '发送',
    'dashboard.agentIntro': '告诉我你想要怎样的学习安排。我可以结合你的时间、状态和学习意图调整今天的计划。',
    'dashboard.agentUpdated': '我已根据你的请求更新今天的计划。',
    'dashboard.requestFailed': '无法读取建议：',
    'dashboard.archiveConfirm': '这会将该学习空间归档。',
    'create.newLearningSpace': '新建学习空间',
    'create.title': '创建学习空间',
    'create.subtitle': '设定目标、上传资料、运行提取、检查 AI 路线，然后进入章节学习。',
    'create.step1': '第 1 步',
    'create.spaceGoal': '学习空间与目标',
    'create.spaceName': '学习空间名称',
    'create.learningGoal': '学习目标',
    'create.targetDays': '目标天数',
    'create.step2': '第 2 步',
    'create.materialRag': '资料与 RAG 提取',
    'create.viewChunks': '查看分块',
    'create.upload': '上传 Markdown 或文本',
    'create.pasteMaterial': '或粘贴资料',
    'create.pastePlaceholder': '粘贴课程笔记、Markdown 或文章内容...',
    'create.embeddingPreset': 'Embedding 预设',
    'create.localChunkEmbeddings': '本地分块 embedding',
    'create.currentDefaultModel': '当前默认模型',
    'create.runIngestion': '运行提取',
    'create.runningIngestion': '正在提取...',
    'create.step3': '第 3 步',
    'create.routeOutline': '学习路线大纲',
    'create.generateRoute': '生成路线',
    'create.generatingRoute': '正在生成路线...',
    'create.editableRoute': '可编辑路线大纲',
    'create.emptyRoute': '提取后，AI 生成的路线会显示在这里。你也可以先生成草稿。',
    'create.days': '天',
    'create.generateDetails': '生成章节学习详情',
    'create.generatingDetails': '正在生成，请稍候...',
    'create.ragPreview': 'RAG 预览',
    'create.embeddedChunks': '已嵌入分块',
    'create.chunk': '分块',
    'create.chapters': '章节',
    'create.chapterDetail': '章节详情',
    'create.entering': '正在进入...',
    'create.confirmEnter': '确认并进入章节学习',
    'create.fillRoute': '请先填写学习空间名称和学习目标，再生成路线。',
    'create.fillRag': '请先填写学习空间名称、学习目标和资料，再运行提取。',
    'create.duplicateName': '已有同名学习空间，请换一个名称。',
    'create.routeFailed': '无法生成路线',
    'create.ragFailed': 'RAG 处理失败',
    'create.notReady': '章节尚未准备好。请先运行 RAG 或生成路线。',
    'create.enterFailed': '无法进入章节学习',
    'settings.localRuntime': '本地运行',
    'settings.title': '设置',
    'settings.subtitle': '管理本地个人运行时的模型、语言和 agent 行为。',
    'settings.general': '常规',
    'settings.appearance': '外观',
    'settings.configuration': '配置',
    'settings.refreshModels': '刷新模型',
    'settings.refreshingModels': '刷新中...',
    'settings.webSearchDefault': '默认开启联网补充',
    'settings.webSearchProvider': '联网服务',
    'settings.language': '语言',
    'settings.answerStyle': '回答风格',
    'settings.mainAgentPrompt': '一层主 Agent 系统提示词',
    'settings.sessionTutorPrompt': '二层会话监督 Agent 系统提示词',
    'settings.chapterMentorPrompt': '三层章节协助 Agent 系统提示词',
    'settings.loading': '正在读取本地配置...',
    'settings.note': '配置保存在本机 .local/settings.json，不会上传到外部服务。'
  }
}

function devAuthHeaders() {
  return {
    'X-User-Id': '00000000-0000-0000-0000-000000000002',
    'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
  }
}

export function useLocalI18n() {
  const config = useRuntimeConfig()
  const locale = useState<Locale>('local-locale', () => 'zh-CN')
  const loaded = useState<boolean>('local-locale-loaded', () => false)

  const isZh = computed(() => locale.value === 'zh-CN')

  async function loadLocale(force = false) {
    if (loaded.value && !force) return locale.value
    try {
      const response = await $fetch<{ locale?: Locale }>(`${config.public.apiBaseUrl}/local-settings/ai`, {
        headers: devAuthHeaders()
      })
      locale.value = response.locale || 'zh-CN'
      loaded.value = true
    } catch {
      loaded.value = true
    }
    return locale.value
  }

  function setLocale(nextLocale: Locale) {
    locale.value = nextLocale
    loaded.value = true
  }

  function t(key: TranslationKey) {
    return translations[locale.value][key] ?? translations['en-US'][key] ?? key
  }

  return {
    locale,
    isZh,
    loadLocale,
    setLocale,
    t
  }
}
