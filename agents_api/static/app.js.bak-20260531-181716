const { createApp, ref, computed, reactive, nextTick, onMounted } = Vue;

const API_BASE = window.location.origin;

const app = createApp({
  setup() {
    // ── 导航 ──
    const activeMenu = ref('dashboard');

    function handleMenuSelect(index) {
      activeMenu.value = index;
      if (index === 'dashboard') loadDashboard();
      if (index === 'agents') loadAgents();
      if (index === 'knowledge') loadKnowledge();
      if (index === 'evolution') loadEvolution();
    }

    // ── API 工具 ──
    async function apiGet(path) {
      const res = await fetch(API_BASE + path);
      return res.json();
    }

    async function apiPost(path, body) {
      const res = await fetch(API_BASE + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(120000)
      });
      return res.json();
    }

    function formatContent(text) {
      if (!text) return '';
      let html = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      if (html.includes('【思考过程】') && html.includes('【回答】')) {
        const parts = html.split('【回答】');
        const thinkPart = parts[0].replace('【思考过程】', '').trim();
        const answerPart = '【回答】' + parts.slice(1).join('【回答】');
        html = `<div class="answer-block">${answerPart}</div>
          <details class="thinking-block">
            <summary>🧠 查看思考过程</summary>
            <div style="margin-top:8px;padding:8px;background:rgba(124,58,237,0.1);border-radius:6px;font-size:13px;color:#a78bfa;">${thinkPart}</div>
          </details>`;
      }
      return html;
    }

    // ── 控制台 ──
    const stats = reactive({
      agents_count: 0,
      knowledge_count: 0,
      evolution_count: 0,
      skills_count: 0
    });

    async function loadDashboard() {
      try {
        const rootData = await apiGet('/');
        stats.agents_count = rootData.agents_count || 0;
        stats.knowledge_count = rootData.knowledge_docs || 0;
        stats.evolution_count = 0;
        stats.skills_count = 0;
      } catch (e) { /* ignore */ }
    }

    // ── 智能体 ──
    const agents = ref([]);

    async function loadAgents() {
      try {
        const data = await apiGet('/agents');
        agents.value = data.agents || [];
      } catch (e) { /* ignore */ }
    }

    // 单个智能体对话
    const agentChatVisible = ref(false);
    const chatAgent = ref(null);
    const agentChatInput = ref('');
    const agentChatLoading = ref(false);
    const agentChatHistory = ref([]);
    const agentChatMsgs = ref(null);

    function showAgentChat(agent) {
      chatAgent.value = agent;
      agentChatHistory.value = [];
      agentChatInput.value = '';
      agentChatVisible.value = true;
    }

    async function sendAgentChat() {
      const msg = agentChatInput.value.trim();
      if (!msg || agentChatLoading.value) return;
      agentChatHistory.value.push({ role: 'user', content: msg });
      agentChatInput.value = '';
      agentChatLoading.value = true;
      scrollChat('agent');
      try {
        const data = await apiPost(`/agents/${chatAgent.value.name}/chat`, { message: msg });
        agentChatHistory.value.push({ role: 'assistant', content: data.response || '无响应' });
      } catch (e) {
        agentChatHistory.value.push({ role: 'assistant', content: '请求失败: ' + e.message });
      }
      agentChatLoading.value = false;
      scrollChat('agent');
    }

    // ── 知识库 ──
    const kbDocs = ref([]);
    const kbLoading = ref(false);
    const kbSearchQuery = ref('');
    const kbSearchResults = ref(null);
    const addKbVisible = ref(false);
    const kbAdding = ref(false);
    const addKbForm = reactive({ content: '', tagsStr: '', source: '' });

    const totalKbDocs = computed(() => kbDocs.value.length);
    const kbDisplayDocs = computed(() => kbSearchResults.value === null ? kbDocs.value : []);

    async function loadKnowledge() {
      kbLoading.value = true;
      try {
        const data = await apiGet('/knowledge');
        kbDocs.value = data.documents || [];
        kbSearchResults.value = null;
        kbSearchQuery.value = '';
      } catch (e) { /* ignore */ }
      kbLoading.value = false;
    }

    async function searchKnowledge() {
      const q = kbSearchQuery.value.trim();
      if (!q) { kbSearchResults.value = null; return; }
      try {
        const data = await apiPost('/knowledge/search', { query: q, top_k: 10 });
        kbSearchResults.value = data.results || [];
      } catch (e) { /* ignore */ }
    }

    function showAddKbDialog() {
      addKbForm.content = '';
      addKbForm.tagsStr = '';
      addKbForm.source = '';
      addKbVisible.value = true;
    }

    async function addKnowledge() {
      if (!addKbForm.content.trim()) return;
      kbAdding.value = true;
      try {
        const tags = addKbForm.tagsStr.split(',').map(t => t.trim()).filter(Boolean);
        await apiPost('/knowledge/add', {
          content: addKbForm.content,
          tags: tags,
          source: addKbForm.source
        });
        addKbVisible.value = false;
        loadKnowledge();
      } catch (e) { /* ignore */ }
      kbAdding.value = false;
    }

    // ── 集群对话 ──
    const clusterInput = ref('');
    const clusterLoading = ref(false);
    const clusterMessages = ref([]);
    const clusterMsgs = ref(null);
    const sessionId = 'session_' + Date.now();

    async function sendClusterTask() {
      const msg = clusterInput.value.trim();
      if (!msg || clusterLoading.value) return;
      clusterMessages.value.push({ role: 'user', content: msg, type: 'user' });
      clusterInput.value = '';
      clusterLoading.value = true;
      scrollChat('cluster');
      try {
        const data = await apiPost('/cluster/run', { task: msg, session_id: sessionId });
        if (data.orchestration) {
          clusterMessages.value.push({ role: 'assistant', content: data.orchestration, type: 'orchestration' });
        }
        if (data.knowledge_used && data.knowledge_used.length > 0) {
          clusterMessages.value.push({
            role: 'assistant',
            content: '检索到 ' + data.knowledge_used.length + ' 条相关知识：\n' +
              data.knowledge_used.map(d => '· ' + d).join('\n'),
            type: 'knowledge'
          });
        }
        if (data.results) {
          data.results.forEach(r => {
            clusterMessages.value.push({
              role: 'assistant',
              content: r.result,
              type: 'agent',
              agent: r.agent
            });
          });
        }
      } catch (e) {
        if (e.name !== 'AbortError') {
          clusterMessages.value.push({ role: 'assistant', content: '请求超时或失败: ' + e.message, type: 'agent', agent: '系统' });
        }
      }
      clusterLoading.value = false;
      scrollChat('cluster');
    }

    // ── 进化系统 ──
    const evolutionStats = reactive({
      total_learned: 0,
      skills_count: 0,
      knowledge_base_size: 0,
      recent_learnings: []
    });
    const evolutionSummary = ref('');

    async function loadEvolution() {
      try {
        evolutionSummary.value = '进化系统功能由 CLI 端 Hermes Agent 管理。\n在这里可以查看进化统计数据。';
      } catch (e) { /* ignore */ }
    }

    // ── 滚动 ──
    function scrollChat(type) {
      nextTick(() => {
        const el = type === 'agent' ? agentChatMsgs.value : clusterMsgs.value;
        if (el) el.scrollTop = el.scrollHeight;
      });
    }

    // ── 初始化 ──
    onMounted(() => {
      loadDashboard();
    });

    return {
      activeMenu, handleMenuSelect,
      stats,
      agents, showAgentChat, agentChatVisible, chatAgent,
      agentChatInput, agentChatLoading, agentChatHistory, agentChatMsgs, sendAgentChat,
      kbDocs, kbLoading, kbSearchQuery, kbSearchResults, addKbVisible, kbAdding,
      addKbForm, totalKbDocs, kbDisplayDocs, loadKnowledge, searchKnowledge, showAddKbDialog, addKnowledge,
      clusterInput, clusterLoading, clusterMessages, clusterMsgs, sendClusterTask,
      evolutionStats, evolutionSummary,
      formatContent
    };
  }
});

// 注册 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component);
}

app.use(ElementPlus);
app.mount('#app');
