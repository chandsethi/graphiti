# Graphiti Local Memory - Embedded Knowledge Graph for Codex

A local-only version of Graphiti designed for work environments without internet access or API keys. This version runs entirely on your Mac, storing data in a local file-based database. Perfect for use with the Codex Mac app over MCP.

## Key Features

- **Zero API Keys Required**: No LLM or embedding API calls. Codex does all the thinking; this just stores and retrieves.
- **Local File Storage**: Uses Kuzu embedded database - all data in `~/.graphiti-local/`
- **Knowledge Types**: Every memory has a `kind`: `fact`, `plan`, or `idea`
  - **Facts**: Stable truth. Conflicts are flagged, not silently overwritten
  - **Plans**: Versioned and can be superseded. Track status (proposed/active/done/dropped)
  - **Ideas**: Just ideas - never treated as truth, can be promoted later
- **Rich Search**: BM25 full-text + graph traversal. Filter by kind, tags, entity type, time range
- **Easy Install**: One command, no Docker, no admin rights needed

## Installation

### One-Line Install

```bash
pip install "git+https://github.com/chandsethi/graphiti.git#subdirectory=mcp_server_local"
```

Or with `pipx` (recommended for isolated installs):

```bash
pipx install "git+https://github.com/chandsethi/graphiti.git#subdirectory=mcp_server_local"
```

This installs the `graphiti-local-mcp` command.

### Requirements

- Python 3.10 or higher
- macOS or Linux

### Development Install

For local development:

```bash
git clone https://github.com/chandsethi/graphiti.git
cd graphiti/mcp_server_local
pip install -e .
```

## Codex Configuration

Add this to your `~/.codex/config.toml`:

```toml
[mcp_servers.graphiti-local]
command = "graphiti-local-mcp"
args = []
env = {}
```

If the command isn't found, use the full path from `which graphiti-local-mcp`:

```toml
[mcp_servers.graphiti-local]
command = "/Users/yourname/.local/bin/graphiti-local-mcp"
args = []
env = {}
```

After adding the configuration, restart Codex.

## Usage from Codex

Codex will use these MCP tools automatically. You can guide it with prompts like:

```
Remember this fact: I prefer Python over JavaScript for backend work.

Track this plan: Migrate the API to FastAPI by end of Q2. Status: active.

This is just an idea: What if we used HTMX instead of React?

What are my current active plans?

Search for facts about my tech preferences.

This plan is done: API migration (mark it complete).

Supersede my plan: the API migration moved to Q3 instead.
```

### Available MCP Tools

Codex calls these tools on your behalf:

- `add_memory`: Add a fact, plan, or idea with entities, relationships, and tags
- `search_memory`: Search memories by text, kind, tags, entity, time range
- `get_entity_neighborhood`: Get an entity and its connections
- `update_plan_status`: Mark a plan as proposed/active/done/dropped
- `supersede_plan`: Replace an old plan with a new version
- `promote_idea`: Convert an idea to a fact or plan
- `mark_fact_correction`: Flag a fact as corrected by new information
- `list_recent`: Get recent memories by kind

## Architecture

Unlike the full Graphiti, this version:

- **No LLM calls**: Codex provides structured entities/relationships/tags. No extraction, no deduplication, no summarization.
- **No embeddings**: Search uses BM25 (keyword) + graph traversal only. Fast, local, deterministic.
- **Simpler schema**: Focused on facts/plans/ideas with versioning.
- **Embedded DB**: Kuzu file-based database, no server process needed.

## Data Storage

All data is stored in `~/.graphiti-local/`:

```
~/.graphiti-local/
├── kuzu.db/        # Kuzu database files
└── config.json     # Local configuration
```

To back up your data, copy the `~/.graphiti-local/` directory.

To reset everything:

```bash
rm -rf ~/.graphiti-local/
```

## Testing

Run the test suite to verify everything works:

```bash
cd mcp_server_local
uv run pytest tests/
```

Key test: `test_no_api_calls.py` - verifies no network calls happen.

## Differences from Full Graphiti

| Feature | Full Graphiti | Local Version |
|---------|---------------|---------------|
| LLM/Embeddings | Required | None |
| Database | Neo4j/FalkorDB server | Kuzu embedded |
| Entity Extraction | Automatic | Codex provides |
| Deduplication | LLM-based | Exact match only |
| Search | Semantic + BM25 + Graph | BM25 + Graph |
| Install | Docker + API keys | One command |
| Knowledge Types | Generic | Fact/Plan/Idea |

## Troubleshooting

**"command not found: graphiti-local-mcp"**
- Install with `uv tool install` first, or use the full path in your Codex config

**"No such file or directory: ~/.graphiti-local/"**
- The directory is created automatically on first use

**Codex doesn't see the tools**
- Check the config.toml path matches your setup
- Restart Codex after config changes
- Check Codex logs for connection errors

## License

Apache 2.0 (same as parent Graphiti project)
