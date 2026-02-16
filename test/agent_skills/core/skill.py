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
    
    Required fields:
        - name: Skill identifier (1-64 chars, lowercase alphanumeric + hyphens)
        - description: What the skill does and when to use it
    
    Optional fields:
        - license: License name or reference
        - compatibility: Environment requirements
        - metadata: Arbitrary key-value pairs
        - allowed_tools: Pre-approved tools the skill may use
    """
    name: str
    description: str
    license: Optional[str] = None
    compatibility: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    allowed_tools: List[str] = field(default_factory=list)
    
    # Internal tracking
    skill_path: Optional[str] = None
    loaded_at: Optional[str] = None
    
    def __post_init__(self):
        """Validate metadata after initialization"""
        self._validate_name()
        self._validate_description()
        if self.compatibility:
            self._validate_compatibility()
    
    def _validate_name(self):
        """Validate name field according to spec"""
        if not self.name:
            raise ValueError("Skill name is required")
        
        if len(self.name) > MAX_NAME_LENGTH:
            raise ValueError(f"Skill name must be <= {MAX_NAME_LENGTH} characters")
        
        if not NAME_PATTERN.match(self.name):
            raise ValueError(
                f"Invalid skill name '{self.name}'. "
                "Must be lowercase alphanumeric with hyphens, "
                "cannot start/end with hyphen or have consecutive hyphens."
            )
    
    def _validate_description(self):
        """Validate description field"""
        if not self.description:
            raise ValueError("Skill description is required")
        
        if len(self.description) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(f"Description must be <= {MAX_DESCRIPTION_LENGTH} characters")
    
    def _validate_compatibility(self):
        """Validate compatibility field"""
        if self.compatibility and len(self.compatibility) > MAX_COMPATIBILITY_LENGTH:
            raise ValueError(f"Compatibility must be <= {MAX_COMPATIBILITY_LENGTH} characters")
    
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
    
    # Cached resources
    _scripts: Dict[str, str] = field(default_factory=dict)
    _references: Dict[str, str] = field(default_factory=dict)
    _assets: Dict[str, bytes] = field(default_factory=dict)
    
    # State
    _instructions_loaded: bool = False
    _resources_loaded: bool = False
    
    @property
    def name(self) -> str:
        return self.metadata.name
    
    @property
    def description(self) -> str:
        return self.metadata.description
    
    def load_instructions(self) -> str:
        """
        Load the full SKILL.md body content.
        Progressive disclosure level 2.
        """
        if self._instructions_loaded:
            return self.instructions
        
        if self.skill_dir:
            skill_md = self.skill_dir / "SKILL.md"
            if skill_md.exists():
                _, self.instructions = parse_skill_md(skill_md)
        
        self._instructions_loaded = True
        return self.instructions
    
    def load_resources(self) -> None:
        """
        Load scripts, references, and assets.
        Progressive disclosure level 3.
        """
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
        
        # Load assets (as bytes)
        assets_dir = self.skill_dir / "assets"
        if assets_dir.exists():
            for f in assets_dir.iterdir():
                if f.is_file():
                    try:
                        self._assets[f.name] = f.read_bytes()
                    except:
                        pass
        
        self._resources_loaded = True
    
    def get_script(self, name: str) -> Optional[str]:
        """Get a script by name"""
        self.load_resources()
        return self._scripts.get(name)
    
    def get_reference(self, name: str) -> Optional[str]:
        """Get a reference document by name"""
        self.load_resources()
        return self._references.get(name)
    
    def get_asset(self, name: str) -> Optional[bytes]:
        """Get an asset by name"""
        self.load_resources()
        return self._assets.get(name)
    
    def list_scripts(self) -> List[str]:
        """List available scripts"""
        self.load_resources()
        return list(self._scripts.keys())
    
    def list_references(self) -> List[str]:
        """List available references"""
        self.load_resources()
        return list(self._references.keys())
    
    def list_assets(self) -> List[str]:
        """List available assets"""
        self.load_resources()
        return list(self._assets.keys())
    
    def get_full_context(self) -> str:
        """
        Get complete skill context for LLM.
        Includes instructions and references to resources.
        """
        self.load_instructions()
        
        parts = [f"# Skill: {self.name}", "", self.instructions]
        
        # Add resource references
        self.load_resources()
        
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
        
        if self._assets:
            parts.append("")
            parts.append("## Available Assets")
            for name in self._assets:
                parts.append(f"- assets/{name}")
        
        return "\n".join(parts)
    
    def to_dict(self) -> Dict:
        """Serialize skill to dictionary"""
        return {
            "metadata": self.metadata.to_dict(),
            "instructions_loaded": self._instructions_loaded,
            "resources_loaded": self._resources_loaded,
            "scripts": list(self._scripts.keys()),
            "references": list(self._references.keys()),
            "assets": list(self._assets.keys()),
        }


# =============================================================================
# PARSER FUNCTIONS
# =============================================================================

def parse_skill_md(file_path: Path) -> tuple:
    """
    Parse a SKILL.md file.
    
    Returns:
        Tuple of (SkillMetadata, markdown_body)
    
    Raises:
        ValueError: If required fields are missing or invalid
        yaml.YAMLError: If frontmatter is malformed
    """
    content = file_path.read_text(encoding='utf-8')
    
    # Extract YAML frontmatter
    frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
    
    if not frontmatter_match:
        raise ValueError(f"Invalid SKILL.md format: {file_path}. Must have YAML frontmatter.")
    
    frontmatter_yaml = frontmatter_match.group(1)
    body = frontmatter_match.group(2).strip()
    
    # Parse YAML
    try:
        frontmatter = yaml.safe_load(frontmatter_yaml)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML frontmatter in {file_path}: {e}")
    
    if not isinstance(frontmatter, dict):
        raise ValueError(f"Frontmatter must be a YAML mapping in {file_path}")
    
    # Extract required fields
    name = frontmatter.get('name')
    description = frontmatter.get('description')
    
    if not name:
        raise ValueError(f"Missing required field 'name' in {file_path}")
    if not description:
        raise ValueError(f"Missing required field 'description' in {file_path}")
    
    # Extract optional fields
    license_ = frontmatter.get('license')
    compatibility = frontmatter.get('compatibility')
    metadata = frontmatter.get('metadata', {}) or {}
    allowed_tools_str = frontmatter.get('allowed-tools', '') or ''
    
    # Parse allowed-tools (space-delimited string)
    allowed_tools = allowed_tools_str.split() if allowed_tools_str else []
    
    # Create metadata
    meta = SkillMetadata(
        name=str(name),
        description=str(description),
        license=str(license_) if license_ else None,
        compatibility=str(compatibility) if compatibility else None,
        metadata={str(k): str(v) for k, v in metadata.items()} if metadata else {},
        allowed_tools=allowed_tools,
        skill_path=str(file_path.parent),
        loaded_at=datetime.now().isoformat(),
    )
    
    return meta, body


def load_skill(skill_dir: Path) -> Skill:
    """
    Load a skill from a directory.
    
    Args:
        skill_dir: Path to the skill directory
        
    Returns:
        Skill object with metadata loaded
        
    Raises:
        ValueError: If SKILL.md is missing or invalid
    """
    skill_md = skill_dir / "SKILL.md"
    
    if not skill_md.exists():
        raise ValueError(f"SKILL.md not found in {skill_dir}")
    
    metadata, instructions = parse_skill_md(skill_md)
    
    # Validate directory name matches skill name
    if skill_dir.name != metadata.name:
        raise ValueError(
            f"Directory name '{skill_dir.name}' must match skill name '{metadata.name}'"
        )
    
    return Skill(
        metadata=metadata,
        instructions=instructions,
        skill_dir=skill_dir,
        _instructions_loaded=True,  # Already loaded during parsing
    )


# =============================================================================
# SKILL REGISTRY
# =============================================================================

class SkillRegistry:
    """
    Registry for managing Agent Skills.
    
    Supports:
    - Loading skills from directories
    - Progressive disclosure (metadata first, instructions on demand)
    - Skill search and discovery
    - LLM context generation
    """
    
    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._load_errors: List[Dict] = []
    
    def load_skill(self, skill_dir: Path) -> Optional[Skill]:
        """
        Load a skill from a directory.
        
        Returns:
            Skill if loaded successfully, None otherwise
        """
        try:
            skill = load_skill(Path(skill_dir))
            self._skills[skill.name] = skill
            return skill
        except Exception as e:
            self._load_errors.append({
                "path": str(skill_dir),
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            })
            return None
    
    def load_directory(self, directory: Path, recursive: bool = True) -> List[str]:
        """
        Load all skills from a directory.
        
        Args:
            directory: Root directory containing skill directories
            recursive: Search subdirectories for skills
            
        Returns:
            List of loaded skill names
        """
        loaded = []
        directory = Path(directory)
        
        if not directory.exists():
            return loaded
        
        # Look for SKILL.md files
        if recursive:
            pattern = "**/SKILL.md"
        else:
            pattern = "*/SKILL.md"
        
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
    
    def search(self, query: str) -> List[Skill]:
        """
        Search skills by name or description.
        Simple keyword matching.
        """
        query = query.lower()
        results = []
        
        for skill in self._skills.values():
            score = 0
            
            # Name match (higher priority)
            if query in skill.name.lower():
                score += 10
            
            # Description match
            if query in skill.description.lower():
                score += 5
            
            # Metadata keywords
            for key, value in skill.metadata.metadata.items():
                if query in key.lower() or query in value.lower():
                    score += 2
            
            if score > 0:
                results.append((score, skill))
        
        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in results]
    
    def get_skills_context(self, include_descriptions: bool = True) -> str:
        """
        Get skill list for LLM context.
        Progressive disclosure level 1 - metadata only.
        """
        lines = ["# Available Skills", ""]
        for skill in sorted(self._skills.values(), key=lambda s: s.name):
            lines.append(skill.metadata.to_llm_context(include_descriptions))
        return "\n".join(lines)
    
    def activate_skill(self, name: str) -> Optional[str]:
        """
        Activate a skill and return its full context.
        Progressive disclosure level 2 - includes instructions.
        """
        skill = self.get(name)
        if not skill:
            return None
        return skill.get_full_context()
    
    def get_load_errors(self) -> List[Dict]:
        """Get any errors that occurred during skill loading"""
        return self._load_errors.copy()
    
    def __len__(self) -> int:
        return len(self._skills)
    
    def __contains__(self, name: str) -> bool:
        return name in self._skills
    
    def __str__(self) -> str:
        return f"SkillRegistry({len(self)} skills: {', '.join(self.list_skills())})"


# =============================================================================
# GLOBAL REGISTRY
# =============================================================================

_global_registry: Optional[SkillRegistry] = None


def get_registry() -> SkillRegistry:
    """Get the global skill registry"""
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry


def load_skills_from_directory(directory: str, recursive: bool = True) -> List[str]:
    """
    Convenience function to load skills into global registry.
    """
    registry = get_registry()
    return registry.load_directory(Path(directory), recursive)


# =============================================================================
# VALIDATION UTILITY
# =============================================================================

def validate_skill(skill_dir: Path) -> List[str]:
    """
    Validate a skill directory.
    Returns list of validation errors (empty if valid).
    """
    errors = []
    skill_dir = Path(skill_dir)
    
    # Check SKILL.md exists
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        errors.append(f"SKILL.md not found in {skill_dir}")
        return errors
    
    # Try to parse
    try:
        metadata, body = parse_skill_md(skill_md)
        
        # Check directory name matches
        if skill_dir.name != metadata.name:
            errors.append(
                f"Directory name '{skill_dir.name}' must match skill name '{metadata.name}'"
            )
        
        # Check for recommended sections in body
        if len(body) < 100:
            errors.append("SKILL.md body is very short. Consider adding detailed instructions.")
        
        # Check instructions are not too long (recommended < 5000 tokens)
        approx_tokens = len(body.split()) * 1.3  # Rough estimate
        if approx_tokens > 5000:
            errors.append(
                f"SKILL.md body may be too long (~{int(approx_tokens)} tokens). "
                "Consider splitting into reference files."
            )
        
    except Exception as e:
        errors.append(str(e))
    
    return errors