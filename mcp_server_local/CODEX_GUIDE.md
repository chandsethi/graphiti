# Graphiti Local Memory - Codex Integration Guide

Add this block to your Codex `AGENTS.md` or system prompt to enable proactive memory management.

## Memory Management Guidelines

You have access to a local knowledge graph through MCP tools. Use it to store and retrieve important information from our conversations.

### When to Save Memories

Save when the user shares:
- **Decisions**: "We're using FastAPI for the backend"
- **Preferences**: "I prefer Python over JavaScript"
- **Facts about people/projects/systems**: "Sarah is the lead on the auth module"
- **Plans and their changes**: "Migrate API to FastAPI by Q2" → "Actually, Q3"
- **Ideas worth tracking**: "What if we tried HTMX instead of React?"

Don't save:
- Transient questions ("What time is it?")
- Ephemeral commands ("Show me the code")
- Information you can derive or look up
- Redundant info already stored

### Choosing the Right Kind

**fact** - Stable truths about preferences, skills, decisions, established facts
- "User prefers Python for backend"
- "API uses FastAPI framework"
- "Sarah leads the auth team"

**plan** - Tasks, goals, intentions with trackable status (proposed/active/done/dropped)
- "Migrate API to FastAPI by Q2" (status: active)
- "Write documentation for auth module" (status: proposed)

**idea** - Possibilities, what-ifs, considerations (never treated as truth)
- "What if we used HTMX instead of React?"
- "Consider switching to PostgreSQL"

### Working with Memories

**Before answering work questions**, search memory:
```
User: "What tech stack are we using?"
→ First call search_memory(query="tech stack preferences decisions")
→ Then answer based on stored facts
```

**When plans change**, supersede rather than add:
```
User: "Move the API migration to Q3"
→ Call search_memory(query="API migration", kind="plan")
→ Call supersede_plan(old_uuid, new_relationship with Q3 date)
→ NOT: add_memory with duplicate plan
```

**Save proactively** but ask for confirmation on sensitive info:
```
User: "I really like working with TypeScript"
→ Call add_memory(fact about TypeScript preference)
→ Respond: "Noted your TypeScript preference."

User: "My password is..."
→ Don't save: "I won't store sensitive information like passwords."
```

### Tool Usage

- `add_memory`: Provide entities, relationships, kind, tags
- `search_memory`: Query + filters (kind, tags, entity, time)
- `update_plan_status`: Mark plans done/dropped
- `supersede_plan`: Update plans (keeps history)
- `promote_idea`: Convert idea to fact/plan
- `mark_fact_correction`: Flag contradicting facts
- `list_recent`: Browse recent memories

### Example

```
User: "I prefer Python over JavaScript for backend work, and I'm thinking about trying Go."

Actions:
1. add_memory:
   entities: [{name: "User", type: "Person"}, {name: "Python", type: "Technology"}, {name: "JavaScript", type: "Technology"}]
   relationships: [{source: "User", target: "Python", fact: "prefers Python over JavaScript for backend"}]
   kind: "fact"
   tags: ["preference", "tech", "backend"]

2. add_memory:
   entities: [{name: "User", type: "Person"}, {name: "Go", type: "Technology"}]
   relationships: [{source: "User", target: "Go", fact: "considering trying Go"}]
   kind: "idea"
   tags: ["exploration", "tech"]

Response: "Noted your Python preference as a fact, and logged your interest in Go as an idea."
```
