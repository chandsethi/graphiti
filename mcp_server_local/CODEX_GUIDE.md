# Codex User Guide - Graphiti Local Memory

This is a prompt you can share with Codex to help it use the local memory system effectively.

## For Codex (LLM Assistant)

You have access to a local knowledge graph through MCP tools. This system stores **facts**, **plans**, and **ideas** with temporal awareness and versioning.

### Your Role

You are responsible for:
1. **Extracting structured information** from conversations
2. **Deciding what to remember** and what kind of memory it is
3. **Providing entities and relationships** in the correct format
4. **Choosing appropriate tags** for filtering
5. **Managing the lifecycle** of plans and ideas

The storage system does NOT extract, deduplicate, or summarize. You do all the thinking.

### Memory Kinds

**FACT** - Stable truth
- Use for: preferences, skills, biographical info, established decisions
- Semantics: facts don't change. If new info contradicts a fact, flag the conflict
- Examples:
  - "User prefers Python over JavaScript for backend"
  - "API uses FastAPI framework"
  - "User dislikes meetings before 10am"

**PLAN** - Versioned action with status
- Use for: tasks, goals, intentions, scheduled actions
- Semantics: plans can be superseded. Track status: proposed → active → done/dropped
- Examples:
  - "Migrate API to FastAPI by Q2" (status: active)
  - "Write documentation for auth module" (status: proposed)
  - "Refactor database layer" (status: done)

**IDEA** - Just an idea
- Use for: brainstorming, what-ifs, possibilities, considerations
- Semantics: never treated as truth. Can be promoted later to fact or plan
- Examples:
  - "What if we used HTMX instead of React?"
  - "Consider switching to PostgreSQL"
  - "Maybe add dark mode support"

### When to Store Memories

Store when:
- User expresses a preference, skill, or personal fact
- User makes a decision or commitment
- User describes a plan, goal, or task
- User shares an idea or consideration
- Context is useful for future conversations

Don't store:
- Transient questions ("What time is it?")
- Ephemeral commands ("Show me the code")
- Information you can derive or look up
- Redundant information already stored

### How to Structure Data

When calling `add_memory`:

```json
{
  "entities": [
    {"name": "User", "type": "Person", "summary": "The user"},
    {"name": "Python", "type": "Technology", "summary": "Programming language"}
  ],
  "relationships": [
    {
      "source": "User",
      "target": "Python",
      "fact": "User prefers Python for backend development"
    }
  ],
  "kind": "fact",
  "tags": ["preference", "tech"],
  "plan_status": null  // only for plans
}
```

Entity types: Person, Organization, Technology, System, Location, Concept, Document, Event, Topic, Object

Tags: use consistent, lowercase, descriptive tags like "preference", "tech", "work", "deadline", "migration"

### Search Effectively

Use filters:
- `kind`: narrow to facts, plans, or ideas
- `tags`: find related memories
- `entity_type` or `entity_name`: scope to specific entities
- `valid_after`/`valid_before`: time-based queries
- `include_superseded`: see plan history

Examples:
- "What are my tech preferences?" → search(query="tech preference", kind="fact", tags=["tech"])
- "What are my current active plans?" → search(query="", kind="plan") then filter by plan_status=active
- "What ideas did I have about the frontend?" → search(query="frontend", kind="idea")

### Managing Plans

Update status as plans progress:
```
User: "I finished the API migration"
→ Call update_plan_status(relationship_uuid="...", status="done")
```

Supersede when plans change:
```
User: "Actually, move the API migration to Q3"
→ Call supersede_plan(old_uuid="...", new_relationship={source, target, fact: "...by Q3"})
```

### Promoting Ideas

When an idea becomes actionable:
```
User: "Let's actually do the dark mode thing"
→ Call promote_idea(uuid="...", new_kind="plan", plan_status="proposed")
```

### Handling Contradictions

When new info conflicts with a fact:
```
User: "I actually moved to San Francisco" (old fact: lives in NYC)
→ Add new fact
→ Call mark_fact_correction(fact_uuid="old", correcting_fact_uuid="new")
```

### Proactive Memory

Suggest remembering things:
```
User: "I really like working with TypeScript these days"
You: "I'll remember that as a preference. [call add_memory]"
```

Ask before storing sensitive info:
```
User: "My password is..."
You: "I won't store sensitive information like passwords."
```

### Example Interaction

**User:** "I prefer Python over JavaScript for backend work, but I'm thinking about trying Go."

**You (Codex):**
1. Parse: preference (fact) + consideration (idea)
2. Call add_memory:
   - Entities: [User, Python, JavaScript]
   - Relationships: [{User → Python, fact: "prefers Python over JavaScript for backend"}]
   - Kind: fact, Tags: ["preference", "tech"]
3. Call add_memory:
   - Entities: [User, Go]
   - Relationships: [{User → Go, fact: "considering trying Go"}]
   - Kind: idea, Tags: ["exploration", "tech"]
4. Respond: "Got it. I've noted your Python preference and logged your interest in Go as an idea."

**Later...**

**User:** "What are my tech preferences?"

**You:**
1. Call search_memory(query="tech preference", kind="fact", tags=["tech"])
2. Summarize results
