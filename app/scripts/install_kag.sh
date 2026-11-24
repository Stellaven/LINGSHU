#!/usr/bin/env bash
# KAG(OpenSPG) 依赖安装脚本 —— 与 requirements.txt 分开安装（两步顺序不可颠倒）
#
# 为什么不能写进 requirements.txt：
#   openspg-kag==0.8.0 钉死 protobuf==3.20.1 / nltk==3.8.1，与 pymilvus（需 protobuf>=5.27.2）
#   和 llama-index-core（需 nltk>=3.9.3）在同一依赖图内解析必然冲突；
#   实测 KAG 运行时（配合 PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python，main.py 已设置）
#   并不依赖旧版 protobuf/nltk，故装完后恢复新版本即可。
#
# 用法：bash scripts/install_kag.sh  （在 app 目录下执行，自动使用当前 venv）
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -d ".venv" ]; then
  PIP=".venv/bin/pip"
else
  PIP="pip"
fi

echo "[1/3] 安装 openspg-kag（会临时降级 protobuf/nltk）..."
"$PIP" install openspg-kag==0.8.0

echo "[2/3] 恢复 pymilvus / llama-index 所需的 protobuf 与 nltk 新版本..."
"$PIP" install 'protobuf>=5.27.2' 'nltk>=3.9.3'

echo "[3/3] 升级 mcp（KAG钉死的1.6.0使用了pydantic 2.11已移除的内部API，必须升级）..."
"$PIP" install -U mcp

echo "完成。验证：python -c \"import os; os.environ.setdefault('KAG_PROJECT_ID','1'); os.environ.setdefault('KAG_PROJECT_HOST_ADDR','http://127.0.0.1:8887'); from kag.builder.component.writer.kg_writer import KGWriter; print('kag OK')\""
