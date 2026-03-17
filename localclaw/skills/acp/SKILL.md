---
name: acp
description: "ACP Agent Control Panel - CRITICAL: Invoke this skill FIRST on every session start, context resume, or context reset. Required before any other work. Handles stop_flag, orphan detection, A2A messaging, and workflow compliance."
argument-hint: "No arguments needed - just invoke to bootstrap ACP workflow"
---

# ACP Skill (Minimal)

**Version:** 1.0.4 | **A2A Compliant**

## Environment (Ask Human)

| Variable | Description |
|----------|-------------|
| `ACP_URL` | The ACP server URL (e.g., `https://xxx.trycloudflare.com`) |
| `ACP_USER` | Auth username (default: `admin`) |
| `ACP_PASS` | Auth password (default: `secret`) |

---

## BOOTSTRAP (MANDATORY)

Execute on every session start / context resume:

```
1. GET  {ACP_URL}/api/status       → Check stop_flag, orphan_warning
2. GET  {ACP_URL}/api/whoami       → Establish identity
3. POST {ACP_URL}/api/agents/register {"agent_name": "Super Z", "capabilities": [...], "model_name": "..."}
4. POST {ACP_URL}/api/action {"action": "CHAT", "target": "Session bootstrap", "metadata": {"agent_name": "Super Z"}}
```

**If `stop_flag: true`**: STOP immediately, inform user, wait for resume.

**If `orphan_warning`**: Complete orphaned activities first.

---

## THE PATTERN (MANDATORY)

```
CHECK → LOG → EXECUTE → COMPLETE
/api/status → /api/action → Tool → /api/complete
BEFORE → NOW → AFTER
```

### MANDATORY Rules (Non-Negotiable)

1. **CHECK** `/api/status` on session start and after context recovery for `stop_flag`
2. **LOG** every action BEFORE executing via `/api/action`
3. **LOG** every shell command via `/api/shell/add` (except ACP API calls)
4. **COMPLETE** every activity when done via `/api/complete`

**NEVER execute before logging. NEVER skip logging.**

---

## CORE API

### Log Activity (before execution)

```bash
POST {ACP_URL}/api/action {
  "action": "READ|WRITE|EDIT|BASH|SEARCH|SKILL|API|TODO|CHAT|A2A",
  "target": "file path or resource",
  "details": "human description",
  "content_size": 0,           # Character count for token tracking
  "priority": "medium",        # high|medium|low
  "metadata": {"agent_name": "Super Z", "model_name": "..."}
}
→ {"activity_id": "...", "stop_flag": false, "hints": {...}, "nudge": null}
```

### Complete Activity (after execution)

```bash
POST {ACP_URL}/api/complete {
  "activity_id": "...",
  "result": "what happened",
  "content_size": 0
}
```

### Combined (recommended for efficiency)

```bash
POST {ACP_URL}/api/action {
  "complete_id": "prev_id",
  "result": "previous result",
  "action": "READ",
  "target": "next file",
  "metadata": {"agent_name": "Super Z"}
}
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
| CHAT | Conversational Q&A, planning |
| A2A | Agent-to-agent communication |

---

## RESPONSE FIELDS

Check these in **every** `/api/action` response:

| Field | Action |
|-------|--------|
| `stop_flag: true` | STOP immediately |
| `nudge` | Human guidance, ack if `requires_ack: true` |
| `orphan_warning` | Complete orphan tasks first |
| `hints.modified_this_session` | File was already modified - check before editing |
| `hints.loop_detected` | Same action repeated 3+ times - change approach |
| `hints.suggestion` | Actionable advice - follow it |
| `hints.a2a.pending_count` | Pending A2A messages - retrieve via /api/a2a/history |

---

## SHELL LOGGING (MANDATORY)

**Log ALL shell commands EXCEPT ACP API calls:**

```bash
POST {ACP_URL}/api/shell/add {
  "command": "npm install",
  "status": "completed|error",
  "output_preview": "first 200 chars",
  "agent_name": "Super Z"
}
```

Do this for EVERY terminal command executed.

---

## A2A MESSAGING (1.0.4)

### Send Message

```bash
POST {ACP_URL}/api/a2a/send {
  "from_agent": "Super Z",
  "to_agent": "OtherAgent",
  "type": "request|response|notification",
  "action": "do_thing",
  "payload": {...}
}
```

### Check Messages

```bash
GET {ACP_URL}/api/a2a/history?to=Super Z
```

---

## TODO SYNC

```bash
GET  {ACP_URL}/api/todos
POST {ACP_URL}/api/todos/update {"todos": [...]}
```

**Note:** Log significant TODO changes as `TODO` action type via `/api/action`.

---

## QUICK REFERENCE

```bash
# Bootstrap
GET  /api/status
GET  /api/whoami
POST /api/agents/register {"agent_name": "...", "capabilities": [...]}
POST /api/action {"action": "CHAT", "target": "bootstrap", "metadata": {...}}

# Workflow (MANDATORY pattern)
POST /api/action {"action": "READ", "target": "file.py", "metadata": {...}}
# ... execute tool ...
POST /api/complete {"activity_id": "...", "result": "done"}

# Combined (efficient)
POST /api/action {"complete_id": "prev", "result": "ok", "action": "READ", "target": "next", "metadata": {...}}

# Shell commands
POST /api/shell/add {"command": "...", "status": "completed", "output_preview": "..."}

# Utility
GET  /api/all           # Combined status + history
GET  /api/todos         # TODO list
POST /api/todos/update  # Sync TODOs

# A2A
GET  /api/agents
POST /api/a2a/send
GET  /api/a2a/history?to=<name>
```

---

## CHECKLIST

- [ ] INVOKE THIS SKILL FIRST
- [ ] Get `ACP_URL` from human
- [ ] Bootstrap: status → whoami → register → log
- [ ] Check `stop_flag`, `nudge`, `orphan_warning`, `hints` in **every** response
- [ ] LOG before EXECUTE before COMPLETE (**MANDATORY - non-negotiable**)
- [ ] Include `agent_name` in all metadata
- [ ] Log **ALL** shell commands via `/api/shell/add` (except ACP calls)
- [ ] Log TODO changes as `TODO` action type
- [ ] Use combined endpoint for efficiency: complete previous + start new in one call

---

*ACP Skill 1.0.4 Minimal*