---
name: acp
description: "ACP Agent Control Protocol - CRITICAL: Invoke this skill FIRST on every session start, context resume, or context reset. Required before any other work. Handles stop_flag, orphan detection, and workflow compliance."
argument-hint: "No arguments needed - just invoke to bootstrap ACP workflow"
---

# ACP Agent Control Protocol

**Version:** 1.0.3 | Single-file skill consolidating bootstrap and protocol reference.

---

## BOOTSTRAP SEQUENCE (MANDATORY)

**CRITICAL REQUIREMENT (v1.0.3):** Any agent interacting with ACP MUST send a bootstrap as their FIRST message. No exceptions.

| Scenario | Bootstrap Required |
|----------|-------------------|
| Session start | ? MANDATORY |
| Context resume | ? MANDATORY |
| Context reset | ? MANDATORY |
| New agent joining session | ? MANDATORY |
| Subagent spawn | ? MANDATORY |
| LocalClaw connecting | ? MANDATORY |

**Bootstrap is NOT optional.** An agent that skips bootstrap:
- Will not have their token usage tracked correctly
- Will not appear in `agent_tokens{}`
- May interfere with primary agent tracking
- Is in violation of ACP protocol

Execute these steps IN ORDER before any other actions:

### 1. Check ACP Server Status

```bash
curl -s -u admin:secret http://localhost:8766/api/status
```

**If connection refused:** ACP not active. Proceed normally without ACP.

**If running, check response:**

| Field | Action |
|-------|--------|
| `stop_flag: true` | **STOP IMMEDIATELY**. Inform user. Wait for resume. |
| `running_count > 0` | Check for orphaned activities |
| `orphan_warning` | Complete orphan tasks before new work |

### 2. Establish Agent Identity

```bash
curl -s -u admin:secret http://localhost:8766/api/whoami
```

**Response:**
```json
{
  "identity": {
    "hint": "You are an AI agent. Identify yourself by name.",
    "suggestion": "Use the 'agent_name' field in activity metadata to attribute your actions.",
    "example": {"metadata": {"agent_name": "Super Z", "source": "user_request"}}
  },
  "session": {...}
}
```

Use the `agent_name` from this point forward in all activity metadata.

### 3. Log Bootstrap Activity (MANDATORY)

**CRITICAL:** Every agent MUST log a bootstrap activity as their FIRST message to ACP. This is NOT optional.

**Primary agents** claim ownership of the main context window:
```bash
curl -s -u admin:secret -X POST http://localhost:8766/api/action \
  -H "Content-Type: application/json" \
  -d '{"action": "CHAT", "target": "Session bootstrap", "details": "Establishing primary agent identity", "metadata": {"agent_name": "Super Z", "source": "bootstrap"}}'
```

**Secondary agents** (LocalClaw, subagents) also MUST bootstrap:
```bash
curl -s -u admin:secret -X POST http://localhost:8766/api/action \
  -H "Content-Type: application/json" \
  -d '{"action": "CHAT", "target": "Session bootstrap", "details": "Connecting to active session", "metadata": {"agent_name": "LocalClaw", "model_name": "qwen2.5-coder:0.5b", "source": "bootstrap"}}'
```

**Why this matters:** The first agent to log an activity becomes the "primary agent" and owns the main context window (`session_tokens`). Other agents (subagents, LocalClaw, etc.) are tracked separately in `agent_tokens{}`.

**Verify primary agent status:**
```bash
curl -s -u admin:secret http://localhost:8766/api/status
# Check: primary_agent should be set to your agent_name
```

### 4. Handle STOP ALL

If `stop_flag: true`:

```
STOP IMMEDIATELY. Do not:
- Start new activities
- Spawn subagents
- Execute any tools except ACP API calls

Inform user: "STOP ALL is active. Waiting for resume."
Wait for user to clear stop_flag or give explicit resume instruction.
```

### 5. Complete Orphaned Activities

