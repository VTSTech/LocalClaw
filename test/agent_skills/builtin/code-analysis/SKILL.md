---
name: code-analysis
description: Analyze code quality, find bugs, review code structure, and understand codebases. Use when reviewing code, finding issues in code, understanding unfamiliar code, or improving code quality.
license: MIT
metadata:
  author: VTSBot
  version: "1.0"
allowed-tools: Read Write Bash(git:*) Bash(grep:*) Bash(find:*)
---

# Code Analysis Skill

This skill provides comprehensive code analysis and review capabilities.

## When to Use This Skill

- User asks for code review or feedback
- User wants to find bugs or issues
- User needs to understand an unfamiliar codebase
- User wants to improve code quality
- User asks about code structure or architecture

## Capabilities

### Code Structure Analysis

Understand project organization:

```bash
# Find all source files
find . -type f \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.java" \)

# Count lines of code by language
find . -name "*.py" -exec wc -l {} + | tail -1

# Find main entry points
grep -r "if __name__" --include="*.py" .
grep -r "def main" --include="*.py" .
```

### Pattern Detection

Find common patterns and anti-patterns:

```bash
# Find TODOs and FIXMEs
grep -rn "TODO\|FIXME" --include="*.py" .

# Find potential security issues
grep -rn "eval\|exec\|shell=True" --include="*.py" .

# Find hardcoded credentials (potential)
grep -rn "password\s*=\s*['\"]" --include="*.py" .

# Find unused imports
grep -r "^import\|^from" --include="*.py" . | sort | uniq -c | sort -rn
```

### Dependency Analysis

Analyze project dependencies:

```bash
# Python dependencies
cat requirements.txt 2>/dev/null || cat pyproject.toml 2>/dev/null

# Node.js dependencies
cat package.json 2>/dev/null | jq '.dependencies, .devDependencies'

# Find imported modules
grep -rh "^import\|^from" --include="*.py" . | sort | uniq
```

### Code Metrics

Calculate code quality metrics:

```bash
# Function complexity (approximate)
grep -rn "def " --include="*.py" . | wc -l

# Average function length
find . -name "*.py" -exec awk '/^def /{start=NR} /^$/{if(start) print NR-start}' {} \;

# Cyclomatic complexity indicators
grep -rn "if\|elif\|for\|while\|and\|or" --include="*.py" . | wc -l
```

## Step-by-Step Analysis Process

### 1. Initial Project Scan

```bash
# Identify project type
ls -la
cat README.md 2>/dev/null | head -50

# Find configuration files
ls *.{json,yaml,yml,toml,ini,cfg} 2>/dev/null
```

### 2. Structure Overview

```bash
# Directory structure
find . -type d -not -path "*/\.*" | head -20

# Main source directories
ls -la src/ lib/ app/ 2>/dev/null
```

### 3. Entry Points

```bash
# Find main files
find . -name "main.py" -o -name "index.js" -o -name "app.py" -o -name "__main__.py"

# Find CLI entry points
grep -rn "argparse\|click\|typer" --include="*.py" .
```

### 4. Code Quality Check

```bash
# Run linter (if available)
ruff check . 2>/dev/null || flake8 . 2>/dev/null || pylint **/*.py 2>/dev/null

# Check for type hints (Python)
grep -rn ": " --include="*.py" . | wc -l

# Check for docstrings
grep -rn '"""' --include="*.py" . | wc -l
```

## Code Review Checklist

When reviewing code, check for:

### Security
- [ ] No hardcoded credentials
- [ ] Input validation present
- [ ] SQL injection prevention
- [ ] XSS prevention (for web)
- [ ] Proper error handling

### Quality
- [ ] Consistent code style
- [ ] Adequate documentation
- [ ] Type hints (Python) / TypeScript
- [ ] Unit tests present
- [ ] No code duplication (DRY)

### Architecture
- [ ] Clear separation of concerns
- [ ] Proper module organization
- [ ] Dependency injection where appropriate
- [ ] No circular dependencies

## Common Issues and Fixes

### Issue: Missing Error Handling

```python
# Bad
result = some_function()

# Good
try:
    result = some_function()
except SpecificError as e:
    logger.error(f"Failed: {e}")
    result = default_value
```

### Issue: SQL Injection Risk

```python
# Bad
query = f"SELECT * FROM users WHERE id = {user_id}"

# Good
query = "SELECT * FROM users WHERE id = ?"
cursor.execute(query, (user_id,))
```

### Issue: Magic Numbers

```python
# Bad
if status == 200:

# Good
HTTP_OK = 200
if status == HTTP_OK:
```

## Output Format

When presenting analysis results:

```
## Code Analysis Report

### Overview
- Language: Python
- Files: 42
- Lines of Code: ~5,000

### Structure
[Directory tree]

### Key Findings
1. [Issue/observation]
2. [Issue/observation]

### Recommendations
1. [Actionable recommendation]
2. [Actionable recommendation]

### Metrics
- Functions: X
- Classes: Y
- Test Coverage: Z%
```

## Dependencies

Optional tools for enhanced analysis:
- `ruff` or `flake8` - Python linting
- `eslint` - JavaScript linting
- `pylint` - Comprehensive Python analysis
- `mypy` - Python type checking
