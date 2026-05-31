# 任务：搭建 Hermes 智能体管理平台 - Web 前端

## 背景
服务器上已有 FastAPI 后端在 `/home/admin/hermes-platform/agents_api/main.py`（端口8000），提供以下 API：
- `GET /` — 平台状态
- `GET /agents` — 列出所有智能体
- `GET /agents/{name}` — 获取智能体详情
- `POST /agents` — 创建智能体
- `DELETE /agents/{name}` — 删除智能体
- `POST /agents/{name}/chat` — 跟单个智能体对话
- `POST /cluster/run` — 启动集群协作（Orchestrator 总指挥调度）
- `GET /web` — 当前简陋的 HTML 页面

智能体配置存放在 `/home/admin/hermes-platform/agents_config/` 的 YAML 文件中。

## 任务目标
搭建一个**美观、专业的 Vue3 管理后台**，功能需求如下：

---

## 一、整体布局

```
┌──────────────────────────────────────────────────────┐
│  🤖 Hermes 智能体管理平台     [状态灯] [设置]        │  ← 顶部导航栏
├──────────┬───────────────────────────────────────────┤
│          │                                           │
│  📋 智能体│  主内容区域（根据标签页切换）              │
│  列表     │                                           │
│          │  💬 对话  🤖 智能体  👥 团队  📚 知识库 ⚙️设置│
│  👑 Hermes│                                           │
│  🎮 小明  │                                           │
│  🛠️ Codex│                                           │
│  💬 小美  │                                           │
│          │                                           │
│  ＋新建   │                                           │
│          │                                           │
├──────────┴───────────────────────────────────────────┤
│  底部状态栏                                           │
└──────────────────────────────────────────────────────┘
```

## 二、标签页功能

### 💬 对话（默认页）
- 左侧显示智能体列表（可点击选中）
- 右侧是聊天区域
- 如果**没有选中任何智能体**，消息发到 `/cluster/run`（集群模式，Orchestrator 自动分配）
- 如果**选中了某个智能体**，消息直接发给那个智能体（`/agents/{name}/chat`）
- 聊天记录保存在本地 localStorage，按 session 分组
- 消息显示思考过程（可折叠的「🧠 查看思考过程」）
- 支持 Markdown 渲染

### 🤖 智能体管理
- 表格显示所有智能体：名称、角色、模型、工具数、操作
- 点击「编辑」弹出对话框，可修改：
  - 名称、角色、描述
  - 模型选择（deepseek-v4-pro / deepseek-v4-flash）
  - 指令（textarea，多行）
  - 工具列表（多选框）
- 点击「删除」确认后删除
- 点击「＋新建智能体」弹出创建表单
- 智能体卡片显示：头像（首字母/emoji）、名称、在线状态

### 👥 团队管理（核心功能）
- **创建团队**：给团队起名，从智能体列表里勾选成员
- **每个团队有一个独立聊天室**：团队内的智能体协作完成任务
- 工作模式：
  - **并发模式**：Orchestrator 分配任务，所有成员同时执行
  - **顺序模式**：Agent A → B → C 依次执行
  - **讨论模式**：所有智能体轮流发言讨论（Round-Robin）
- 团队列表显示：名称、成员数、模式、最后活动时间
- 可以随时往团队里添加/移除智能体
- 可以同时创建多个团队，互不干扰

### 📚 知识库（留空占位）
- 显示「即将上线」页面
- 后续接入 RAG

### ⚙️ 设置
- API 状态显示（DeepSeek / OpenRouter 连接状态）
- 模型选择
- 暗色/亮色主题切换（默认暗色）

## 三、UI/UX 要求

### 设计风格
- **暗色主题**为主（#0f0f1a 深色背景）
- **紫色系主色调**（#7c3aed, #6d28d9）
- 毛玻璃效果（glassmorphism）
- 圆角、阴影、平滑动画
- 字体：系统字体栈（-apple-system, 'Segoe UI', sans-serif）

### 技术选型
- **Vue 3** + **Element Plus**（通过 CDN 引入，不需要打包工具）
- 所有代码写在一个 HTML 文件里（单页应用）
- 通过 `fetch` 调用后端 API
- 使用 `marked.js` 渲染 Markdown
- 使用 `highlight.js` 代码高亮