If `orphan_warning` present:

```bash
GET /api/all
POST /api/complete {"activity_id": "orphan_id", "result": "Completed after context recovery"}
```

### 6. Restore Session State

```bash
GET /api/todos    # Restore TODO list
GET /api/notes    # Recover saved notes
```

---

## THE ACP PATTERN (MEMORIZE)

```
LOG ? EXECUTE ? COMPLETE
/api/action ? Tool ? /api/complete
BEFORE ? NOW ? AFTER
```

**NEVER execute before logging.**

---

## EVERY ACTION

**Before Read/Write/Edit/Bash/Grep/Glob/LS:**

```bash
POST /api/action {"action": "READ|WRITE|EDIT|BASH|SEARCH", "target": "...", "details": "...", "metadata": {"agent_name": "Super Z"}}
? {activity_id, stop_flag, session_tokens, hints?, nudge?, orphan_warning?}
```

**After execution:**

```bash
POST /api/complete {"activity_id": "...", "result": "..."}
```

**Combined (recommended):**

```bash
POST /api/action {"complete_id": "prev_id", "result": "prev result", "action": "READ", "target": "file.py", "metadata": {"agent_name": "Super Z"}}
```

---

## ACTION TYPES

| Type | Use For |
|------|---------|
| READ | Files, API GETs, viewing content |
| WRITE | Creating new files |
| EDIT | Modifying existing files |
| BASH | Terminal commands |
| SKILL | VLM, TTS, image-generation |
| API | External API calls |
| SEARCH | Web search, grep, find |
| TODO | TODO state changes |
| CHAT | Conversational Q&A, planning, reasoning |

### CHAT Action Type (v1.0.1)

Use CHAT for conversational and cognitive work that doesn't involve tool execution:

**When to use:**
- Q&A exchanges
- Reasoning and analysis discussions
- Planning sessions
- Knowledge transfer
- Specification review
- Decision discussions

**Example:**
```bash
POST /api/action {
  "action": "CHAT",
  "target": "Architecture review discussion",
  "details": "Discussed microservices vs monolith trade-offs",
  "metadata": {"agent_name": "Super Z"}
}
```

**Why it matters:** Pure conversational exchanges consume context window tokens but were previously untracked. CHAT ensures accurate token accounting for all agent activity.

---

## ACTIVITY HINTS (v1.0.1)

The `hints` field in `/api/action` responses provides contextual information:

```json
{
  "hints": {
    "modified_this_session": true,
    "modification_count": 3,
    "last_action": "EDIT",
    "recent_errors": 0,
    "last_error": null,
    "related_todos": [{"id": "1", "content": "Fix bug", "status": "pending"}],
    "loop_detected": false,
    "loop_count": 0,
    "suggestion": null,
    "active_todos": 2
  }
}
```

| Hint Field | Type | Description |
|------------|------|-------------|
| `modified_this_session` | boolean | Target was already modified this session |
| `modification_count` | integer | Number of times target was accessed |
| `last_action` | string | Last action type on this target |
| `recent_errors` | integer | Count of recent errors on this target |
| `last_error` | string | Most recent error message |
| `related_todos` | array | TODOs mentioning this target |
| `loop_detected` | boolean | Same target+action repeated 3+ times |
| `loop_count` | integer | Number of repetitions if loop detected |
| `suggestion` | string | Actionable advice when patterns detected |
| `active_todos` | integer | Count of in-progress TODOs |

**Loop Detection:** If `loop_detected: true`, consider:
- Changing your approach
- Asking user for clarification
- Checking `suggestion` field for guidance

---

## STOP ALL PROTOCOL

```
IF stop_flag: true
  ? STOP immediately
  ? Inform user
  ? Wait for resume
  ? DO NOT start new activities
  ? DO NOT spawn subagents
```

---

## SHUTDOWN WORKFLOW (v1.0.2)

