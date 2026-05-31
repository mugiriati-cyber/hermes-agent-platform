#!/usr/bin/env python3
"""
Hermes 智能体管理平台 v3.0
- 总指挥 Orchestrator
- 向量知识库 RAG（基于 ChromaDB + 嵌入模型）
- 并行执行，速度更快
- Web 管理界面
"""
import os, sys, json, yaml, re, asyncio, time, hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# 环境变量
env_file = Path("/home/admin/.hermes/.env")
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            if val and val != "***":
                os.environ.setdefault(key.strip(), val.strip())

sys.path.insert(0, "/home/admin/praison-env/lib/python3.11/site-packages")

# ─── 配置 ───────
AGENTS_DIR = Path("/home/admin/hermes-platform/agents_config")
DATA_DIR = Path("/home/admin/hermes-platform/data")
CHAT_DIR = DATA_DIR / "chat"
KB_DIR = DATA_DIR / "knowledge"
CACHE_DIR = DATA_DIR / "cache"
KB_DIR.mkdir(parents=True, exist_ok=True)
CHAT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ─── 缓存系统 ───────
class ResponseCache:
    """智能缓存系统 - 相同问题直接返回，速度提升"""
    
    def __init__(self, max_size=100, ttl=3600):
        self.cache_file = CACHE_DIR / "response_cache.json"
        self.max_size = max_size
        self.ttl = ttl
        self.cache: Dict[str, Dict] = {}
        self._load()
    
    def _load(self):
        if self.cache_file.exists():
            try:
                data = json.loads(open(self.cache_file).read())
                # 清理过期缓存
                now = time.time()
                self.cache = {k: v for k, v in data.items() if now - v.get('time', 0) < self.ttl}
            except:
                self.cache = {}
    
    def _save(self):
        with open(self.cache_file, "w") as f:
            json.dump(self.cache, f, ensure_ascii=False)
    
    def _make_key(self, model: str, messages: list) -> str:
        """生成缓存键"""
        content = f"{model}|{json.dumps(messages, ensure_ascii=False, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, model: str, messages: list) -> Optional[str]:
        key = self._make_key(model, messages)
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['time'] < self.ttl:
                return entry['response']
            else:
                del self.cache[key]
        return None
    
    def set(self, model: str, messages: list, response: str):
        key = self._make_key(model, messages)
        self.cache[key] = {'response': response, 'time': time.time()}
        # 限制缓存大小
        if len(self.cache) > self.max_size:
            oldest = min(self.cache.keys(), key=lambda k: self.cache[k]['time'])
            del self.cache[oldest]
        self._save()
    
    def stats(self) -> Dict:
        return {"size": len(self.cache), "max_size": self.max_size, "ttl": self.ttl}

cache = ResponseCache()

# ─── 知识库 (RAG) ───────
class KnowledgeBase:
    """轻量级知识库 - 关键词检索（不依赖 ChromaDB，减少依赖）"""
    
    def __init__(self):
        self.docs: List[Dict] = []
        self._load()
    
    def _load(self):
        """加载知识库文档"""
        self.docs = []
        if KB_DIR.exists():
            for f in sorted(KB_DIR.glob("*.json")):
                try:
                    with open(f) as fh:
                        data = json.load(fh)
                        if isinstance(data, list):
                            self.docs.extend(data)
                        else:
                            self.docs.append(data)
                except:
                    pass
        # 如果没有文档，添加默认示例
        if not self.docs:
            self.docs = [
                {"id": "default_1", "content": "Hermes 智能体管理平台 v3.0，支持多智能体协作、RAG知识库、思考模式", "tags": ["platform", "hermes"]},
                {"id": "default_2", "content": "可用智能体：Hermes（主智能体）、Codex（代码智能体）、小明（NPC角色）、小美（客服）", "tags": ["agents"]},
                {"id": "default_3", "content": "所有智能体使用 deepseek-v4-pro 模型，开启思考模式", "tags": ["model", "deepseek"]},
            ]
            self._save()
    
    def _save(self):
        with open(KB_DIR / "knowledge_base.json", "w") as f:
            json.dump(self.docs, f, ensure_ascii=False)
    
    def add(self, content: str, tags: List[str] = None, source: str = ""):
        """添加文档到知识库"""
        doc = {
            "id": f"doc_{len(self.docs) + 1}_{int(time.time())}",
            "content": content,
            "tags": tags or [],
            "source": source,
            "added_at": datetime.now().isoformat()
        }
        self.docs.append(doc)
        self._save()
        return doc["id"]
    
    def search(self, query: str, top_k: int = 3) -> List[str]:
        """关键词搜索 + 简单语义评分"""
        if not self.docs:
            return []
        
        query = query.lower()
        query_words = set(query.split())
        
        scored = []
        for doc in self.docs:
            content = doc.get("content", "").lower()
            tags = " ".join(doc.get("tags", [])).lower()
            
            # 评分：关键词匹配 + 标签匹配
            score = 0
            for word in query_words:
                if len(word) < 2:
                    continue
                if word in content:
                    score += content.count(word) * 2
                if word in tags:
                    score += 5
                # 短语匹配
                if query in content:
                    score += 10
            
            if score > 0:
                scored.append((score, doc["content"]))
        
        # 按分数排序
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:top_k]]
    
    def get_all(self) -> List[Dict]:
        return self.docs

