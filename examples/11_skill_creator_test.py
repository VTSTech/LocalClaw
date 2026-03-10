"""
examples/11_skill_creator_test.py
---------------------------------
Test skill-creator with models from smallest to largest.
Goal: Create a file-conversion skill.

Run: python examples/11_skill_creator_test.py

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

import os
import sys
import time
import shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw.skills import SkillLoader, SkillRegistry
from localclaw import Agent, OllamaClient
from localclaw.tools.builtins import make_builtin_registry


# Models ordered by size (smallest first)
MODEL_ORDER = [
    # 270M
    "gemma3:270m",
    "functiongemma:270m",
    # 350M
    "granite4:350m",
    # 494M-500M
    "qwen2.5:0.5b",
    "qwen2.5-coder:0.5b-instruct-q4_k_m",
    # 600M
    "qwen3:0.6b",
    # 1B
    "granite3.1-moe:1b",
    "llama3.2:1b",
    "tinyllama:latest",
    # 1.5B
    "qwen2-math:1.5b",
    # 3.8B
    "phi3.5:3.8b",
]

# The skill we want to create
SKILL_NAME = "file-converter"
SKILL_PATH_EXPECTED = "SKILL.md"

# Simplified skill content for small models
SKILL_CONTENT = """---
name: file-converter
description: Convert files between formats like markdown, HTML, CSV, JSON. Use when user needs to transform a file from one format to another.
---

# File Converter

Convert files between common formats.

## Supported Conversions

- Markdown <-> HTML
- CSV <-> JSON
- Plain text <-> Markdown

## How to Use

1. Read source file with read_file
2. Transform the content
3. Write output with write_file
"""


def test_model(client: OllamaClient, model: str, skills_dir: str) -> dict:
    """Test if a model can create the file-converter skill."""
    
    skill_dir = os.path.join(skills_dir, SKILL_NAME)
    skill_path = os.path.join(skill_dir, "SKILL.md")
    
    # Clean up previous attempt
    if os.path.exists(skill_dir):
        shutil.rmtree(skill_dir)
    os.makedirs(skill_dir, exist_ok=True)
    
    # Load skill-creator with explicit path
    loader = SkillLoader(skills_dir)
    skill_creator = loader.load("skill-creator")
    
    registry = SkillRegistry()
    registry.add(skill_creator)
    
    # Create agent with skill-creator knowledge
    tools = make_builtin_registry().subset(["write_file", "read_file"])
    
    # Get skill prompt
    skill_prompt = registry.to_system_prompt_addition()
    
    agent = Agent(
        model=model,
        tools=tools,
        system_prompt="You create skills using the write_file tool. " + skill_prompt,
        max_steps=5,
        client=client,
        model_options={"temperature": 0.3},
    )
    
    # Clear prompt for small models
    prompt = f"""Create a new skill called '{SKILL_NAME}' for converting files between formats.

Use the write_file tool to create: {skill_path}

The SKILL.md should have:
1. YAML frontmatter with name and description
2. Brief instructions for file conversion

Write the file now."""

    start = time.time()
    steps_info = []
    
    try:
        result = agent.run(prompt)
        elapsed = time.time() - start
        
        # Collect step info
        for s in result.steps:
            if s.type == "tool_call":
                steps_info.append(f"TOOL: {s.tool_name}({list(s.tool_args.keys())[:2]})")
            elif s.type == "tool_result":
                steps_info.append(f"  -> {str(s.content)[:50]}")
        
        # Check if file was created
        success = os.path.exists(skill_path)
        
        if success:
            with open(skill_path) as f:
                content = f.read()
            has_frontmatter = "---" in content and "name:" in content
            has_description = "description:" in content.lower()
            
            return {
                "model": model,
                "success": success and has_frontmatter,
                "elapsed": elapsed,
                "steps": len(result.steps),
                "steps_info": steps_info,
                "file_exists": success,
                "has_frontmatter": has_frontmatter,
                "content_length": len(content),
                "content_preview": content[:400] if success else None,
            }
        else:
            return {
                "model": model,
                "success": False,
                "elapsed": elapsed,
                "steps": len(result.steps),
                "steps_info": steps_info,
                "error": "File not created",
            }
            
    except Exception as e:
        elapsed = time.time() - start
        return {
            "model": model,
            "success": False,
            "elapsed": elapsed,
            "steps": 0,
            "steps_info": steps_info,
            "error": f"{type(e).__name__}: {str(e)[:100]}",
        }


def main():
    print("🦞 LocalClaw R01 - Skill Creator Test")
    print("=" * 60)
    print(f"Goal: Create '{SKILL_NAME}' skill")
    print(f"Testing models from smallest to largest...")
    print("=" * 60)
    
    client = OllamaClient()
    
    if not client.is_running():
        print("❌ Ollama is not running!")
        return
    
    available = client.list_models()
    print(f"\nAvailable models: {len(available)}")
    
    # Find models to test (in order)
    models_to_test = []
    for m in MODEL_ORDER:
        found = None
        for avail in available:
            # Match by model family name
            if m.split(":")[0] in avail or m in avail:
                found = avail
                break
        if found and found not in models_to_test:
            models_to_test.append(found)
    
    print(f"Testing order: {models_to_test}")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    skills_dir = os.path.join(base_dir, "localclaw", "skills")
    
    # Test each model
    results = []
    for model in models_to_test:
        print(f"\n{'='*60}")
        print(f"🧪 Model: {model}")
        print("="*60)
        
        result = test_model(client, model, skills_dir)
        results.append(result)
        
        # Print result
        if result.get("success"):
            print(f"\n✅ SUCCESS!")
            print(f"   Time: {result['elapsed']:.1f}s")
            print(f"   Steps: {result['steps']}")
            print(f"   Content length: {result['content_length']} chars")
            if result.get("content_preview"):
                print(f"   Preview:\n{result['content_preview']}")
            print("\n🎉 Skill created successfully! Stopping.")
            break
        else:
            print(f"\n❌ Failed")
            if result.get("error"):
                print(f"   Error: {result['error']}")
            print(f"   Time: {result.get('elapsed', 0):.1f}s")
            if result.get("steps"):
                print(f"   Steps: {result['steps']}")
            for step in result.get("steps_info", [])[:8]:
                print(f"      {step}")
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print("="*60)
    
    for r in results:
        status = "✅" if r.get("success") else "❌"
        time_str = f"{r.get('elapsed', 0):.1f}s"
        print(f"  {status} {r['model']:<40} {time_str:>8}")
        if r.get("error"):
            print(f"      Error: {r['error'][:60]}")
    
    # Check final result
    skill_path = os.path.join(skills_dir, SKILL_NAME, "SKILL.md")
    if os.path.exists(skill_path):
        print(f"\n✅ Final skill created at: {skill_path}")
        with open(skill_path) as f:
            content = f.read()
        print(f"\n{content}")
    else:
        print(f"\n❌ No skill was successfully created")
        print("\n💡 Consider using a larger model or adjusting the prompt")


if __name__ == "__main__":
    main()
