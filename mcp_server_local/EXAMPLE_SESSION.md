# Example Session - Graphiti Local Memory

This shows what a typical Codex conversation looks like using the local memory system.

## Setup Verification

First, verify the server is installed:
```bash
cd mcp_server_local
python3 -m pytest tests/
```

All 10 tests should pass, including the network-blocking test.

## Example Conversation Flow

### User: "Remember this: I prefer Python over JavaScript for backend work."

**Codex thinks:**
- This is a preference (stable fact)
- Entities: User (Person), Python (Technology), JavaScript (Technology)
- Relationship: User → Python (prefers for backend)
- Tags: preference, tech, backend

**Codex calls:**
```json
{
  "tool": "add_memory",
  "arguments": {
    "entities": [
      {"name": "User", "type": "Person", "summary": "The user"},
      {"name": "Python", "type": "Technology", "summary": "Programming language"},
      {"name": "JavaScript", "type": "Technology", "summary": "Programming language"}
    ],
    "relationships": [
      {
        "source": "User",
        "target": "Python",
        "fact": "User prefers Python over JavaScript for backend development"
      }
    ],
    "kind": "fact",
    "tags": ["preference", "tech", "backend"]
  }
}
```

**Response:**
```
{
  "status": "success",
  "entities_created": 3,
  "relationships_created": 1,
  "relationship_uuids": ["uuid-123"]
}
```

**Codex to User:**
"Got it. I've noted your Python preference as a fact."

---

### User: "I'm planning to migrate our API to FastAPI by Q2. Status: active."

**Codex thinks:**
- This is a plan (versioned, has status)
- Entities: Team (Organization), API (System), FastAPI (Technology)
- Relationship: Team → API (migrate to FastAPI)
- Plan status: active, due Q2

**Codex calls:**
```json
{
  "tool": "add_memory",
  "arguments": {
    "entities": [
      {"name": "Engineering Team", "type": "Organization"},
      {"name": "API", "type": "System"},
      {"name": "FastAPI", "type": "Technology"}
    ],
    "relationships": [
      {
        "source": "Engineering Team",
        "target": "API",
        "fact": "Migrate API to FastAPI by Q2"
      }
    ],
    "kind": "plan",
    "plan_status": "active",
    "tags": ["migration", "api", "backend"]
  }
}
```

**Codex to User:**
"I've tracked that plan. It's marked as active with a Q2 timeline."

---

### User: "What if we used HTMX instead of React for the frontend?"

**Codex thinks:**
- This is an idea (exploration, not a commitment)
- Entities: Frontend (System), HTMX (Technology), React (Technology)

**Codex calls:**
```json
{
  "tool": "add_memory",
  "arguments": {
    "entities": [
      {"name": "Frontend", "type": "System"},
      {"name": "HTMX", "type": "Technology"},
      {"name": "React", "type": "Technology"}
    ],
    "relationships": [
      {
        "source": "Frontend",
        "target": "HTMX",
        "fact": "Consider using HTMX instead of React for frontend"
      }
    ],
    "kind": "idea",
    "tags": ["frontend", "exploration", "tech"]
  }
}
```

**Codex to User:**
"Interesting idea. I've logged it as an exploration - not a commitment yet."

---

### User: "What are my current active plans?"

**Codex calls:**
```json
{
  "tool": "search_memory",
  "arguments": {
    "query": "",
    "kind": "plan",
    "limit": 20
  }
}
```

**Response:**
```
Found 1 memories:

[plan [active]] Engineering Team → API: Migrate API to FastAPI by Q2 tags:['migration', 'api', 'backend'] (uuid: uuid-123, valid: 2026-10-03T15:00:00Z)
```

**Codex to User:**
"You have one active plan:
- Migrate API to FastAPI by Q2 (Engineering Team)"

---

### User: "Actually, move that API migration to Q3 instead."

**Codex thinks:**
- Supersede the old plan with a new one
- Keep the old plan in history (marked invalid)

**Codex calls:**
```json
{
  "tool": "supersede_plan",
  "arguments": {
    "old_relationship_uuid": "uuid-123",
    "new_relationship": {
      "source": "Engineering Team",
      "target": "API",
      "fact": "Migrate API to FastAPI by Q3"
    }
  }
}
```

**Response:**
```
Plan superseded. Old: uuid-123, New: uuid-456
```

**Codex to User:**
"Updated. The API migration plan is now scheduled for Q3. The old Q2 timeline is preserved in history."

---

### User: "Let's actually do that HTMX thing. Make it a plan."

**Codex thinks:**
- Promote the idea to a plan
- Find the idea UUID first

**Codex calls search first:**
```json
{
  "tool": "search_memory",
  "arguments": {
    "query": "HTMX",
    "kind": "idea"
  }
}
```

**Then promotes:**
```json
{
  "tool": "promote_idea",
  "arguments": {
    "relationship_uuid": "uuid-789",
    "new_kind": "plan",
    "plan_status": "proposed"
  }
}
```

**Codex to User:**
"Done. I've promoted the HTMX idea to a proposed plan."

---

### User: "What are my tech preferences?"

**Codex calls:**
```json
{
  "tool": "search_memory",
  "arguments": {
    "query": "tech preference",
    "kind": "fact",
    "tags": ["tech", "preference"]
  }
}
```

**Response:**
```
Found 1 memories:

[fact] User → Python: User prefers Python over JavaScript for backend development tags:['preference', 'tech', 'backend'] (uuid: uuid-123, valid: 2026-10-03T14:00:00Z)
```

**Codex to User:**
"Your tech preferences:
- You prefer Python over JavaScript for backend development"

---

### User: "The migration is done!"

**Codex calls:**
```json
{
  "tool": "search_memory",
  "arguments": {
    "query": "API migration FastAPI",
    "kind": "plan"
  }
}
```

**Then updates status:**
```json
{
  "tool": "update_plan_status",
  "arguments": {
    "relationship_uuid": "uuid-456",
    "status": "done"
  }
}
```

**Codex to User:**
"Congratulations! I've marked the API migration as complete."

---

## Key Points

1. **Codex decides** fact vs plan vs idea
2. **Codex extracts** entities and relationships
3. **Codex chooses** appropriate tags
4. **Server just stores** and retrieves
5. **No LLM calls** on the server
6. **Search is deterministic** (BM25 keywords)
7. **History is preserved** (superseded plans, corrected facts)

## Data on Disk

After this session, `~/.graphiti-local/kuzu.db/` contains:

**Entities:**
- User (Person)
- Python (Technology)
- JavaScript (Technology)
- Engineering Team (Organization)
- API (System)
- FastAPI (Technology)
- Frontend (System)
- HTMX (Technology)
- React (Technology)

**Relationships:**
- [fact] User → Python: "prefers Python over JavaScript..." (active)
- [plan] Engineering Team → API: "Migrate API to FastAPI by Q2" (superseded)
- [plan] Engineering Team → API: "Migrate API to FastAPI by Q3" (done)
- [plan] Frontend → HTMX: "Consider using HTMX instead of React..." (proposed)

## Backup and Reset

Backup:
```bash
cp -r ~/.graphiti-local/ ~/backup-graphiti-$(date +%Y%m%d)/
```

Reset:
```bash
rm -rf ~/.graphiti-local/
# Will be recreated on next use
```

## Performance

With this architecture:
- Add memory: < 10ms (just database writes)
- Search: < 50ms for typical queries
- Get neighborhood: < 20ms
- No network latency
- No API rate limits
- Works offline

Perfect for daily use on a work Mac.
