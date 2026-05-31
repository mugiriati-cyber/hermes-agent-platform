#!/usr/bin/env python3
"""
Agent Gateway v1.0 — Hermes ↔ AI 通信桥梁

GitHub 管代码，Hermes 管执行，Gateway 管调用，AI 管分析与生成。

单接口设计：POST /agent/run
认证：Bearer Token
日志：每次请求完整记录
"""
import os, sys, json, re, time
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import uvicorn

# ═══════════════════════════════════════
# 配置
# ═══════════════════════════════════════

GATEWAY_DIR = Path("/home/admin/hermes-platform/gateway")
LOG_DIR = GATEWAY_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Token — 第一版写死在环境变量，后续可升级
GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "hermes-trae-gateway-v1")

# DeepSeek API
def get_deepseek_key():
    try:
        d = json.load(open("/home/admin/.hermes/auth.json"))
        for cred in d.get('credential_pool', {}).get('deepseek', []):
            return cred['access_token']
    except:
        pass
    return os.environ.get("DEEPSEEK_API_KEY", "")

DEEPSEEK_API_KEY = get_deepseek_key()
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# ═══════════════════════════════════════
# 数据模型（按 Trae 方案设计）
# ═══════════════════════════════════════

class AgentRunRequest(BaseModel):
    """POST /agent/run 请求体"""
    task: str = Field(..., description="任务描述，如：修复这个bug、添加登录功能")
    context: Dict[str, Any] = Field(default_factory=dict, description="上下文")
    files: Optional[List[Dict]] = Field(None, description="相关文件，每项包含 path 和 content")
    constraints: Optional[List[str]] = Field(None, description="约束条件，如：不要改数据库结构")
    history: Optional[List[Dict]] = Field(None, description="历史消息")

class AgentRunResponse(BaseModel):
    """POST /agent/run 响应体"""
    summary: str = Field(..., description="概要说明")
    analysis: str = Field("", description="详细分析")
    patch: Optional[str] = Field(None, description="代码补丁（标准 diff 格式）")
    commands: Optional[List[str]] = Field(None, description="建议执行的命令")
    risks: Optional[List[str]] = Field(None, description="风险提示")
    reasoning: Optional[str] = Field(None, description="AI 思考过程预览")

# ═══════════════════════════════════════
# 系统提示
# ═══════════════════════════════════════

AGENT_SYSTEM_PROMPT = """你是一个 AI 开发助手，与远程执行环境协作完成开发任务。

## 你的职责
- 分析任务和上下文
- 生成代码补丁
- 提供审查意见
- 建议下一步操作

## 输出格式要求
你必须返回严格的 JSON 格式，不要包含其他内容：
{
  "summary": "一句话概括你做了什么",
  "analysis": "详细分析过程",
  "patch": "代码补丁（diff格式），如果没有修改则留空",
  "commands": ["建议执行的shell命令"],
  "risks": ["风险提示"]
}

## 注意事项
- patch 使用标准的 unified diff 格式
- 如果没有代码修改，patch 设为空字符串
- commands 列出建议 Hermes 执行的验证命令
- risks 列出可能的副作用"""

# ═══════════════════════════════════════
# FastAPI
# ═══════════════════════════════════════

app = FastAPI(title="Agent Gateway", version="1.0",
              description="Hermes ↔ AI 通信桥梁")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

security = HTTPBearer(auto_error=False)

