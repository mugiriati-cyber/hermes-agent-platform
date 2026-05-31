#!/usr/bin/env python3
"""
HTTP Agent Gateway v1.0
Hermes 与 Trae 之间的通信桥梁

职责：
1. 接收 Hermes 的执行上下文（日志、diff、文件内容）
2. 调用 deepseek-v4-pro 思考模式进行分析
3. 返回结构化结果（answer、patch、review、commands、next_step）
4. 记录所有交互供溯源

API 端口：8001
"""
import os, sys, json, re, time, hashlib, asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# ─── 配置 ───────
GATEWAY_DIR = Path("/home/admin/hermes-platform/gateway")
GATEWAY_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR = GATEWAY_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 从 auth.json 获取 API key
def get_deepseek_key():
    try:
        import json
        d = json.load(open("/home/admin/.hermes/auth.json"))
        for cred in d.get('credential_pool', {}).get('deepseek', []):
            return cred['access_token']
    except:
        pass
    return os.environ.get("DEEPSEEK_API_KEY", "")

DEEPSEEK_API_KEY = get_deepseek_key()
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# ─── 数据结构 ───────

class GatewayRequest(BaseModel):
    """网关请求"""
    task_type: str = "analyze"  # analyze | code | review | debug | plan
    context: Dict[str, Any] = {}  # 上下文：日志、diff、文件内容
    files: Optional[List[Dict]] = None  # 相关文件
    history: Optional[List[Dict]] = None  # 历史交互

class GatewayResponse(BaseModel):
    """网关结构化响应"""
    type: str  # answer | patch | review | commands | next_step | error
    content: str  # 主要内容
    structured: Optional[Dict] = None  # 结构化数据
    suggested_actions: Optional[List[str]] = None  # 建议操作
    confidence: float = 0.8

# ─── 系统提示词 ───────

SYSTEM_PROMPTS = {
    "analyze": """你是一个 AI 架构师，负责分析问题和制定方案。
请分析提供的上下文，给出：
1. 问题分析
2. 解决方案
3. 建议的下一步

返回 JSON 格式：
{"type": "answer", "content": "分析结果", "structured": {"问题": "..", "方案": ".."}, "suggested_actions": ["动作1", "动作2"]}""",

    "code": """你是一个资深程序员，负责编写代码。
根据任务描述和上下文，生成代码。
如果需要修改现有文件，返回 patch 格式。

返回 JSON 格式：
{"type": "patch", "content": "代码说明", "structured": {"file": "路径", "changes": "修改内容", "new_code": "新代码"}, "suggested_actions": ["动作1"]}""",

    "review": """你是一个代码审查者，负责审查代码质量。
检查：逻辑错误、性能问题、安全隐患、代码风格。

返回 JSON 格式：
{"type": "review", "content": "审查结论", "structured": {"issues": ["问题1"], "suggestions": ["建议1"], "rating": "A/B/C/D"}, "suggested_actions": ["动作1"]}""",

    "debug": """你是一个调试专家，负责分析错误和异常。
分析错误日志、堆栈跟踪，找出根本原因。

返回 JSON 格式：
{"type": "answer", "content": "调试分析", "structured": {"root_cause": "根本原因", "fix": "修复方案"}, "suggested_actions": ["动作1"]}""",

    "plan": """你是一个项目经理，负责制定开发计划。
根据需求拆解任务，排定优先级，估算工作量。

返回 JSON 格式：
{"type": "next_step", "content": "计划概述", "structured": {"tasks": [{"name": "任务", "priority": "高/中/低", "estimate": "预估时间"}], "timeline": "时间线"}, "suggested_actions": ["动作1"]}"""
}

# ─── FastAPI ───────

app = FastAPI(title="HTTP Agent Gateway", version="1.0",
              description="Hermes ↔ Trae 通信网关")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

def call_llm(messages, max_tokens=8192):
    """调用 deepseek-v4-pro"""
    from openai import OpenAI
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    try:
        resp = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=messages,
            temperature=0.3,
            max_tokens=max_tokens,
            reasoning_effort="high"
        )
        content = resp.choices[0].message.content
        
        # 提取思考过程
        rc = getattr(resp.choices[0].message, 'reasoning_content', None) or ""
        return content, rc
    except Exception as e:
        return f'{{"type":"error","content":"调用失败: {e}","structured":{{}},"suggested_actions":[]}}', ""

def parse_response(text):
    """解析 AI 返回的 JSON"""
    # 尝试从 ```json 块中提取
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1))
        except: pass
    
    # 尝试全文解析
    start, end = text.find('{'), text.rfind('}')
    if start != -1 and end != -1:
        try:
            data = json.loads(text[start:end+1])
            if "type" in data:
                return data
        except: pass
    
    # 兜底
    return {"type": "answer", "content": text[:1000], "structured": {}, "suggested_actions": []}

