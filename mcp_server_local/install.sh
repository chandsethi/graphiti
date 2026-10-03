#!/usr/bin/env bash
set -euo pipefail

echo "=== Graphiti Local Memory - Installation Script ==="
echo ""

if ! command -v pip &> /dev/null && ! command -v pip3 &> /dev/null; then
    echo "Error: pip is not installed."
    echo "Install Python 3.10+ from python.org"
    exit 1
fi

# Use pip3 if available, otherwise pip
PIP_CMD="pip3"
if ! command -v pip3 &> /dev/null; then
    PIP_CMD="pip"
fi

echo "Installing graphiti-local from GitHub..."
$PIP_CMD install "git+https://github.com/chandsethi/graphiti.git#subdirectory=mcp_server_local"

echo ""
echo "=== Installation Complete ==="
echo ""
echo "The 'graphiti-local-mcp' command is now available."
echo ""

# Try to find the installed command
if command -v graphiti-local-mcp &> /dev/null; then
    COMMAND_PATH=$(which graphiti-local-mcp)
    echo "Command location: $COMMAND_PATH"
else
    echo "Note: 'graphiti-local-mcp' not found in PATH."
    echo "You may need to add pip's bin directory to your PATH."
    echo "Common locations:"
    echo "  - ~/.local/bin/graphiti-local-mcp"
    echo "  - /usr/local/bin/graphiti-local-mcp"
fi

echo ""
echo "Add this to your ~/.codex/config.toml:"
echo ""
echo "[mcp_servers.graphiti-local]"
echo "command = \"graphiti-local-mcp\""
echo "args = []"
echo "env = {}"
echo ""
echo "Or use the full path if needed:"
echo ""
if command -v graphiti-local-mcp &> /dev/null; then
    echo "[mcp_servers.graphiti-local]"
    echo "command = \"$(which graphiti-local-mcp)\""
    echo "args = []"
    echo "env = {}"
    echo ""
fi
echo "Then restart Codex."
echo ""
echo "Data will be stored in: ~/.graphiti-local/"
echo ""
echo "Reset data with: graphiti-local-mcp reset --yes"
echo ""
