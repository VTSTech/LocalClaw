---
name: datetime
description: Get current date, time, timezone information, and perform date calculations. Use when the user asks about today's date, current time, what day it is, timezones, or date arithmetic. Triggers on phrases like "what is today", "what's the date", "current time", "what day is it", "date now", "time now", "what is the date".
---

# DateTime Skill

Answer date/time questions by calling the `python_repl` tool.

## CRITICAL: Tool Name is `python_repl`

The tool is named `python_repl` (not "date", not "today", not anything else).

**Correct tool call:**
```
Tool name: python_repl
Arguments: {"code": "from datetime import datetime\nprint(datetime.now().strftime('Today is %A, %B %d, %Y.'))"}
```

**WRONG** - These will fail:
- `{"name": "today", ...}` - NO TOOL CALLED "today"
- `{"name": "date", ...}` - NO TOOL CALLED "date"
- `{"name": "get_date", ...}` - NO TOOL CALLED "get_date"

## Code to Use

For "What is today's date?":
```
from datetime import datetime
now = datetime.now()
print(f"Today is {now.strftime('%A, %B %d, %Y')}.")
```

For "What time is it?":
```
from datetime import datetime
now = datetime.now()
print(f"The current time is {now.strftime('%I:%M %p')}.")
```

## Summary

1. Tool name MUST be: `python_repl`
2. Argument MUST be: `{"code": "...your python code..."}`
3. The code should print the result