kb = KnowledgeBase()

# ─── LLM ───────
def call_llm(messages, model="deepseek-v4-pro", temperature=0.7, max_tokens=8192, use_cache=True):
    """调用 DeepSeek API（带缓存）"""
    from openai import OpenAI
    
    # 缓存查询
    if use_cache:
        cached = cache.get(model, messages)
        if cached:
            return cached
    
    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        base_url="https://api.deepseek.com"
    )
    try:
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if "pro" in model.lower():
            kwargs["reasoning_effort"] = "high"
        resp = client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content
        rc = getattr(resp.choices[0].message, 'reasoning_content', None) or ""
        if rc:
            content = f"【思考过程】\n{rc}\n\n【回答】\n{content}"
        
        # 保存到缓存
        if use_cache:
            cache.set(model, messages, content)
        
        return content
    except Exception as e:
        return f"⚠️ 调用失败: {e}"

def call_llm_fast(messages, model="deepseek-v4-pro", temperature=0.7):
    """快速调用（低 max_tokens）"""
    return call_llm(messages, model, temperature, max_tokens=2048)

def load_agents():
    agents = {}
    if AGENTS_DIR.exists():
        for f in AGENTS_DIR.glob("*.yaml"):
            if f.name.startswith("_"): continue
            with open(f) as fh:
                try:
                    cfg = yaml.safe_load(fh)
                    if cfg: agents[cfg["name"]] = cfg
                except: pass
    return agents

def get_agents_info():
    agents = load_agents()
    return "\n".join([f"- {n}({a.get('role','')}): {a.get('description','')[:60]}" for n,a in agents.items()])

