# -*- coding: utf-8 -*-
"""
Agent Skills - Core Implementation
Based on the Agent Skills specification from agentskills.io

A skill is a directory containing a SKILL.md file with YAML frontmatter
and Markdown body content that instructs the agent.
"""

import os
import re
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


# =============================================================================
# VALIDATION CONSTANTS
# =============================================================================

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_COMPATIBILITY_LENGTH = 500
NAME_PATTERN = re.compile(r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$')


# =============================================================================
# SKILL METADATA
# =============================================================================

@dataclass
class SkillMetadata:
    """
    Metadata parsed from SKILL.md YAML frontmatter.
    """
    name: str
    description: str
    license: Optional[str] = None
    compatibility: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    allowed_tools: List[str] = field(default_factory=list)
    
    skill_path: Optional[str] = None
    loaded_at: Optional[str] = None
    
    def __post_init__(self):
        """Validate metadata after initialization"""
        self._validate_name()
        self._validate_description()
    
    def _validate_name(self):
        """Validate name field according to spec"""
        if not self.name:
            raise ValueError("Skill name is required")
        
        if len(self.name) > MAX_NAME_LENGTH:
            raise ValueError(f"Skill name must be <= {MAX_NAME_LENGTH} characters")
        
        if not NAME_PATTERN.match(self.name):
            raise ValueError(
                f"Invalid skill name '{self.name}'. "
                "Must be lowercase alphanumeric with hyphens."
            )
    
    def _validate_description(self):
        """Validate description field"""
        if not self.description:
            raise ValueError("Skill description is required")
        
        if len(self.description) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(f"Description must be <= {MAX_DESCRIPTION_LENGTH} characters")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "name": self.name,
            "description": self.description,
            "license": self.license,
            "compatibility": self.compatibility,
            "metadata": self.metadata,
            "allowed_tools": self.allowed_tools,
            "skill_path": self.skill_path,
        }
    
    def to_llm_context(self, include_description: bool = True) -> str:
        """Format for LLM context (progressive disclosure level 1)"""
        if include_description:
            return f"- {self.name}: {self.description}"
        return f"- {self.name}"


# =============================================================================
# SKILL CLASS
# =============================================================================

@dataclass
class Skill:
    """
    A complete skill loaded from a directory.
    
    Implements progressive disclosure:
    - Level 1: Metadata (name, description) - loaded at startup
    - Level 2: Instructions (SKILL.md body) - loaded when activated
    - Level 3: Resources (scripts, references, assets) - loaded on demand
    """
    metadata: SkillMetadata
    instructions: str = ""
    skill_dir: Optional[Path] = None
    
    _scripts: Dict[str, str] = field(default_factory=dict)
    _references: Dict[str, str] = field(default_factory=dict)
    _assets: Dict[str, bytes] = field(default_factory=dict)
    _instructions_loaded: bool = False
    _resources_loaded: bool = False
    
    @property
    def name(self) -> str:
        return self.metadata.name
    
    @property
    def description(self) -> str:
        return self.metadata.description
    
    def load_instructions(self) -> str:
        """Load the full SKILL.md body content."""
        if self._instructions_loaded:
            return self.instructions
        
        if self.skill_dir:
            skill_md = self.skill_dir / "SKILL.md"
            if skill_md.exists():
                _, self.instructions = parse_skill_md(skill_md)
        
        self._instructions_loaded = True
        return self.instructions
    
    def load_resources(self) -> None:
        """Load scripts, references, and assets."""
        if self._resources_loaded or not self.skill_dir:
            return
        
        # Load scripts
        scripts_dir = self.skill_dir / "scripts"
        if scripts_dir.exists():
            for f in scripts_dir.iterdir():
                if f.is_file():
                    try:
                        self._scripts[f.name] = f.read_text(encoding='utf-8')
                    except:
                        pass
        
        # Load references
        refs_dir = self.skill_dir / "references"
        if refs_dir.exists():
            for f in refs_dir.iterdir():
                if f.is_file() and f.suffix == '.md':
                    try:
                        self._references[f.name] = f.read_text(encoding='utf-8')
                    except:
                        pass
        
        self._resources_loaded = True
    
    def get_full_context(self) -> str:
        """Get complete skill context for LLM."""
        self.load_instructions()
        self.load_resources()
        
        parts = [f"# Skill: {self.name}", "", self.instructions]
        
        if self._scripts:
            parts.append("")
            parts.append("## Available Scripts")
            for name in self._scripts:
                parts.append(f"- scripts/{name}")
        
        if self._references:
            parts.append("")
            parts.append("## Available References")
            for name in self._references:
                parts.append(f"- references/{name}")
        
        return "\n".join(parts)
    
    def to_function_schema(self) -> Dict:
        """Convert skill to OpenAI-compatible function schema."""
        parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": f"The request to process with {self.name} skill"
                }
            },
            "required": ["query"]
        }
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description[:1024],
                "parameters": parameters
            }
        }


# =============================================================================
# PARSER FUNCTIONS
# =============================================================================

