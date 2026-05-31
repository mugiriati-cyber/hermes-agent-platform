#!/usr/bin/env python3
"""
Hermes Agent Client — Hermes 调用 Agent Gateway 的客户端

用法：
  # 分析问题
  python3 agent_client.py analyze "数据库连接失败" --context '{"error": "..."}' --files server.py
  
  # 审查代码
  python3 agent_client.py review --diff < current.diff
  
  # 修复bug
  python3 agent_client.py fix "修复登录bug" --files auth.py --constraints "不要改数据库"
"""
import os, sys, json, argparse, subprocess, urllib.request, urllib.error
from pathlib import Path
from typing import Optional

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8001")
GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "hermes-trae-gateway-v1")

def read_file(path: str, max_len: int = 3000) -> str:
    """读取文件，自动截断"""
    p = Path(path)
    if not p.exists():
        return f"文件不存在: {path}"
    content = p.read_text(encoding="utf-8", errors="ignore")
    if len(content) > max_len:
        return content[:max_len] + f"\n...（截断，共{len(content)}字）"
    return content

def get_git_diff() -> str:
    """获取当前 git diff"""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached"],  # staged changes
            capture_output=True, text=True, timeout=10
        )
        staged = result.stdout
        
        result = subprocess.run(
            ["git", "diff"],  # unstaged changes
            capture_output=True, text=True, timeout=10
        )
        unstaged = result.stdout
        
        diff = staged + unstaged
        if not diff.strip():
            return ""
        if len(diff) > 5000:
            diff = diff[:5000] + f"\n...（diff 过长，截断）"
        return diff
    except:
        return ""

def call_gateway(task: str, context: dict = None, files: list = None,
                 constraints: list = None) -> dict:
    """调用 Agent Gateway（使用 urllib）"""
    payload = {
        "task": task,
        "context": context or {},
        "files": files or [],
        "constraints": constraints or []
    }
    
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{GATEWAY_URL}/agent/run",
        data=data,
        headers={
            "Authorization": f"Bearer {GATEWAY_TOKEN}",
            "Content-Type": "application/json"
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"summary": f"HTTP {e.code}: {e.read().decode()[:200]}",
                "analysis": "", "patch": None, "commands": [], "risks": []}
    except Exception as e:
        return {"summary": f"请求失败: {e}", "analysis": "", "patch": None,
                "commands": [], "risks": []}

def cmd_analyze(args):
    """分析问题"""
    files = []
    if args.files:
        for f in args.files:
            files.append({"path": f, "content": read_file(f)})
    
    context = {}
    if args.context:
        try:
            context = json.loads(args.context)
        except:
            context = {"raw": args.context}
    
    if args.diff:
        context["diff"] = args.diff
    else:
        diff = get_git_diff()
        if diff:
            context["current_diff"] = diff
    
    print(f"🔍 分析: {args.task}")
    result = call_gateway(args.task, context, files, args.constraints)
    
    print(f"\n{'='*50}")
    print(f"📋 {result.get('summary', '无结果')}")
    print(f"{'='*50}")
    
    if result.get('analysis'):
        print(f"\n📝 分析:\n{result['analysis']}")
    
    if result.get('patch'):
        print(f"\n💾 补丁:\n{result['patch']}")
    
    if result.get('commands'):
        print(f"\n⚡ 建议命令:")
        for cmd in result['commands']:
            print(f"  $ {cmd}")
    
    if result.get('risks'):
        print(f"\n⚠️ 风险:")
        for r in result['risks']:
            print(f"  - {r}")
    
    if result.get('reasoning'):
        print(f"\n🧠 思考过程:\n{result['reasoning'][:300]}...")

def cmd_review(args):
    """审查代码"""
    files = []
    if args.files:
        for f in args.files:
            files.append({"path": f, "content": read_file(f)})
    
    context = {}
    if args.diff:
        context["diff"] = args.diff
    else:
        diff = get_git_diff()
        if diff:
            context["current_diff"] = diff
    
    task = f"审查以下代码，检查逻辑错误、性能问题、安全隐患：\n{args.task or ''}"
    print(f"🔍 审查代码...")
    result = call_gateway(task, context, files)
    
    print(f"\n{'='*50}")
    print(f"📋 审查结论: {result.get('summary', '')}")
    print(f"{'='*50}")
    
    if result.get('analysis'):
        print(f"\n{result['analysis']}")

def cmd_fix(args):
    """修复问题"""
    files = []
    if args.files:
        for f in args.files:
            files.append({"path": f, "content": read_file(f)})
    
    context = {}
    if args.diff:
        context["diff"] = args.diff
    else:
        diff = get_git_diff()
        if diff:
            context["current_diff"] = diff
    
    print(f"🔧 修复: {args.task}")
    result = call_gateway(args.task, context, files, args.constraints)
    
    print(f"\n{'='*50}")
    print(f"📋 {result.get('summary', '')}")
    print(f"{'='*50}")
    
    if result.get('patch'):
        print(f"\n💾 补丁:\n{result['patch']}")
        print(f"\n❓ 是否应用这个补丁？(y/N) ", end="")
        choice = input().strip().lower()
        if choice == 'y':
            patch_file = "/tmp/hermes_patch.diff"
            with open(patch_file, "w") as f:
                f.write(result['patch'])
            subprocess.run(["git", "apply", patch_file])
            print("✅ 补丁已应用")
    
    if result.get('commands'):
        print(f"\n⚡ 建议执行:")
        for cmd in result['commands']:
            print(f"  $ {cmd}")

def main():
    parser = argparse.ArgumentParser(description="Hermes Agent Client")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # analyze
    p = subparsers.add_parser("analyze", help="分析问题")
    p.add_argument("task", help="任务描述")
    p.add_argument("--context", help="上下文 JSON")
    p.add_argument("--files", nargs="*", help="相关文件")
    p.add_argument("--diff", help="代码 diff")
    p.add_argument("--constraints", nargs="*", help="约束条件")
    
    # review
    p = subparsers.add_parser("review", help="审查代码")
    p.add_argument("task", nargs="?", default="", help="审查重点")
    p.add_argument("--files", nargs="*", help="要审查的文件")
    p.add_argument("--diff", help="代码 diff")
    
    # fix
    p = subparsers.add_parser("fix", help="修复问题")
    p.add_argument("task", help="问题描述")
    p.add_argument("--files", nargs="*", help="相关文件")
    p.add_argument("--diff", help="代码 diff")
    p.add_argument("--constraints", nargs="*", help="约束条件")
    
    args = parser.parse_args()
    
    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "review":
        cmd_review(args)
    elif args.command == "fix":
        cmd_fix(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
