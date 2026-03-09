# Pipeline Phases Reference

Detailed instructions for each phase of skill creation.

## Phase 1: Discovery

### Objective
Research and understand the domain, APIs, data sources, and tools needed for the skill.

### Activities
1. **Read all user-provided material**
   - Links: Follow and read web pages
   - Files: Read local files
   - PDFs: Parse and extract key information
   - Code: Study existing implementations

2. **Research APIs and services**
   - Compare options by cost, rate limits, data quality
   - Check documentation quality
   - Identify authentication requirements
   - Note any SDK availability

3. **Identify data sources**
   - Primary data sources
   - Backup/fallback options
   - Data formats and schemas

4. **Document findings**
   - Create internal notes about the domain
   - List recommended APIs with justification

### Output
- Clear understanding of the problem domain
- List of required APIs and libraries
- Data source decisions with justification

## Phase 2: Design

### Objective
Create a detailed specification for the skill.

### Activities
1. **Define use cases (4-6 priority cases)**
   For each use case:
   - Name and objective
   - Required inputs
   - Expected outputs
   - Methodology/steps

2. **Specify data flows**
   - Input formats and validation
   - Processing steps
   - Output formats

3. **Identify edge cases**
   - Error conditions
   - Missing data scenarios
   - Rate limiting considerations

4. **Define success criteria**
   - How to measure if the skill worked correctly
   - What constitutes a good vs bad output

### Output
- Complete internal specification document
- Use case definitions
- Edge case handling plan

## Phase 3: Architecture

### Objective
Structure the skill directory appropriately.

### Decision: Simple vs Complex

**Simple Skill** (recommended for most cases):
- Single SKILL.md
- scripts/ for Python code
- references/ for detailed docs
- assets/ for templates

**Complex Suite** (rare):
- Multiple component skills
- Shared resources
- Requires orchestration

### Directory Structure
```
skill-name/
├── SKILL.md          # Main instructions (<500 lines)
├── scripts/          # Python scripts
│   ├── __init__.py
│   └── main.py
├── references/       # Detailed docs
│   └── details.md
├── assets/           # Templates, configs
└── README.md         # Install instructions
```

## Phase 4: Detection

### Objective
Create an effective activation description.

### Guidelines
1. **Length**: <=1024 characters
2. **Content**:
   - What the skill does
   - When to use it (trigger phrases)
   - Key domain keywords
3. **Style**: Clear, keyword-rich, not too generic

### Example
```yaml
description: >-
  Convert between common file formats (CSV, JSON, XML, YAML, Excel).
  Activates when users need to convert, transform, or migrate data
  between formats. Triggers on phrases like convert to, transform to,
  change format, export as, import from, migrate data.
```

## Phase 5: Implementation

### Objective
Create all files with full implementation.

### File Creation Order
1. Create directory structure
2. Write SKILL.md with proper frontmatter
3. Implement Python scripts (no placeholders)
4. Write reference documentation
5. Create assets (templates, configs)
6. Write README.md
7. Validate
8. Security scan
9. Report to user

### Code Standards
- Complete implementations (no `pass` or `TODO`)
- Type hints on public functions
- Docstrings on all functions
- Error handling with informative messages
- Environment variables for secrets

### Validation Checklist
- [ ] SKILL.md has valid frontmatter
- [ ] name field: 1-64 chars, lowercase, hyphens, ends with -skill
- [ ] description field: 1-1024 chars
- [ ] SKILL.md body: <500 lines
- [ ] No hardcoded API keys
- [ ] Scripts have no TODOs or empty functions

### Security Checklist
- [ ] No API keys in code
- [ ] No .env files included
- [ ] No injection vulnerabilities
- [ ] Secrets use environment variables
