# OpenCode 任务：彻底美化 Hermes 管理后台前端

## 背景
这是一个 AI 智能体管理平台（Hermes v3.0），使用 Vue3 + Element Plus CDN 方式构建。当前页面只有功能骨架，视觉上很简陋。

## 项目位置
- 工作目录：`/home/admin/hermes-platform/`
- 前端文件：`/home/admin/hermes-platform/agents_api/static/`
  - `index.html` — 主页面（Vue3 + Element Plus CDN）
  - `app.js` — Vue3 应用逻辑
  - `style.css` — 当前样式（需要被彻底重写）

## 后端 API（不要改，直接使用）
- GET `/` — 平台状态 `{agents_count, knowledge_docs}`
- GET `/agents` — 智能体列表 `{agents: [{name, role, description, model, reasoning}]}`
- GET `/knowledge` — 知识库 `{documents: [{id, content, tags, source, added_at}], count}`
- POST `/knowledge/add` — 添加知识 `{content, tags, source}`
- POST `/knowledge/search` — 搜索知识 `{query, top_k}`
- POST `/cluster/run` — 集群对话 `{task, session_id}` → 返回 `{orchestration, results: [{agent, result}], knowledge_used}`
- POST `/agents/{name}/chat` — 单智能体对话 `{message}` → `{response}`

## 任务目标

彻底重写 `style.css` 和修改 `index.html`（必要时也可修改 `app.js`），让页面达到**顶级 SaaS 管理后台的视觉水准**。

### 设计要求

#### 1. 配色方案
- 主色调：紫色 (#7c3aed / #a78bfa) + 深色背景
- 背景：从 #0a0a14 到 #12121e 渐变
- 卡片背景：半透明玻璃态效果（backdrop-filter: blur）
- 辅助色：绿色 (#22c55e) 表示运行中，金色/橙色 (#f59e0b) 表示思考和等待
- 整体要有"科技感"、"AI感"

#### 2. 侧边栏
- 不要纯色背景，使用半透明毛玻璃效果
- LOGO 区域：Hermes 图标 + 品牌名，有光晕效果
- 菜单项：大间距，悬浮有紫色光晕，激活项有左边框亮条 + 背景渐变
- 底部状态标签：圆润且有间距

#### 3. 统计卡片（控制台）
- 每张卡片要有对应图标（智能体=🤖，知识库=📚，学习次数=🧠，技能=⚡）
- 数字要大且醒目，使用渐变色文字
- 卡片顶部分割线光效（激活时亮起）
- 悬浮有 lift 动画 + 阴影扩散

#### 4. 智能体管理页面
- Agent 卡片：左上角显示 emoji 头像，右侧显示名称、角色、模型标签
- 思考模式标签使用紫色背景
- 卡片悬浮有紫色边框光晕
- 对话弹窗美观，气泡有圆角渐变

#### 5. 知识库页面
- el-table 使用深色主题行
- 操作按钮美观
- 添加弹窗表单排列优雅

#### 6. 集群对话页面
- 用户消息紫色渐变气泡
- AI 消息深色气泡，带 Agent 标签
- 思考过程用 details/summary 折叠，紫色主题
- 输入框区域有分割线，按钮好看

#### 7. 页面整体
- 背景有微弱的径向渐变光晕（左上角紫色，右下角蓝色）
- 所有卡片都有圆角、阴影、悬浮效果
- 页面切换有 fadeIn 动画
- 滚动条细且美观
- 字体优化（中英文混排好看）
- 所有 Element Plus 组件适配深色主题

#### 8. 不要有功能bug
- app.js 中 `loadDashboard` 只调 GET `/`，不要再调 `/evolution`（那个接口不存在）
- `loadEvolution` 页面只显示占位文字，不调任何 API
- 所有 API 调用路径用绝对路径 `/static/style.css`、`/static/app.js`（不要相对路径）
- 确保 script 加载顺序正确：Vue3 → Element Plus → Element Plus Icons → app.js，且都在 `</body>` 之前

## 输出要求
1. 重写 `/home/admin/hermes-platform/agents_api/static/style.css`（完整的漂亮样式）
2. 根据需要修改 `index.html`（比如加一些装饰性的 DOM 元素）
3. 确保所有路径使用绝对路径 `/static/xxx`
4. 完成后截图并告诉我结果