def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Bearer Token 鉴权"""
    if not credentials:
        raise HTTPException(401, "缺少 Authorization: Bearer <token>")
    if credentials.credentials != GATEWAY_TOKEN:
        raise HTTPException(403, "Token 无效")
    return credentials

def call_llm(messages: List[Dict]) -> tuple:
    """调用 deepseek-v4-pro 思考模式"""
    from openai import OpenAI
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    try:
        resp = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=messages,
            temperature=0.3,
            max_tokens=8192,
            reasoning_effort="high"
        )
        content = resp.choices[0].message.content
        rc = getattr(resp.choices[0].message, 'reasoning_content', None) or ""
        return content, rc
    except Exception as e:
        error_json = json.dumps({
            "summary": f"AI 调用失败: {str(e)}",
            "analysis": "",
            "patch": "",
            "commands": [],
            "risks": ["AI 服务暂时不可用"]
        })
        return error_json, ""

def parse_agent_response(text: str) -> dict:
    """解析 AI 返回的 JSON"""
    # 优先从 ```json 块提取
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1))
        except: pass
    
    # 尝试全文 JSON
    start, end = text.find('{'), text.rfind('}')
    if start != -1 and end != -1:
        try:
            data = json.loads(text[start:end+1])
            if "summary" in data:
                return data
        except: pass
    
    # 兜底
    return {
        "summary": text[:500],
        "analysis": "",
        "patch": "",
        "commands": [],
        "risks": []
    }

def log_request(task: str, resp: dict, duration: float):
    """记录审计日志"""
    entry = {
        "time": datetime.now().isoformat(),
        "task_preview": task[:100],
        "duration_sec": round(duration, 2),
        "has_patch": bool(resp.get("patch")),
        "commands_count": len(resp.get("commands", [])),
        "summary_preview": resp.get("summary", "")[:100]
    }
    log_file = LOG_DIR / f"{datetime.now().strftime('%Y%m%d')}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

# ═══════════════════════════════════════
# API — 核心单接口
# ═══════════════════════════════════════

@app.get("/")
async def root():
    return {
        "service": "Agent Gateway",
        "version": "1.0",
        "status": "running",
        "model": "deepseek-v4-pro (reasoning)"
    }

@app.post("/agent/run", response_model=AgentRunResponse)
async def agent_run(req: AgentRunRequest, auth=Depends(verify_token)):
    """核心接口：Hermes 调用 AI 完成任务"""
    start_time = time.time()
    
    # 构建上下文
    context_parts = [f"## 任务\n{req.task}\n"]
    
    if req.context:
        context_parts.append("## 上下文")
        for key, value in req.context.items():
            val_str = str(value)
            if len(val_str) > 3000:
                val_str = val_str[:3000] + "..."
            context_parts.append(f"### {key}\n```\n{val_str}\n```")
    
    if req.files:
        context_parts.append(f"\n## 相关文件（{len(req.files)}个）")
        for f in req.files[:10]:  # 最多10个
            content = f.get("content", "")
            if len(content) > 2000:
                content = content[:2000] + "\n...（截断）"
            context_parts.append(f"### {f.get('path', 'unknown')}\n```\n{content}\n```")
    
    if req.constraints:
        context_parts.append("\n## 约束条件\n" + "\n".join(f"- {c}" for c in req.constraints))
    
    context_str = "\n".join(context_parts)
    
    # 构建消息
    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    
    if req.history:
        for h in req.history[-5:]:
            messages.append(h)
    
    messages.append({"role": "user", "content": context_str})
    
    # 调用 AI
    response, reasoning = call_llm(messages)
    parsed = parse_agent_response(response)
    
    # 日志
    duration = time.time() - start_time
    log_request(req.task, parsed, duration)
    
    return {
        "summary": parsed.get("summary", ""),
        "analysis": parsed.get("analysis", ""),
        "patch": parsed.get("patch"),
        "commands": parsed.get("commands", []),
        "risks": parsed.get("risks", []),
        "reasoning": reasoning[:800] if reasoning else ""
    }

# ═══════════════════════════════════════
if __name__ == "__main__":
    print(f"🚀 Agent Gateway v1.0")
    print(f"📡 端口: 8001")
    print(f"🔑 Token: {GATEWAY_TOKEN}")
    print(f"🧠 模型: deepseek-v4-pro (思考模式)")
    print(f"📋 接口: POST /agent/run")
    uvicorn.run(app, host="0.0.0.0", port=8001)