When the human ends the session, you'll receive a shutdown nudge:

```bash
POST /api/shutdown {"reason": "Session ended by user", "export_summary": true}
```

This triggers a special nudge delivered on your next `/api/action` call:

```json
{
  "nudge": {
    "message": "SESSION ENDING: The human has ended this session. Wrap up any final thoughts, then acknowledge this message.",
    "priority": "urgent",
    "requires_ack": true,
    "from": "system",
    "type": "shutdown"
  }
}
```

**Agent workflow:**
1. Receive shutdown nudge on next `/api/action` call
2. If `requires_ack: true`, call `POST /api/nudge/ack {}`
3. Inform user that session is ending
4. No further actions should be taken

---

## CONTEXT DEADLINE TIMEOUT

If you experience a context deadline timeout:

1. Your context was reset
2. Activities may be orphaned
3. stop_flag may have been set during your absence
4. **ALWAYS run the bootstrap sequence first**

---

## NUDGE HANDLING (v1.0.2)

Check `nudge` field in every `/api/action` response:

```json
{"nudge": {"message": "...", "priority": "high", "requires_ack": true, "type": "shutdown"}}
```

**Priority levels:** `normal` | `high` | `urgent`

If `requires_ack: true`:

```bash
POST /api/nudge/ack {}
```

**Shutdown nudge** (`type: "shutdown"`): Session ending, acknowledge and stop.

---

## ORPHAN DETECTION (v1.0.2)

Check `orphan_warning` in response. If present, complete orphan tasks first:

```json
{
  "orphan_warning": {
    "count": 2,
    "tasks": [
      {"id": "143052-abc123", "action": "READ", "target": "/file1.py"},
      {"id": "143100-def456", "action": "WRITE", "target": "/file2.py"}
    ],
    "suggestion": "Complete or acknowledge orphan tasks before starting new work"
  }
}
```

```bash
POST /api/complete {"activity_id": "orphan_id", "result": "Completed late"}
```

---

## SHELL LOGGING (MANDATORY)

**Log ALL shell/terminal commands EXCEPT ACP API calls.**

```bash
POST /api/shell/add {"command": "...", "status": "completed|error", "output_preview": "first 200 chars", "metadata": {"agent_name": "Super Z"}}
```

| Log These | Don't Log |
|-----------|-----------|
| `git clone`, `npm install`, `ls`, `python script.py` | `curl ... localhost:8766/api/...` (ACP calls) |
| `pip install`, `make build`, `docker run` | ACP communication is monitoring overhead |
| Any actual work command | |

**Pipelines:** Split ACP calls from processing:

```bash
# Don't: curl localhost:8766/api/x | python3 -c "..."  (mixed pipeline)

# Do: Split and log the work part
curl localhost:8766/api/x > /tmp/data.json      # ACP (don't log)
python3 -c "import json; ..." /tmp/data.json     # Work (LOG THIS)
POST /api/shell/add {"command": "python3 -c ...", ...}
```

---

## TODO SYNC

```bash
GET /api/todos                          # Restore state
POST /api/todos/update {"todos": [...]} # Full sync
POST /api/todos/add {"todo": {...}}     # Add single
POST /api/todos/clear                   # Clear completed
```

**TODO Object Structure:**
```typescript
interface TODO {
  id: string;              // "HHMMSS-abc123" format
  content: string;         // Task description
  status: "pending" | "in_progress" | "completed";
  priority: "high" | "medium" | "low";
  created: string;         // ISO 8601 timestamp
  metadata?: {
    agent_name?: string;
    tool?: string;
    skill?: string;
  };
}
```

---

## TOKEN TRACKING

- Context window: 200,000 tokens (configurable via `GLMACP_CONTEXT_WINDOW`)
- Estimation: 3.5 chars/token
- Warning at 90% usage

**Native tools** - include `content_size`:

