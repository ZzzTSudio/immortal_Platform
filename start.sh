#!/bin/bash

# Agent Immortal 一键启动脚本

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo -e "${GREEN}=== Agent Immortal 启动脚本 ===${NC}"

# 加载本地环境变量（可放 RAG_SILICONFLOW_API_KEY 等私密配置）
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}加载 .env...${NC}"
    set -a
    # shellcheck disable=SC1091
    . "$PROJECT_ROOT/.env"
    set +a
fi

# 加载 nvm
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    echo -e "${YELLOW}加载 nvm...${NC}"
    \. "$NVM_DIR/nvm.sh"
    nvm use 22 > /dev/null 2>&1 || nvm install 22
    export PATH="$(dirname "$(nvm which 22)"):$PATH"
fi

# 检查 Node.js 版本
NODE_VERSION_RAW=$(node --version | cut -d'v' -f2)
NODE_MAJOR=$(echo "$NODE_VERSION_RAW" | cut -d'.' -f1)
NODE_MINOR=$(echo "$NODE_VERSION_RAW" | cut -d'.' -f2)
if [ "$NODE_MAJOR" -lt 22 ] || { [ "$NODE_MAJOR" -eq 22 ] && [ "$NODE_MINOR" -lt 14 ]; }; then
    echo -e "${RED}错误: Node.js 版本过低 (当前: $(node --version))${NC}"
    echo -e "${RED}需要 Node.js 22.14+ 版本${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Node.js 版本: $(node --version)${NC}"

# 构建前端
echo -e "${YELLOW}构建前端...${NC}"
cd "$PROJECT_ROOT/web"

if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}安装前端依赖...${NC}"
    npm install
fi

echo -e "${YELLOW}编译前端代码...${NC}"
npm run build

if [ ! -d "dist" ]; then
    echo -e "${RED}错误: 前端构建失败，dist 目录不存在${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 前端构建完成${NC}"

# 启动后端
cd "$PROJECT_ROOT"
echo -e "${YELLOW}启动后端服务...${NC}"

PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON_BIN" ]; then
    echo -e "${RED}错误: 未找到 Python，请先安装 Python 3${NC}"
    exit 1
fi

# 设置环境变量
export IMMORTAL_HOST="${IMMORTAL_HOST:-0.0.0.0}"
export IMMORTAL_PORT="${IMMORTAL_PORT:-8030}"
export RAG_QDRANT_MODE="${RAG_QDRANT_MODE:-local}"
export RAG_QDRANT_PATH="${RAG_QDRANT_PATH:-data/qdrant}"

if [ -z "${RAG_SILICONFLOW_API_KEY:-}" ] && [ -z "${CYBER_COLLEAGUE_API_KEY:-}" ]; then
    echo -e "${YELLOW}提示: 未设置 RAG_SILICONFLOW_API_KEY，RAG 上传/检索会在调用 Embedding 时失败。${NC}"
fi

echo -e "${GREEN}✓ 后端服务启动中...${NC}"
echo -e "${GREEN}访问地址: http://localhost:${IMMORTAL_PORT}${NC}"
echo -e "${GREEN}Qdrant: ${RAG_QDRANT_MODE} (${RAG_QDRANT_PATH})${NC}"
echo -e "${YELLOW}按 Ctrl+C 停止服务${NC}"

# 启动后端
"$PYTHON_BIN" -m app.web
