#!/usr/bin/env bash
set -euo pipefail

echo "=== Graphiti Local Memory - Installation Script ==="
echo ""

if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed."
    echo "Install uv first: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "Installing graphiti-local..."
cd "$(dirname "$0")"
uv sync

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Add this to your ~/.codex/config.toml:"
echo ""
echo "[mcp_servers.graphiti-local]"
echo "command = \"$(which uv)\""
echo "args = ["
echo "    \"run\","
echo "    \"--directory\", \"$(pwd)\","
echo "    \"python\", \"graphiti_local/main.py\""
echo "]"
echo "env = { }  # No API keys needed!"
echo ""
echo "Then restart Codex."
echo ""
echo "Data will be stored in: ~/.graphiti-local/"
echo ""
