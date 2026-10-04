#!/bin/bash
set -e

echo "=== Starting Stub Server ==="
python3 /workspace/enhanced_stub.py > /dev/null 2>&1 &
STUB_PID=$!
echo "Stub server PID: $STUB_PID"
sleep 2

echo ""
echo "=== Testing Graphiti MCP Server with Gateway Configuration ==="
echo ""

# Clear log
> /tmp/stub.log

# Test startup with minimal env
echo "Running: env -i HOME=$HOME PATH=/usr/local/bin:/usr/bin:/bin OPENAI_BASE_URL=http://127.0.0.1:8799/openai/v1 BIFROST_VK=vk-test-123 LLM_MODEL=openai.gpt-4o-mini EMBEDDER_MODEL=openai.text-embedding-3-small DATABASE_PROVIDER=kuzu graphiti-mcp-server"
echo ""

timeout 5 env -i HOME=$HOME PATH=/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin \
    OPENAI_BASE_URL=http://127.0.0.1:8799/openai/v1 \
    BIFROST_VK=vk-test-123 \
    LLM_MODEL=openai.gpt-4o-mini \
    EMBEDDER_MODEL=openai.text-embedding-3-small \
    DATABASE_PROVIDER=kuzu \
    graphiti-mcp-server 2>&1 | head -50 || true

echo ""
echo "=== Stub Server Log ===" 
cat /tmp/stub.log 2>/dev/null || echo "(No requests logged yet)"

echo ""
kill $STUB_PID 2>/dev/null || true
echo "Done"
