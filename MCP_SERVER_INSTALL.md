# Graphiti MCP Server Installation

The Graphiti MCP Server now supports memory kind tracking, allowing you to distinguish between facts, plans, and ideas.

## Installation

Install directly from this git branch using `uv`:

```bash
uv tool install --python 3.12 "git+https://github.com/chandsethi/graphiti.git@cursor/memory-kind-tracking-b83a#subdirectory=mcp_server"
```

This installs the `graphiti-mcp-server` command with:
- Embedded Kuzu database (no Docker or external server needed)
- Local storage at `~/.graphiti/kuzu.db`
- All memory kind tracking features

## Codex Configuration

Add the following to your `~/.codex/config.toml`:

```toml
[mcp_servers.graphiti]
command = "graphiti-mcp-server"
env = { OPENAI_API_KEY = "<your-key-here>" }
```

That's it! No config file needed. The server will:
- Start over stdio when Codex launches it
- Use embedded Kuzu database at `~/.graphiti/kuzu.db`
- Work from any working directory

### Custom LLM Gateway (e.g., Bifrost, Ollama, LM Studio)

For OpenAI-compatible gateways with custom authentication:

```toml
[mcp_servers.graphiti]
command = "graphiti-mcp-server"

[mcp_servers.graphiti.env]
OPENAI_BASE_URL = "https://bifrost-llm-proxy-alb-0.cmd.hotstar-prod.com/openai/v1"
LLM_EXTRA_HEADERS = "{\"x-bf-vk\":\"<your-virtual-key>\"}"
LLM_MODEL = "openai.gpt-4o-mini"
EMBEDDER_MODEL = "openai.text-embedding-3-small"
```

Or use the convenience var for Bifrost:

```toml
[mcp_servers.graphiti]
command = "graphiti-mcp-server"

[mcp_servers.graphiti.env]
OPENAI_BASE_URL = "https://your-gateway.com/openai/v1"
BIFROST_VK = "<your-virtual-key>"
LLM_MODEL = "google.gemma-3-27b-it"
```

**Note**: The server uses the generic OpenAI client (`/chat/completions`) for custom base URLs, which works with most OpenAI-compatible gateways. Set `OPENAI_API_KEY` to any dummy value if your gateway doesn't need it.

### Alternative LLM Providers

Native provider support (not through a gateway):

```toml
# Anthropic
[mcp_servers.graphiti]
command = "graphiti-mcp-server"
env = { ANTHROPIC_API_KEY = "<your-key-here>" }

# Google Gemini
[mcp_servers.graphiti]
command = "graphiti-mcp-server"
env = { GOOGLE_API_KEY = "<your-key-here>" }

# Groq
[mcp_servers.graphiti]
command = "graphiti-mcp-server"
env = { GROQ_API_KEY = "<your-key-here>" }
```

For other configurations, see the [full MCP server documentation](mcp_server/README.md).

## Memory Kind Tracking

The server now tracks three kinds of information:

- **fact**: Stable statements about how things are or were (default)
- **plan**: Intended or committed future actions that may change
- **idea**: Speculative thoughts or possibilities nobody has committed to

### How It Works

When you add memory with `add_memory`, Graphiti's LLM automatically classifies each extracted relationship by its kind. You don't need to specify the kind yourself.

### Resolution Rules

Different kinds have different update rules:

1. **Fact vs Fact**:
   - If the new fact explicitly corrects or updates an old fact, the old fact is invalidated
   - If the new fact contradicts an old fact but is not a correction (e.g., different sources), both are kept and marked as conflicting

2. **Plan vs Plan**:
   - A new plan supersedes the older plan about the same subject/goal
   - The old plan is invalidated but kept for history

3. **Idea**:
   - Ideas never invalidate or conflict with facts or plans
   - Ideas only dedupe against identical ideas

### Searching by Kind

Use the `search_memory_facts` tool with the `kinds` parameter:

```python
# Search only for plans
results = search_memory_facts(query="...", kinds=["plan"])

# Search for facts and plans, excluding ideas
results = search_memory_facts(query="...", kinds=["fact", "plan"])

# Include invalidated/superseded items
results = search_memory_facts(query="...", include_invalidated=True)
```

### Result Fields

Search results include:

- `kind`: The memory kind (fact/plan/idea)
- `superseded_by`: UUID of the edge that superseded this one (for plans)
- `conflicts_with`: List of UUIDs of conflicting edges (for contradictory facts)
- `expired_at`: When the edge was invalidated (null for current edges)

## Locked-Down Environment

This build uses the embedded Kuzu driver by default, which requires no external database. Perfect for environments without Docker or admin rights.

## Migration

If upgrading an existing Graphiti installation with data:

```python
from graphiti_core.migrations.add_edge_kind_fields import migrate_edges

# After initializing your driver
stats = await migrate_edges(driver)
print(f"Migrated {stats['edges_updated']} edges")
```

This sets default values for existing edges (kind='fact', no supersession or conflicts).
