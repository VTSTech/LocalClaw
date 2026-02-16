# -*- coding: utf-8 -*-
"""
Agent Skills Framework

A standardized skill system for AI agents based on the Agent Skills specification.
Skills are defined as directories with SKILL.md files containing YAML frontmatter
and Markdown instructions.

Usage:
    from agent_skills import SkillRegistry
    
    # Load skills
    registry = SkillRegistry()
    registry.load_directory("./my_skills")
    
    # Get tools for function calling
    tools = registry.get_function_schemas()
"""

from .core.skill import (
    Skill,
    SkillMetadata,
    SkillRegistry,
    parse_skill_md,
    load_skill,
    validate_skill,
    get_registry,
    load_skills_from_directory,
)

__all__ = [
    "Skill",
    "SkillMetadata",
    "SkillRegistry",
    "parse_skill_md",
    "load_skill",
    "validate_skill",
    "get_registry",
    "load_skills_from_directory",
]

__version__ = "1.0.0"