# Install Graphiti Local Memory

This is the quick-start guide for the local-only version of Graphiti designed for locked-down work environments.

## What This Is

A knowledge graph that runs 100% locally on your Mac:
- **No API keys** - No LLM or embedding calls
- **No Docker** - Uses embedded Kuzu database
- **No admin rights** - Pure Python install
- **For Codex** - Designed to work with the Codex Mac app over MCP

Codex provides the structured data (entities, relationships, tags), and this server just stores and retrieves it.

## Requirements

- macOS (tested on 13+)
- Python 3.10 or higher
- Internet access for initial install (packages only, no runtime API calls)

## Installation

### Step 1: Install Python (if needed)

Check if you have Python 3.10+:
```bash
python3 --version
```

If not, download from [python.org](https://www.python.org/downloads/)

### Step 2: Install Dependencies

```bash
cd mcp_server_local
pip3 install --user pydantic python-dotenv kuzu pandas mcp
```

Or using the included install script:
```bash
cd mcp_server_local
./install.sh
```

### Step 3: Test the Installation

```bash
cd mcp_server_local
python3 -m pytest tests/
```

All tests should pass. The key test is `test_no_api_calls.py` which verifies no network calls happen.

### Step 4: Configure Codex

Add this to your `~/.codex/config.toml`:

```toml
[mcp_servers.graphiti-local]
command = "/usr/bin/python3"  # or wherever your python3 is
args = [
    "/full/path/to/graphiti/mcp_server_local/graphiti_local/main.py"
]
env = { }  # No API keys!
```

To find your python3 path:
```bash
which python3
```

To find the full path to main.py:
```bash
cd mcp_server_local && pwd
# Then add /graphiti_local/main.py to the end
```

Example result:
```toml
[mcp_servers.graphiti-local]
command = "/usr/bin/python3"
args = [
    "/Users/yourname/projects/graphiti/mcp_server_local/graphiti_local/main.py"
]
env = { }
```

### Step 5: Restart Codex

Restart the Codex app to pick up the new MCP server.

## Verify It Works

In Codex, try:
```
Remember this fact: I prefer Python for backend work.

What are my tech preferences?
```

Codex should call the `add_memory` and `search_memory` MCP tools and store/retrieve the memory.

## Data Location

All data is stored in `~/.graphiti-local/`

To backup:
```bash
cp -r ~/.graphiti-local/ ~/backup-graphiti-local/
```

To reset:
```bash
rm -rf ~/.graphiti-local/
```

## Troubleshooting

**"command not found: python3"**
- Install Python 3.10+ from python.org

**"No module named 'kuzu'"**
- Run `pip3 install --user kuzu pydantic python-dotenv pandas mcp`

**Codex doesn't see the tools**
- Check the path in config.toml is correct
- Make sure you restarted Codex
- Check Codex logs for errors

**Tests fail with network errors**
- Good! That means the network-blocking test is working
- If tests fail for other reasons, check the error message

## For Codex Users: Quick Prompt

You can share this with Codex to help it understand the system:

> You have access to a local knowledge graph through MCP. Store facts (stable truths), plans (versioned actions with status), and ideas (just ideas, not treated as truth). You're responsible for extracting entities, relationships, and tags from our conversation. Use the add_memory, search_memory, update_plan_status, supersede_plan, promote_idea, and other tools as needed.

See `CODEX_GUIDE.md` for the full guide.

## Architecture Notes

This version differs from the full Graphiti:
- **No LLM extraction** - Codex provides structured data
- **No embeddings** - Uses BM25 keyword search + graph traversal
- **Simpler schema** - Focus on fact/plan/idea lifecycle
- **Embedded DB** - Kuzu file-based, no server needed
- **No deduplication** - Exact string matching only

## License

Apache 2.0 (same as parent Graphiti project)
