# skill-creator

A cross-platform agent skill for creating other agent skills. Works on any platform that supports the Agent Skills Open Standard (SKILL.md format).

## Installation

### LocalClaw
```bash
# The skill is already installed in localclaw/skills/skill-creator/
# Just use --skills skill-creator when starting a chat
python cli.py chat --skills skill-creator --tools shell,write_file
```

### Claude Code
```bash
git clone https://github.com/FrancyJGLisboa/agent-skill-creator.git ~/.claude/skills/skill-creator
```

### Cursor
```bash
git clone https://github.com/FrancyJGLisboa/agent-skill-creator.git .cursor/rules/skill-creator
```

### GitHub Copilot
```bash
git clone https://github.com/FrancyJGLisboa/agent-skill-creator.git .github/skills/skill-creator
```

### Universal (Codex CLI, Gemini CLI, etc.)
```bash
git clone https://github.com/FrancyJGLisboa/agent-skill-creator.git ~/.agents/skills/skill-creator
```

## Usage

Activate the skill by invoking it:

```
/skill-creator Create a skill for analyzing CSV files
/skill-creator Automate my weekly report workflow
/skill-creator Turn my Python script into a reusable skill
```

The skill will:
1. **Discovery**: Research and understand your workflow
2. **Design**: Create a specification with use cases
3. **Architecture**: Structure the skill directory
4. **Detection**: Write an activation description
5. **Implementation**: Create all files with validation

## What Gets Created

```
your-skill/
├── SKILL.md          # Skill instructions (YAML frontmatter + markdown)
├── scripts/          # Python scripts (functional, no placeholders)
├── references/       # Detailed documentation
├── assets/           # Templates, schemas, data files
└── README.md         # Installation instructions
```

## Validation

After creating a skill, validate it:

```bash
python scripts/validate.py path/to/your-skill/
python scripts/security_scan.py path/to/your-skill/
```

## Quality Standards

Every generated skill:
- Has complete, functional code (no TODOs, no placeholders)
- Follows the Agent Skills Open Standard
- Is cross-platform compatible
- Passes validation and security scans
- Uses environment variables for secrets

## License

MIT License - See SKILL.md for details.

## Author

Francy Lisboa Charuto

Based on the Agent Skills Open Standard: https://agentskills.io/
