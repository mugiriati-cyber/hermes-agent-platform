# OpenCode 任务：Vue3 管理前端

## 项目位置
- 工作目录：`/home/admin/hermes-platform/`
- 后端 API：FastAPI 服务，在 `agents_api/main.py`，端口 8000
- 前端输出目录：`/home/admin/hermes-platform/agents_api/static/`
- Agent 配置目录：`/home/admin/hermes-platform/agents_config/`

## 后端 API 接口（已存在，请直接调用）

### GET /agents
返回智能体列表：
```json
{"agents": [{"name": "hermes", "role": "主智能体", "description": "...", "model": "deepseek-v4-pro", "reasoning": true}, ...]}
```

### GET /knowledge
返回知识库文档：
```json
{"documents": [{"id": "doc_1", "content": "...", "tags": [...], "source": ""}], "count": 3}
```

### POST /knowledge/add
添加知识：`{"content": "...", "tags": [...], "source": ""}` → `{"status": "ok", "id": "...", "total": N}`

### POST /knowledge/search
搜索知识：`{"query": "...", "top_k": 5}` → `{"results": [...], "count": N}`

### POST /cluster/run
集群协作（核心接口）：`{"task": "...", "session_id": "..."}`
返回：
```json
{
  "session_id": "...",
  "task": "...",
  "orchestration": "总指挥分析结果文本",
  "plan": {"plan": [{"agent": "hermes", "task": "..."}], "type": "single"},
  "results": [{"agent": "hermes", "task": "...", "result": "智能体回复"}],
  "knowledge_used": ["知识库匹配的文本"],
  "agents_involved": ["hermes", "xiaoming"]
}
```

### POST /agents/{name}/chat
直接对话：`{"message": "..."}` → `{"agent": "hermes", "model": "deepseek-v4-pro", "response": "回复"}`

## 任务要求

### 1. 技术栈
- Vue 3 (Composition API + script setup)
- Element Plus (最新版)
- Vite 构建
- 单页面应用（SPA），可刷新不丢失状态
- jsDelivr CDN 或 npm 构建都行（CDN 更简单不需要 Node 构建）

### 2. 页面结构

用 Element Plus 的 el-container + el-menu 实现后台布局：

#### 左侧导航菜单
- 🗣️ 聊天（默认）
- 🧠 Agent 管理
- 👥 团队协作
- 📚 知识库
- ⚙️ 设置

#### 顶部
- 平台标题 + 状态指示（绿色圆点 + "运行中"）
- API 地址显示

#### 🗣️ 聊天页面
- 聊天记录区域（自动滚动到底部）
- 输入框（支持 Enter 发送，Shift+Enter 换行）
- 发送按钮（发送时禁用，显示加载状态）
- 每条消息显示：角色（用户/Agent名）、时间、内容（markdown 渲染）
- Agent 消息显示来源 Agent 名称标签
- 思考过程折叠/展开（如果回复包含 【思考过程】 段落）
- 知识库匹配结果在消息下方显示 "📚 检索到 N 条知识"

#### 🧠 Agent 管理页面
- 显示所有 Agent 卡片（el-card）
- 每个卡片：头像 emoji、名称、角色、模型、思考模式标签、描述
- 新建 Agent 按钮 → 弹窗表单（名称、角色、模型选择、描述、提示词）
- 编辑/删除 Agent
- 测试对话按钮（在当前 Agent 卡片内直接对话，不跳转页面）

#### 👥 团队协作页面
- 显示已创建的团队列表
- 创建团队弹窗：输入团队名称、勾选参与 Agent
- 团队运行模式选择：并发（所有 Agent 同时执行）、顺序（依次执行）、讨论（多轮对话）
- 团队运行界面：输入任务 → 显示每个 Agent 的执行过程和结果
- Agent 执行状态指示（等待中→运行中→完成）

#### 📚 知识库页面
- 搜索框（搜索知识库）
- 文档列表（el-table 或 el-card 列表）
- 添加文档弹窗（内容、标签、来源）
- 删除文档
- 文档数量统计

#### ⚙️ 设置页面
- 模型选择（deepseek-v4-pro / deepseek-v4-flash）
- API 地址显示（只读）
- 系统状态（Agent 数量、知识库文档数、运行时间）

### 3. 样式要求
- 深色主题（已有后端 CSS 是深色风格，保持一致）
- Element Plus 使用 dark 主题（class="dark" 或 el-config-provider）
- 丝滑动画
- 响应式
- 中文字体优化

### 4. 技术细节
- 所有 API 调用用 fetch，baseURL 为 `window.location.origin`
- 使用 Element Plus 的 el-loading 和弹窗组件
- 错误处理：API 失败时显示 ElMessage 错误提示
- session_id 存在 localStorage，刷新不丢失
- 支持深色模式持久化

### 5. 文件结构
```
agents_api/static/
  index.html          # 入口 HTML（加载 vue3、element-plus CDN）
  app.js              # Vue3 应用代码（所有页面和组件）
  style.css           # 自定义样式（Element Plus dark 覆盖）
```

不需要 npm/vite 构建，直接用 CDN 方式加载 Vue3 + Element Plus，所有代码在 app.js 里。

## 输出要求
请创建上述 3 个文件（index.html, app.js, style.css）到 /home/admin/hermes-platform/agents_api/static/ 目录。
然后修改 /home/admin/hermes-platform/agents_api/main.py，在 FastAPI 中挂载 static 目录并提供 /web 路由指向新的 index.html。

完成后告诉我创建了哪些文件。
