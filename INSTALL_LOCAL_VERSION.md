# Install Graphiti Local Memory

Quick-start guide for the local-only version of Graphiti designed for locked-down work environments.

## What This Is

A knowledge graph that runs 100% locally on your Mac:
- **No API keys** - No LLM or embedding calls
- **No Docker** - Uses embedded Kuzu database
- **No admin rights** - Pure Python install
- **For Codex** - Designed to work with the Codex Mac app over MCP

## One-Line Install

**For testing (before PR merge):**

```bash
pip install "git+https://github.com/chandsethi/graphiti.git@cursor/local-memory-agent-90d5#subdirectory=mcp_server_local"
```

**After PR merge:**

```bash
pip install "git+https://github.com/chandsethi/graphiti.git#subdirectory=mcp_server_local"
```

Or with `pipx` (recommended for isolated installs):

```bash
pipx install "git+https://github.com/chandsethi/graphiti.git@cursor/local-memory-agent-90d5#subdirectory=mcp_server_local"
```

This installs the `graphiti-local-mcp` command.

## Configure Codex

Add this to your `~/.codex/config.toml`:

```toml
[mcp_servers.graphiti-local]
command = "graphiti-local-mcp"
```

If the command isn't found after install, use the full path:

```bash
which graphiti-local-mcp
# Example output: /Users/yourname/.local/bin/graphiti-local-mcp
```

Then use the full path in your config:

```toml
[mcp_servers.graphiti-local]
command = "/Users/yourname/.local/bin/graphiti-local-mcp"
```

## Restart Codex

Restart the Codex app to pick up the new MCP server.

## Verify It Works

In Codex, try:
```
Remember this fact: I prefer Python for backend work.

What are my tech preferences?
```

Codex should call the MCP tools and store/retrieve the memory.

## Data Location

All data is stored in `~/.graphiti-local/`

To backup:
```bash
cp -r ~/.graphiti-local/ ~/backup-graphiti-local/
```

To reset:
```bash
graphiti-local-mcp reset --yes
```

## For Codex: Integration Prompt

See `mcp_server_local/CODEX_GUIDE.md` for a prompt snippet to help Codex use the memory system effectively. Add it to your Codex `AGENTS.md` or system prompt.

## Requirements

- macOS (tested on 13+) or Linux
- Python 3.10 or higher
- pip or pipx

## Manual Install (Development)

If you want to install from a local clone:

```bash
git clone https://github.com/chandsethi/graphiti.git
cd graphiti/mcp_server_local
pip install -e .
```

## CLI Commands

```bash
# Run the MCP server (default)
graphiti-local-mcp

# Reset all data (DANGEROUS)
graphiti-local-mcp reset --yes

# Help
graphiti-local-mcp --help
```

## Troubleshooting

**"command not found: graphiti-local-mcp"**
- Make sure pip's bin directory is on your PATH
- Use `which graphiti-local-mcp` to find the full path
- Or reinstall with `pipx` which handles PATH automatically

**Codex doesn't see the tools**
- Check the path in config.toml is correct
- Restart Codex after config changes
- Check Codex logs for connection errors

**Data isn't persisting**
- Check `~/.graphiti-local/` exists and is writable
- Try `graphiti-local-mcp reset --yes` to recreate the database

## What You Get

8 MCP tools for Codex:
- `add_memory` - Store facts/plans/ideas
- `search_memory` - Query with filters
- `get_entity_neighborhood` - Explore entity connections
- `update_plan_status` - Mark plans done/dropped
- `supersede_plan` - Update plans with history
- `promote_idea` - Convert ideas to facts/plans
- `mark_fact_correction` - Flag corrected facts
- `list_recent` - Browse recent memories

No network calls, ever. Verified by tests.

## License

Apache 2.0 (same as parent Graphiti project)