def parse_plan(text):
    """解析 Orchestrator 返回的计划"""
    if not text: return None
    patterns = [
        r'```(?:json)?\s*(\{.*?\})\s*```',
        r'(\{[^{}]*"plan"[^{}]*\[.*?\][^{}]*\})',
    ]
    for p in patterns:
        m = re.search(p, text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                if "plan" in data: return data
            except: pass
    # 尝试全文
    start, end = text.find('{'), text.rfind('}')
    if start != -1 and end != -1:
        try:
            data = json.loads(text[start:end+1])
            if "plan" in data: return data
        except: pass
    return None

def save_chat(session_id, message):
    f = CHAT_DIR / f"{session_id}.json"
    msgs = []
    if f.exists():
        try: msgs = json.loads(open(f).read())
        except: pass
    msgs.append(message)
    with open(f, "w") as fh:
        json.dump(msgs[-100:], fh, ensure_ascii=False)

def load_chat(session_id):
    f = CHAT_DIR / f"{session_id}.json"
    if f.exists():
        try: return json.loads(open(f).read())
        except: pass
    return []

# ─── Orchestrator 提示词 ───────
ORCHESTRATOR_PROMPT = """## 你的身份
你是**总指挥智能体（Orchestrator）**，只负责分配任务，不自己完成。

## 你的职责
1. 分析用户任务 → 判断是简单还是复杂
2. 简单任务 → 分配**一个**最合适的智能体
3. 复杂任务 → 拆解为子任务，分配给多个智能体并行执行

## 分配规则（必须遵守）
- 问候/闲聊 → 分配给 Hermes
- 写代码/技术 → 分配给 Codex
- 角色扮演/剧情 → 分配给 小明
- 客服/咨询 → 分配给 小美
- 复杂项目 → 拆解后分配给多个智能体并行

## 可用智能体
{agents_info}

## 返回格式（只返回JSON，不要其他内容）
简单任务：
{{"plan": [{{"agent": "名称", "task": "任务"}}], "type": "single"}}

复杂任务（并行）：
{{"plan": [{{"agent": "名称1", "task": "子任务1"}}, {{"agent": "名称2", "task": "子任务2"}}], "type": "multi"}}"""

# ─── FastAPI ───────
app = FastAPI(title="Hermes 智能体管理平台", version="3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# ═══════════════════════════════════════
# API
# ═══════════════════════════════════════

@app.get("/")
async def root():
    agents = load_agents()
    return {"platform": "Hermes 智能体管理平台", "version": "3.0",
            "agents_count": len(agents), "knowledge_docs": len(kb.docs),
            "agents": [{"name": a["name"], "role": a.get("role","")} for a in agents.values()],
            "status": "running"}

@app.get("/agents")
async def list_agents():
    agents = load_agents()
    return {"agents": [{"name": a["name"], "role": a.get("role",""),
                        "description": a.get("description",""), "model": a.get("model",""),
                        "reasoning": a.get("reasoning", False)} for a in agents.values()]}

# ─── 知识库 API ───────

@app.get("/knowledge")
async def get_knowledge():
    return {"documents": kb.get_all(), "count": len(kb.docs)}

@app.post("/knowledge/add")
async def add_knowledge(req: Request):
    body = await req.json()
    doc_id = kb.add(
        content=body.get("content", ""),
        tags=body.get("tags", []),
        source=body.get("source", "")
    )
    return {"status": "ok", "id": doc_id, "total": len(kb.docs)}

@app.post("/knowledge/search")
async def search_knowledge(req: Request):
    body = await req.json()
    results = kb.search(body.get("query", ""), top_k=body.get("top_k", 5))
    return {"results": results, "count": len(results)}

@app.post("/agents/{name}/chat")
async def chat_with_agent(name: str, req: Request):
    body = await req.json()
    message = body.get("message", "")
    
    agents = load_agents()
    if name not in agents:
        raise HTTPException(404, f"智能体 '{name}' 不存在")
    
    agent = agents[name]
    system_prompt = agent.get("instructions", f"你是{name}。")
    model = agent.get("model", "deepseek-v4-pro")
    
    # 检索知识库
    kb_results = kb.search(message, top_k=3)
    if kb_results:
        system_prompt += f"\n\n相关知识：\n" + "\n".join([f"- {d}" for d in kb_results])
    
    response = call_llm(
        [{"role": "system", "content": system_prompt},
         {"role": "user", "content": message}],
        model=model
    )
    
    return {"agent": name, "model": model, "response": response}

# ─── Web 界面 ───────

# ═══════════════════════════════════════
# 智能体进化系统
# ═══════════════════════════════════════

class EvolutionSystem:
    """智能体自我进化系统
    每次对话后自动学习 → 保存知识 → 生成 skill → 下次直接用
    """
    
    def __init__(self):
        self.skills_dir = DATA_DIR / "skills"
        self.evolution_log = DATA_DIR / "evolution.json"
        self.skills_dir.mkdir(exist_ok=True)
        self.learned_patterns = self._load_evolution_log()
    
    def _load_evolution_log(self) -> List[Dict]:
        if self.evolution_log.exists():
            try: return json.loads(open(self.evolution_log).read())
            except: pass
        return []
    
    def _save_evolution_log(self):
        with open(self.evolution_log, "w") as f:
            json.dump(self.learned_patterns[-100:], f, ensure_ascii=False, indent=2)
    
    async def learn_from_interaction(self, task: str, agent_name: str, response: str):
        """从一次交互中学习"""
        
        # 1. 提取可学习的知识点
        learn_prompt = f"""分析以下智能体交互，提取值得学习的知识点：

任务：{task}
智能体：{agent_name}
回复：{response[:500]}

请判断：
1. 这次交互中有什么值得记住的知识？
2. 有没有新的技能或模式？
3. 下次遇到类似情况应该怎么做？

如果没有什么值得学习的，返回：{{"learn": false}}
如果有，返回：{{"learn": true, "knowledge": "知识点", "tags": ["标签"], "skill": "技能描述"}}"""

        analysis = call_llm_fast(
            [{"role": "user", "content": learn_prompt}],
            model="deepseek-v4-pro"
        )
        
        try:
            # 提取 JSON
            m = re.search(r'\{.*\}', analysis, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                if data.get("learn"):
                    # 保存到知识库
                    knowledge = data.get("knowledge", "")
                    tags = data.get("tags", [])
                    skill = data.get("skill", "")
                    
                    if knowledge:
                        kb.add(knowledge, tags=tags + [agent_name, "auto_learned"], 
                               source=f"evolution:{agent_name}")
                    
                    # 记录进化日志
                    entry = {
                        "time": datetime.now().isoformat(),
                        "agent": agent_name,
                        "task": task[:100],
                        "knowledge": knowledge[:200],
                        "skill": skill[:200],
                        "tags": tags
                    }
                    self.learned_patterns.append(entry)
                    self._save_evolution_log()
                    
                    return entry
        except:
            pass
        return None
    
    def get_stats(self) -> Dict:
        """获取进化统计"""
        return {
            "total_learned": len(self.learned_patterns),
            "skills_count": len(list(self.skills_dir.glob("*.md"))),
            "recent_learnings": self.learned_patterns[-5:],
            "knowledge_base_size": len(kb.docs)
        }
    
    def get_evolution_summary(self) -> str:
        """生成进化摘要"""
        if not self.learned_patterns:
            return "还没有学到任何东西，开始对话让我成长！"
        
        summary = f"🧬 进化统计：\n"
        summary += f"- 累计学习次数：{len(self.learned_patterns)}\n"
        summary += f"- 知识库文档：{len(kb.docs)} 条\n"
        
        # 按智能体统计
        agent_stats = {}
        for entry in self.learned_patterns:
            agent = entry.get("agent", "unknown")
            agent_stats[agent] = agent_stats.get(agent, 0) + 1
        
        summary += "- 各智能体学习情况：\n"
        for agent, count in sorted(agent_stats.items(), key=lambda x: -x[1]):
            summary += f"  · {agent}: {count} 次\n"
        
        # 最近的学习
        recent = self.learned_patterns[-3:]
        if recent:
            summary += "\n最近学到：\n"
            for r in recent:
                summary += f"  · {r.get('knowledge','')[:80]}...\n"
        
        return summary

evo = EvolutionSystem()

@app.get("/evolution")
async def get_evolution():
    """获取进化状态"""
    return evo.get_stats()

@app.get("/evolution/summary")
async def evolution_summary():
    return {"summary": evo.get_evolution_summary()}

@app.get("/system/stats")
async def system_stats():
    """系统统计"""
    agent_count = len(load_agents())
    return {
        "agents": agent_count,
        "knowledge_docs": len(kb.docs),
        "cache_size": cache.stats()["size"],
        "cache_max": cache.stats()["max_size"],
        "evolution_count": evo.get_stats()["total_learned"],
        "uptime": "运行中"
    }

@app.post("/cluster/run")
async def run_cluster(req: Request):
    """集群运行 - 多轮反馈调度 + 进化机制"""
    body = await req.json()
    task = body.get("task", "")
    session_id = body.get("session_id", f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    if not task:
        return {"error": "请输入任务"}
    
    agents = load_agents()
    agent_list = list(agents.keys())
    agents_info = get_agents_info()
    
    # 检索知识库
    kb_results = kb.search(task, top_k=5)
    kb_context = "\n".join([f"- {d}" for d in kb_results]) if kb_results else ""
    
    # ═══ 第1轮：Orchestrator 分析 ═══
    orchestrator_prompt = ORCHESTRATOR_PROMPT.replace("{agents_info}", agents_info)
    if kb_context:
        orchestrator_prompt += f"\n\n## 相关知识库\n{kb_context}"
    
    analysis = call_llm_fast(
        [{"role": "system", "content": orchestrator_prompt},
         {"role": "user", "content": task}],
        model="deepseek-v4-pro"
    )
    
    plan = parse_plan(analysis)
    
    # ═══ 第2轮：执行计划 ═══
    all_results = []
    all_rounds = []
    
    for round_num in range(3):  # 最多3轮迭代
        if not plan or "plan" not in plan:
            break
        
        round_results = []
        for step in plan["plan"]:
            agent_name = step.get("agent", "")
            subtask = step.get("task", "")
            
            if agent_name in agents:
                agent = agents[agent_name]
                prompt = agent.get("instructions", f"你是{agent_name}。")
                
                # 注入知识库 + 前几轮的结果作为上下文
                agent_kb = kb.search(subtask, top_k=3)
                if agent_kb:
                    prompt += "\n\n相关知识：\n" + "\n".join([f"- {d}" for d in agent_kb])
                if all_results:
                    prompt += "\n\n之前已完成的工作：\n" + "\n".join([f"- [{r['agent']}] {r['result'][:200]}" for r in all_results])
                
                resp = call_llm(
                    [{"role": "system", "content": prompt},
                     {"role": "user", "content": subtask}],
                    model=agent.get("model", "deepseek-v4-pro")
                )
                round_results.append({"agent": agent_name, "task": subtask, "result": resp})
                
                # 进化学习
                await evo.learn_from_interaction(subtask, agent_name, resp)
            else:
                round_results.append({"agent": agent_name, "task": subtask, "result": "智能体不存在"})
        
        all_results.extend(round_results)
        all_rounds.append({"round": round_num + 1, "results": round_results})
        
        # ═══ 第3轮：Orchestrator 检查是否需要继续 ═══
        if round_num < 2:  # 最多反馈2次
            summary = "\n".join([f"- [{r['agent']}] {r.get('result','')[:200]}" for r in round_results])
            
            review_prompt = f"""你是总指挥，请审查以下智能体的工作成果：

任务：{task}
完成情况：
{summary}

请判断：
1. 任务是否已经完成？(yes/no)
2. 如果未完成，还需要什么？
3. 如果需要继续，下一步应该分配给谁？

只返回JSON：{{"done": true/false, "next_task": "如果需要继续的任务", "next_agent": "智能体名称", "reason": "原因"}}"""
            
            review = call_llm_fast(
                [{"role": "user", "content": review_prompt}],
                model="deepseek-v4-pro"
            )
            
            try:
                m = re.search(r'\{.*\}', review, re.DOTALL)
                if m:
                    review_data = json.loads(m.group(0))
                    if review_data.get("done"):
                        break  # 任务完成，退出循环
                    elif review_data.get("next_agent") and review_data.get("next_task"):
                        # 继续下一轮
                        plan = {"plan": [{"agent": review_data["next_agent"], "task": review_data["next_task"]}]}
                        continue
            except:
                pass
        
        break  # 默认退出
    
    # 全局学习
    await evo.learn_from_interaction(task, "Orchestrator", analysis)
    
    save_chat(session_id, {"role": "user", "content": task, "time": datetime.now().isoformat()})
    
    return {
        "session_id": session_id,
        "task": task,
        "orchestration": analysis,
        "plan": plan,
        "rounds": all_rounds,
        "results": all_results,
        "knowledge_used": kb_results,
        "evolution": evo.get_stats(),
        "agents_involved": agent_list
    }

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/web", response_class=HTMLResponse)
async def web_ui():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse("<h1>前端文件未找到</h1>", status_code=404)

# ═══════════════════════════════════════
if __name__ == "__main__":
    agents = load_agents()
    print(f"🚀 Hermes 智能体管理平台 v3.0")
    print(f"📂 智能体: {', '.join(a['name'] for a in agents.values())}")
    print(f"📚 知识库: {len(kb.docs)} 条文档")
    print(f"🌐 Web 界面: http://localhost:8000/web")
    uvicorn.run(app, host="0.0.0.0", port=8000)