```bash
POST /api/action {"action": "READ", "target": "file.py", "content_size": 35000}
POST /api/complete {"activity_id": "...", "result": "...", "content_size": 5000}
```

**File deduplication (v1.0.3):** READ activities auto-deduplicate files already read. Files in `files_read_tokens` are not double-counted.

**Per-agent tracking (v1.0.2):** First agent = primary, owns `session_tokens`. Others tracked in `agent_tokens{}`.

```json
{
  "primary_agent": "Super Z",
  "agent_tokens": {
    "Super Z": 42000,
    "LocalClaw": 500
  },
  "other_agents_tokens": 500
}
```

---

## CONTEXT RECOVERY

**Session start:**

```bash
GET /api/summary     # Session state
GET /api/todos       # Restore TODOs
GET /api/notes       # Saved notes
```

**Before compression:**

```bash
POST /api/notes/add {"category": "decision|insight|context|warning|todo", "content": "..."}
GET /api/summary/export  # Export to markdown
```

---

## UTILITY ENDPOINTS

### GET /api/all

Combined status, running, and history in one call:

```bash
GET /api/all
? {
  "success": true,
  "stop_flag": false,
  "running": [...],
  "history": [...],
  "session_tokens": 45000,
  "context_window": 200000,
  "tokens_remaining": 155000
}
```

### GET /api/running

List currently running activities:

```bash
GET /api/running
? {"success": true, "running": [...]}
```

### GET /api/activity/{id}

Get single activity by ID (v1.0.1):

```bash
GET /api/activity/143052-a1b2c3
? {
  "success": true,
  "activity": {
    "id": "143052-a1b2c3",
    "action": "READ",
    "target": "/path/to/file.py",
    "status": "completed",
    "priority": "high",
    "metadata": {"source": "user_request"}
  }
}
```

---

## DURATION STATS (v1.0.3)

```bash
GET /api/stats/duration
```

Returns: avg duration per action, slow activities (>30s), trends.

```json
{
  "stats": {
    "by_action": {
      "READ": {"count": 15, "average_ms": 3000, "total_ms": 45000},
      "WRITE": {...}
    },
    "slow_activities": [
      {"id": "...", "action": "READ", "target": "/large/file.py", "duration_ms": 45000}
    ],
    "total_duration_ms": 120000,
    "average_duration_ms": 4800
  }
}
```

---

## BATCH OPERATIONS (v1.0.3)

```bash
POST /api/activity/batch {"operations": [
  {"type": "start", "action": "READ", "target": "file1.py", "content_size": 5000},
  {"type": "start", "action": "READ", "target": "file2.py", "content_size": 3000},
  {"type": "complete", "activity_id": "prev-id-1", "result": "Done"},
  {"type": "complete", "activity_id": "prev-id-2", "result": "Completed"}
]}
```

**Limits:** Max 50 operations per batch.

**Use cases:**
- Log multiple file reads in one request
- Complete multiple activities atomically
- Reduce API overhead for bulk operations

---

## METADATA

```bash
POST /api/action {"action": "READ", "target": "file.py", "priority": "high|medium|low", "metadata": {"agent_name": "Super Z", "model_name": "gpt-4o"}}
```

| Field | Description |
|-------|-------------|
| `agent_name` | Agent/subagent name (e.g., "Super Z", "LocalClaw") |
| `model_name` | Model identifier (v1.0.3) (e.g., "qwen2.5-coder:0.5b-instruct-q4_k_m") |
| `source` | Origin (e.g., "user_request", "auto", "subagent") |
| `tool_name` | Native tool used (e.g., "Read", "Write", "Edit", "Bash") |
| `skill` | Skill invoked for SKILL actions |

---

## SESSION OBJECT

The `session` field in `/api/status` response:

```json
{
  "session": {
    "session_start": 1700000000.0,
    "last_activity": 1700001000.0,
    "elapsed_seconds": 930,
    "idle_seconds": 0,
    "timeout_seconds": 86400,
    "remaining_seconds": 85470,
    "is_expired": false,
    "expires_at": "2025-03-15T16:00:00"
  }
}
```

