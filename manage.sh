#!/usr/bin/env bash
# Hermes 智能体管理平台 - 管理脚本
# 支持：启动、停止、重启、状态、日志
set -e

PROJECT_DIR="/home/admin/hermes-platform/agents_api"
LOG_FILE="/tmp/hermes-platform.log"
PID_FILE="/tmp/hermes-platform.pid"
PYTHON="/home/admin/praison-env/bin/python"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

case "${1:-status}" in
  start)
    echo -e "${GREEN}🚀 启动 Hermes 智能体管理平台...${NC}"
    
    # 检查是否已在运行
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
      echo -e "${YELLOW}⚠️ 平台已在运行 (PID: $(cat $PID_FILE))${NC}"
      exit 0
    fi
    
    # 从 auth.json 获取 key
    DEEPSEEK_KEY=$(python3 -c "
import json
d = json.load(open('/home/admin/.hermes/auth.json'))
for cred in d['credential_pool']['deepseek']:
    print(cred['access_token'])
    break
" 2>/dev/null)
    
    if [ -z "$DEEPSEEK_KEY" ]; then
      echo -e "${RED}❌ 无法获取 DEEPSEEK_API_KEY${NC}"
      exit 1
    fi
    
    cd "$PROJECT_DIR"
    export DEEPSEEK_API_KEY="$DEEPSEEK_KEY"
    export DEEPSEEK_BASE_URL="https://api.deepseek.com"
    
    nohup $PYTHON main.py > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    
    sleep 3
    if kill -0 $(cat "$PID_FILE") 2>/dev/null; then
      echo -e "${GREEN}✅ 平台启动成功 (PID: $(cat $PID_FILE))${NC}"
      echo -e "${GREEN}🌐 Web 界面: http://localhost:8000/web${NC}"
    else
      echo -e "${RED}❌ 启动失败，查看日志: tail -50 $LOG_FILE${NC}"
      exit 1
    fi
    ;;
    
  stop)
    if [ -f "$PID_FILE" ]; then
      PID=$(cat "$PID_FILE")
      echo -e "${YELLOW}🛑 停止平台 (PID: $PID)...${NC}"
      kill "$PID" 2>/dev/null || true
      rm -f "$PID_FILE"
      # 也可能有其他进程占用了 8000
      kill $(ss -tlnp | grep 8000 | grep -oP 'pid=\K[0-9]+') 2>/dev/null || true
      sleep 1
      echo -e "${GREEN}✅ 已停止${NC}"
    else
      echo -e "${YELLOW}⚠️ 平台未在运行${NC}"
    fi
    ;;
    
  restart)
    $0 stop
    sleep 2
    $0 start
    ;;
    
  status)
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
      PID=$(cat "$PID_FILE")
      echo -e "${GREEN}✅ 平台运行中 (PID: $PID)${NC}"
      curl -s http://localhost:8000/ 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  但 API 未响应"
    else
      # 检查端口
      PORT_PID=$(ss -tlnp | grep 8000 | grep -oP 'pid=\K[0-9]+' || echo "")
      if [ -n "$PORT_PID" ]; then
        echo -e "${YELLOW}⚠️ 端口 8000 被占用 (PID: $PORT_PID)，但 PID 文件丢失${NC}"
      else
        echo -e "${RED}❌ 平台未运行${NC}"
      fi
    fi
    ;;
    
  logs)
    if [ -f "$LOG_FILE" ]; then
      tail -50 "$LOG_FILE"
    else
      echo -e "${RED}❌ 日志文件不存在${NC}"
    fi
    ;;
    
  health)
    echo "=== Hermes 平台健康检查 ==="
    echo "时间: $(date)"
    echo ""
    
    # 检查 API
    API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null || echo "000")
    if [ "$API_STATUS" = "200" ]; then
      echo -e "${GREEN}✅ API 服务: 正常 ($API_STATUS)${NC}"
    else
      echo -e "${RED}❌ API 服务: 异常 ($API_STATUS)${NC}"
    fi
    
    # 检查智能体
    AGENTS=$(curl -s http://localhost:8000/agents 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('agents',[])))" 2>/dev/null || echo "0")
    echo -e "🤖 智能体数量: $AGENTS"
    
    # 检查知识库
    KB=$(curl -s http://localhost:8000/knowledge 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('count',0))" 2>/dev/null || echo "0")
    echo -e "📚 知识库文档: $KB"
    
    # 检查进化
    EVO=$(curl -s http://localhost:8000/evolution 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('total_learned',0))" 2>/dev/null || echo "0")
    echo -e "🧬 进化学习次数: $EVO"
    
    # 内存
  health)
    $0 _health_check
    ;;
    
  gateway)
    case "${2:-status}" in
      start)
        echo -e "${GREEN}🚀 启动 Agent Gateway...${NC}"
        DEEPSEEK_KEY=$(python3 -c "import json;d=json.load(open('/home/admin/.hermes/auth.json'));print([c['access_token'] for c in d['credential_pool']['deepseek']][0])" 2>/dev/null)
        cd "$PROJECT_DIR/../gateway"
        export DEEPSEEK_API_KEY="$DEEPSEEK_KEY"
        nohup $PYTHON gateway.py > /tmp/gateway.log 2>&1 &
        sleep 2
        curl -s http://localhost:8001/ >/dev/null 2>&1 && echo -e "${GREEN}✅ Gateway 启动成功 (端口 8001)${NC}" || echo -e "${RED}❌ 启动失败${NC}"
        ;;
      stop)
        kill $(ss -tlnp | grep 8001 | grep -oP 'pid=\K[0-9]+') 2>/dev/null
        echo -e "${GREEN}✅ Gateway 已停止${NC}"
        ;;
      logs)
        tail -30 /tmp/gateway.log 2>/dev/null || echo "无日志"
        ;;
      *)
        echo "用法: $0 gateway {start|stop|logs}"
        ;;
    esac
    ;;
    
  *)
    echo "用法: $0 {start|stop|restart|status|logs|health}"
    echo ""
    echo "  start   启动平台"
    echo "  stop    停止平台"
    echo "  restart 重启平台"
    echo "  status  查看运行状态"
    echo "  logs    查看日志"
    echo "  health  健康检查"
    ;;
esac
