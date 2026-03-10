---
name: datetime
description: Get current date, time, timezone information, and perform date calculations. Use when the user asks about today's date, current time, what day it is, timezones, or date arithmetic. Triggers on phrases like "what is today", "what's the date", "current time", "what day is it", "date now", "time now", "what is the date".
---

# DateTime Skill

Answer date/time questions by calling the `python_repl` tool.

## CRITICAL: Tool Name is `python_repl`

The tool is named `python_repl` (not "date", not "today", not "datetime", not anything else).

## CRITICAL: You MUST provide the `code` argument

The `python_repl` tool REQUIRES a `code` argument. NEVER call it with empty arguments.

**Correct tool call:**
```json
{
  "name": "python_repl",
  "arguments": {
    "code": "from datetime import datetime\nprint(datetime.now().strftime('Today is %A, %B %d, %Y.'))"
  }
}
```

**WRONG** - These will fail:
- `{"name": "today", "arguments": {}}` - NO TOOL CALLED "today", and NO CODE!
- `{"name": "date", "arguments": {}}` - NO TOOL CALLED "date", and NO CODE!
- `{"name": "datetime", "arguments": {}}` - NO TOOL CALLED "datetime", and NO CODE!
- `{"name": "python_repl", "arguments": {}}` - MISSING the required "code" argument!

## Code to Use

For "What is today's date?":
```python
from datetime import datetime
now = datetime.now()
print(f"Today is {now.strftime('%A, %B %d, %Y')}.")
```

For "What time is it?":
```python
from datetime import datetime
now = datetime.now()
print(f"The current time is {now.strftime('%I:%M %p')}.")
```

## Summary

1. Tool name MUST be: `python_repl`
2. Arguments MUST include: `{"code": "...your python code..."}`
3. NEVER call with empty arguments `{}`
4. The code should print the result