### 交互细节
- 发送消息时显示加载状态
- 智能体思考时显示打字动画
- 消息里如果包含 ```json 代码块，自动美化显示
- 团队协作时，显示每个智能体的任务进度
- 错误提示用 Element Plus 的 ElMessage

## 四、API 对接

前端所有数据通过 fetch 调用后端 API：
```javascript
const API_BASE = window.location.origin;

// 智能体
GET  /agents
GET  /agents/{name}
POST /agents         body: {name, role, description, model, instructions, tools}
DELETE /agents/{name}

// 对话
POST /agents/{name}/chat  body: {message, session_id}
POST /cluster/run         body: {task, session_id}

// 团队（需要新增后端 API）
POST /teams/create        body: {name, members: [...], mode: "parallel"|"sequential"|"discussion"}
GET  /teams/list
POST /teams/{id}/chat     body: {task, session_id}
DELETE /teams/{id}
```

## 五、新增后端 API（需要在 main.py 中添加）

在 main.py 末尾（`# ═════════ 启动 ═════════` 之前）添加团队管理 API：

```python
# 团队数据存储
TEAMS_FILE = DATA_DIR / "teams.json"

def load_teams():
    if TEAMS_FILE.exists():
        try: return json.loads(open(TEAMS_FILE).read())
        except: pass
    return []

def save_teams(teams):
    with open(TEAMS_FILE, "w") as f:
        json.dump(teams, f, ensure_ascii=False, indent=2)

@app.post("/teams/create")
async def create_team(req: Request):
    body = await req.json()
    teams = load_teams()
    team = {
        "id": f"team_{len(teams)+1}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "name": body.get("name", "新团队"),
        "members": body.get("members", []),
        "mode": body.get("mode", "parallel"),
        "created_at": datetime.now().isoformat(),
        "last_active": datetime.now().isoformat()
    }
    teams.append(team)
    save_teams(teams)
    return {"status": "ok", "team": team}

@app.get("/teams/list")
async def list_teams():
    return {"teams": load_teams()}

@app.post("/teams/{team_id}/chat")
async def team_chat(team_id: str, req: Request):
    body = await req.json()
    task = body.get("task", "")
    teams = load_teams()
    team = None
    for t in teams:
        if t["id"] == team_id:
            team = t
            break
    if not team:
        raise HTTPException(404, "团队不存在")
    
    agents = load_agents()
    members = [m for m in team["members"] if m in agents]
    
    if team["mode"] == "parallel":
        # 并发模式：Orchestrator 分配任务，所有成员同时执行
        # 调用现有 /cluster/run 逻辑
        pass
    elif team["mode"] == "sequential":
        # 顺序模式：A → B → C
        pass
    elif team["mode"] == "discussion":
        # 讨论模式：轮流发言
        pass
    
    return {"team": team["name"], "mode": team["mode"], "result": "开发中..."}

@app.delete("/teams/{team_id}")
async def delete_team(team_id: str):
    teams = load_teams()
    teams = [t for t in teams if t["id"] != team_id]
    save_teams(teams)
    return {"status": "ok"}
```

## 六、实施步骤

1. 先创建一个新的 HTML 文件 `/home/admin/hermes-platform/agents_api/dashboard.html`（完整的 Vue3 SPA）
2. 创建 `/home/admin/hermes-platform/agents_api/static/` 目录
3. 在 main.py 中添加团队管理 API
4. 添加一个 `GET /dashboard` 路由返回 dashboard.html
5. 修改 `__main__` 启动信息，提示 dashboard 地址

## 七、验证方式

1. 重启后端：`pkill -f "python main.py" && sleep 1 && cd /home/admin/hermes-platform/agents_api && nohup python main.py > /tmp/hermes_platform.log 2>&1 &`
2. 访问 http://localhost:8000/dashboard 查看完整效果
3. 测试：创建智能体、跟智能体对话、创建团队、团队协作

## 八、注意
- 保持后端 main.py 原有代码不变，只追加团队 API
- 前端使用 CDN 引入 Vue3/Element Plus，不要 npm 打包
- 所有代码兼容 Python 3.11
- 不要修改已经存在的 API 路径
- 颜色主题统一用紫色系