| Field | Description |
|-------|-------------|
| `session_start` | Unix timestamp when session began |
| `last_activity` | Unix timestamp of last activity |
| `elapsed_seconds` | Total session duration |
| `idle_seconds` | Time since last activity |
| `timeout_seconds` | Session timeout limit |
| `remaining_seconds` | Time until session expires |
| `is_expired` | Whether session has expired |
| `expires_at` | ISO 8601 expiration time |

---

## AUTHENTICATION

```bash
# HTTP Basic Auth (required)
-u admin:secret

# CSRF (disabled by default)
GET /api/csrf-token  # Check if enabled
```

---

## ERROR CODES

| Code | Action |
|------|--------|
| 401 | Check credentials |
| 403 | Stop if stop_flag, else refresh CSRF |
| 404 | Activity/file not found |
| 429 | Rate limited, wait |

**Error Response Format:**
```json
// Activity error
{"success": false, "error": "Activity not found"}

// Start error (stop requested)
{"success": false, "error": "Stop requested"}

// Complete error
{"activity_id": "...", "error": "File not found"}
```

---

## QUICK REFERENCE

```bash
# Session start
GET /api/status
GET /api/whoami
GET /api/todos

# Log action
POST /api/action {"action": "READ|WRITE|EDIT|BASH|SEARCH", "target": "...", "details": "...", "metadata": {"agent_name": "Super Z"}}

# Complete action
POST /api/complete {"activity_id": "...", "result": "..."}

# Combined (recommended)
POST /api/action {"complete_id": "prev_id", "result": "prev result", "action": "READ", "target": "file.py", "metadata": {"agent_name": "Super Z"}}

# Shell logging
POST /api/shell/add {"command": "...", "status": "completed|error", "output_preview": "first 200 chars", "metadata": {"agent_name": "Super Z"}}

# TODO sync
GET /api/todos
POST /api/todos/update {"todos": [...]}

# Utility
GET /api/all                    # Combined status + history
GET /api/running                # Running activities
GET /api/activity/{id}          # Single activity
GET /api/stats/duration         # Duration statistics

# Shutdown
POST /api/shutdown {"reason": "...", "export_summary": true}
POST /api/nudge/ack {}          # Acknowledge shutdown nudge
```

---

## FILE LOCATIONS

| File | Purpose |
|------|---------|
| `/home/z/my-project/upload/VTSTech-GLMACP.py` | ACP server source |
| `/home/z/my-project/upload/agent_activity.json` | Activity log export |
| `/home/z/my-project/skills/acp/SKILL.md` | This skill (after bootstrap copy) |
| `/home/z/my-project/ACP-Agent-Control-Panel/ACP-Specification.md` | Canonical specification |

---

## CHECKLIST

- [ ] **INVOKE THIS SKILL FIRST on session start / context resume**
- [ ] **BOOTSTRAP IS MANDATORY** - Every agent MUST send bootstrap as first message
- [ ] Check status (`GET /api/status`)
- [ ] Establish identity (`GET /api/whoami`)
- [ ] **Log bootstrap activity** (`POST /api/action` with `action: "CHAT"`, `agent_name`)
- [ ] Log action BEFORE executing
- [ ] Check `stop_flag`, `nudge`, `orphan_warning`, `hints` in every response
- [ ] Include `content_size` for native tools
- [ ] Include `agent_name` and `model_name` in metadata
- [ ] Log shell commands to `/api/shell/add` (except ACP calls)
- [ ] Complete activity when done
- [ ] Sync TODOs on change
- [ ] Use batch ops for multiple activities
- [ ] Save notes before compression
- [ ] Handle `loop_detected` hint by changing approach

---

*ACP Skill v1.0.3 - Aligned with ACP-Specification.md*