# ═══════════════════════════════════════
# API
# ═══════════════════════════════════════

@app.get("/")
async def root():
    return {
        "service": "HTTP Agent Gateway",
        "version": "1.0",
        "status": "running",
        "model": "deepseek-v4-pro (reasoning)",
        "task_types": list(SYSTEM_PROMPTS.keys())
    }

@app.post("/v1/chat")
async def chat_gateway(req: GatewayRequest):
    """统一的网关入口"""
    
    task_type = req.task_type
    context = req.context
    files = req.files or []
    history = req.history or []
    
    # 构建上下文
    context_str = f"## 任务类型：{task_type}\n\n"
    
    if context:
        context_str += "## 上下文\n"
        for key, value in context.items():
            if isinstance(value, str) and len(value) > 2000:
                context_str += f"### {key}\n```\n{value[:2000]}...\n```\n"
            else:
                context_str += f"### {key}\n```\n{value}\n```\n"
    
    if files:
        context_str += "\n## 相关文件\n"
        for f in files:
            content = f.get("content", "")[:2000]
            context_str += f"### {f.get('path', 'unknown')}\n```\n{content}\n```\n"
    
    # 系统提示
    system_prompt = SYSTEM_PROMPTS.get(task_type, SYSTEM_PROMPTS["analyze"])
    
    messages = [
        {"role": "system", "content": f"{system_prompt}\n\n使用 deepseek-v4-pro 思考模式，返回结构化 JSON。"},
    ]
    
    # 历史
    for h in history[-5:]:
        messages.append(h)
    
    messages.append({"role": "user", "content": context_str})
    
    # 调用模型
    response, reasoning = call_llm(messages)
    
    # 解析结果
    parsed = parse_response(response)
    
    # 记录日志
    log_entry = {
        "time": datetime.now().isoformat(),
        "task_type": task_type,
        "context_keys": list(context.keys()),
        "response_type": parsed.get("type", "unknown"),
        "response_preview": parsed.get("content", "")[:200],
    }
    
    log_file = LOG_DIR / f"{datetime.now().strftime('%Y%m%d')}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    return {
        "type": parsed.get("type", "answer"),
        "content": parsed.get("content", response[:1000]),
        "structured": parsed.get("structured", {}),
        "suggested_actions": parsed.get("suggested_actions", []),
        "confidence": parsed.get("confidence", 0.8),
        "reasoning_preview": reasoning[:500] if reasoning else ""
    }

@app.post("/v1/analyze")
async def analyze(req: Request):
    """快捷接口：分析问题"""
    body = await req.json()
    return await chat_gateway(GatewayRequest(
        task_type="analyze",
        context=body.get("context", {}),
        files=body.get("files"),
        history=body.get("history")
    ))

@app.post("/v1/review")
async def review(req: Request):
    """快捷接口：审查代码"""
    body = await req.json()
    return await chat_gateway(GatewayRequest(
        task_type="review",
        context=body.get("context", {}),
        files=body.get("files"),
        history=body.get("history")
    ))

@app.get("/v1/logs")
async def get_logs(date: str = None):
    """查看网关调用日志"""
    if date:
        log_file = LOG_DIR / f"{date}.jsonl"
    else:
        # 最新的
        logs = sorted(LOG_DIR.glob("*.jsonl"), reverse=True)
        log_file = logs[0] if logs else None
    
    if not log_file or not log_file.exists():
        return {"logs": [], "count": 0}
    
    logs = []
    with open(log_file) as f:
        for line in f:
            if line.strip():
                logs.append(json.loads(line))
    
    return {"logs": logs[-20:], "count": len(logs), "file": log_file.name}

@app.get("/v1/stats")
async def get_stats():
    """网关统计"""
    total = 0
    by_type = {}
    today = datetime.now().strftime('%Y%m%d')
    
    for log_file in LOG_DIR.glob("*.jsonl"):
        with open(log_file) as f:
            for line in f:
                if line.strip():
                    total += 1
                    entry = json.loads(line)
                    t = entry.get("response_type", "unknown")
                    by_type[t] = by_type.get(t, 0) + 1
    
    return {
        "total_calls": total,
        "by_type": by_type,
        "today": today,
        "model": "deepseek-v4-pro"
    }

# ═══════════════════════════════════════
if __name__ == "__main__":
    print(f"🚀 HTTP Agent Gateway v1.0")
    print(f"📡 端口: 8001")
    print(f"🧠 模型: deepseek-v4-pro (思考模式)")
    print(f"📋 任务类型: {', '.join(SYSTEM_PROMPTS.keys())}")
    uvicorn.run(app, host="0.0.0.0", port=8001)