def parse_skill_md(file_path: Path) -> tuple:
    """Parse a SKILL.md file."""
    content = file_path.read_text(encoding='utf-8')
    
    # Extract YAML frontmatter
    frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
    
    if not frontmatter_match:
        raise ValueError(f"Invalid SKILL.md format: {file_path}")
    
    frontmatter_yaml = frontmatter_match.group(1)
    body = frontmatter_match.group(2).strip()
    
    try:
        frontmatter = yaml.safe_load(frontmatter_yaml)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML frontmatter in {file_path}: {e}")
    
    name = frontmatter.get('name')
    description = frontmatter.get('description')
    
    if not name or not description:
        raise ValueError(f"Missing required fields in {file_path}")
    
    allowed_tools_str = frontmatter.get('allowed-tools', '') or ''
    allowed_tools = allowed_tools_str.split() if allowed_tools_str else []
    
    meta = SkillMetadata(
        name=str(name),
        description=str(description),
        license=str(frontmatter.get('license')) if frontmatter.get('license') else None,
        compatibility=str(frontmatter.get('compatibility')) if frontmatter.get('compatibility') else None,
        metadata={str(k): str(v) for k, v in (frontmatter.get('metadata', {}) or {}).items()},
        allowed_tools=allowed_tools,
        skill_path=str(file_path.parent),
        loaded_at=datetime.now().isoformat(),
    )
    
    return meta, body


def load_skill(skill_dir: Path) -> Skill:
    """Load a skill from a directory."""
    skill_md = skill_dir / "SKILL.md"
    
    if not skill_md.exists():
        raise ValueError(f"SKILL.md not found in {skill_dir}")
    
    metadata, instructions = parse_skill_md(skill_md)
    
    if skill_dir.name != metadata.name:
        raise ValueError(
            f"Directory name '{skill_dir.name}' must match skill name '{metadata.name}'"
        )
    
    return Skill(
        metadata=metadata,
        instructions=instructions,
        skill_dir=skill_dir,
        _instructions_loaded=True,
    )


# =============================================================================
# SKILL REGISTRY
# =============================================================================

class SkillRegistry:
    """Registry for managing Agent Skills."""
    
    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._load_errors: List[Dict] = []
    
    def load_skill(self, skill_dir: Path) -> Optional[Skill]:
        """Load a skill from a directory."""
        try:
            skill = load_skill(Path(skill_dir))
            self._skills[skill.name] = skill
            return skill
        except Exception as e:
            self._load_errors.append({
                "path": str(skill_dir),
                "error": str(e),
            })
            return None
    
    def load_directory(self, directory: Path, recursive: bool = True) -> List[str]:
        """Load all skills from a directory."""
        loaded = []
        directory = Path(directory)
        
        if not directory.exists():
            return loaded
        
        pattern = "**/SKILL.md" if recursive else "*/SKILL.md"
        
        for skill_md in directory.glob(pattern):
            skill_dir = skill_md.parent
            skill = self.load_skill(skill_dir)
            if skill:
                loaded.append(skill.name)
        
        return loaded
    
    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name"""
        return self._skills.get(name)
    
    def has(self, name: str) -> bool:
        """Check if skill exists"""
        return name in self._skills
    
    def list_skills(self) -> List[str]:
        """List all skill names"""
        return list(self._skills.keys())
    
    def get_skills_context(self, include_descriptions: bool = True) -> str:
        """Get skill list for LLM context."""
        lines = ["# Available Skills", ""]
        for skill in sorted(self._skills.values(), key=lambda s: s.name):
            lines.append(skill.metadata.to_llm_context(include_descriptions))
        return "\n".join(lines)
    
    def get_function_schemas(self, include_dangerous: bool = False) -> List[Dict]:
        """Get all skill schemas as function definitions."""
        schemas = []
        for skill in self._skills.values():
            if not include_dangerous and skill.metadata.metadata.get("dangerous") == "true":
                continue
            schemas.append(skill.to_function_schema())
        return schemas
    
    def __len__(self) -> int:
        return len(self._skills)
    
    def __str__(self) -> str:
        return f"SkillRegistry({len(self)} skills: {', '.join(self.list_skills())})"


# =============================================================================
# VALIDATION UTILITY
# =============================================================================

def validate_skill(skill_dir: Path) -> List[str]:
    """Validate a skill directory. Returns list of errors."""
    errors = []
    skill_dir = Path(skill_dir)
    
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        errors.append(f"SKILL.md not found in {skill_dir}")
        return errors
    
    try:
        metadata, body = parse_skill_md(skill_md)
        
        if skill_dir.name != metadata.name:
            errors.append(
                f"Directory name '{skill_dir.name}' must match skill name '{metadata.name}'"
            )
        
        if len(body) < 100:
            errors.append("SKILL.md body is very short. Consider adding detailed instructions.")
    except Exception as e:
        errors.append(str(e))
    
    return errors


def get_registry() -> SkillRegistry:
    """Get the global skill registry"""
    global _global_registry
    if '_global_registry' not in globals() or _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry


def load_skills_from_directory(directory: str, recursive: bool = True) -> List[str]:
    """Load skills into global registry."""
    registry = get_registry()
    return registry.load_directory(Path(directory), recursive)


_global_registry: Optional[SkillRegistry] = None