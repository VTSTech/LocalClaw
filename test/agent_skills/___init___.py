# -*- coding: utf-8 -*-
"""
Agent Skills Framework

A standardized skill system for AI agents based on the Agent Skills specification.
Skills are defined as directories with SKILL.md files containing YAML frontmatter
and Markdown instructions.

Usage:
    from agent_skills import SkillRegistry, SkillAwareAgent
    
    # Create agent with skills
    agent = SkillAwareAgent(skills_dirs=["./my_skills"])
    
    # Execute user request
    response = agent.execute("Extract text from this PDF")
"""

from .core import (
    # Core classes
    Skill,
    SkillMetadata,
    SkillRegistry,
    
    # Parsing functions
    parse_skill_md,
    load_skill,
    validate_skill,
    
    # Convenience functions
    get_registry,
    load_skills_from_directory,
)

from .agent import (
    SkillAwareAgent,
    run_agent,
)

__all__ = [
    # Core
    "Skill",
    "SkillMetadata",
    "SkillRegistry",
    
    # Parsing
    "parse_skill_md",
    "load_skill",
    "validate_skill",
    
    # Convenience
    "get_registry",
    "load_skills_from_directory",
    
    # Agent
    "SkillAwareAgent",
    "run_agent",
]

__version__ = "1.0.0"