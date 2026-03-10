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
import yaml
import re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw.skills import SkillLoader, SkillRegistry
from localclaw import Agent, OllamaClient, StepResult
from localclaw.tools.builtins import make_builtin_registry


# Configuration
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

SKILL_NAME = "file-converter"
VERBOSE = os.environ.get("LOCALCLAW_VERBOSE", "1") == "1"
TIMEOUT = int(os.environ.get("LOCALCLAW_TIMEOUT", "180"))  # 3 minutes per model


def print_step(step: StepResult, indent="  "):
    """Print step information with details."""
    if step.type == "tool_call":
        args_str = ", ".join(f"{k}={repr(v)[:30]}" for k, v in (step.tool_args or {}).items())
        print(f"{indent}🔧 TOOL CALL: {step.tool_name}({args_str})")
    elif step.type == "tool_result":
        preview = step.content[:100] + "..." if len(step.content) > 100 else step.content
        print(f"{indent}📦 RESULT: {preview.replace(chr(10), ' ')}")
    elif step.type == "final":
        preview = step.content[:150] + "..." if len(step.content) > 150 else step.content
        print(f"{indent}💬 FINAL: {preview.replace(chr(10), ' ')}")


def validate_skill(content: str) -> dict:
    """Validate a skill file and return validation results."""
    result = {
        "valid": False,
        "has_frontmatter": False,
        "has_name": False,
        "has_description": False,
        "has_instructions": False,
        "frontmatter_valid": False,
        "partial": False,
        "errors": [],
        "content_length": len(content),
    }
    
    # Check for frontmatter
    if not content.strip().startswith("---"):
        result["errors"].append("Missing YAML frontmatter (should start with ---)")
        return result
    
    result["has_frontmatter"] = True
    
    # Extract frontmatter
    parts = content.split("---", 2)
    if len(parts) < 3:
        result["errors"].append("Missing closing ---")
        # Try regex fallback for name/description
        if re.search(r'name:\s*\S+', content):
            result["has_name"] = True
        if re.search(r'description:\s*\S+', content):
            result["has_description"] = True
        result["partial"] = result["has_name"] and result["has_description"]
        return result
    
    frontmatter_text = parts[1].strip()
    body = parts[2].strip() if len(parts) > 2 else ""
    
    # Parse YAML
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        if not isinstance(frontmatter, dict):
            result["errors"].append(f"Frontmatter is not a dict: {type(frontmatter)}")
            return result
        
        result["frontmatter_valid"] = True
        
        # Check required fields
        if "name" in frontmatter and frontmatter["name"]:
            result["has_name"] = True
        else:
            result["errors"].append("Missing 'name' in frontmatter")
        
        if "description" in frontmatter and frontmatter["description"]:
            result["has_description"] = True
        else:
            result["errors"].append("Missing 'description' in frontmatter")
            
    except yaml.YAMLError as e:
        result["errors"].append(f"YAML parse error: {e}")
        # Still check for name/description with regex fallback
        if re.search(r'name:\s*\S+', content):
            result["has_name"] = True
        if re.search(r'description:\s*\S+', content):
            result["has_description"] = True
    
    # Check body has instructions (need at least some content)
    if body and len(body) > 20:
        result["has_instructions"] = True
    else:
        result["errors"].append("Body is missing or too short (need instructions)")
    
    # Calculate validity
    result["valid"] = (
        result["has_frontmatter"] and 
        result["has_name"] and 
        result["has_description"] and 
        result["has_instructions"]
    )
    
    # Partial success - has frontmatter with name and description
    result["partial"] = (
        result["has_frontmatter"] and 
        result["has_name"] and 
        result["has_description"] and 
        not result["valid"]
    )
    
    return result


def check_tool_used(run, tool_name: str) -> bool:
    """Check if a specific tool was called."""
    for step in run.steps:
        if step.type == "tool_call" and step.tool_name == tool_name:
            return True
    return False


def test_model(client: OllamaClient, model: str, skills_dir: str) -> dict:
    """Test if a model can create the file-converter skill."""
    
    skill_dir = os.path.join(skills_dir, SKILL_NAME)
    skill_path = os.path.join(skill_dir, "SKILL.md")
    
    # Clean up previous attempt
    if os.path.exists(skill_dir):
        shutil.rmtree(skill_dir)
    os.makedirs(skill_dir, exist_ok=True)
    
    # Load skill-creator
    loader = SkillLoader(skills_dir)
    skill_creator = loader.load("skill-creator")
    
    if not skill_creator:
        return {
            "model": model,
            "success": False,
            "elapsed": 0,
            "steps": 0,
            "error": "Could not load skill-creator",
        }
    
    registry = SkillRegistry()
    registry.add(skill_creator)
    
    # Create agent with tools
    tools = make_builtin_registry().subset(["write_file", "read_file"])
    skill_prompt = registry.to_system_prompt_addition()
    
    agent = Agent(
        model=model,
        tools=tools,
        system_prompt="You create AgentSkills using the write_file tool. " + skill_prompt,
        max_steps=8,
        client=client,
        model_options={"temperature": 0.3},
        on_step=lambda s: print_step(s, "    ") if VERBOSE else None,
    )
    
    # Clear, explicit prompt with example
    prompt = f"""Create a new skill called '{SKILL_NAME}' for converting files between formats.

Use the write_file tool to create: {skill_path}

The SKILL.md file MUST have this exact structure:

---
name: file-converter
description: Convert files between formats like CSV, JSON, HTML, Markdown.
---

# File Converter

Instructions for converting files between formats.

## Supported Formats
- CSV to JSON
- JSON to CSV  
- Markdown to HTML
- HTML to Markdown

## Usage
1. Read source file
2. Parse and transform
3. Write output file

Write the complete file now with ALL sections included."""

    start = time.time()
    steps_info = []
    tool_calls = []
    
    try:
        result = agent.run(prompt)
        elapsed = time.time() - start
        
        # Collect detailed step info
        for s in result.steps:
            if s.type == "tool_call":
                tool_calls.append(s.tool_name)
                steps_info.append({
                    "type": "tool_call",
                    "tool": s.tool_name,
                    "args": list((s.tool_args or {}).keys()),
                })
            elif s.type == "tool_result":
                steps_info.append({
                    "type": "tool_result",
                    "preview": str(s.content)[:80],
                })
        
        # Check if file was created
        if not os.path.exists(skill_path):
            return {
                "model": model,
                "success": False,
                "elapsed": elapsed,
                "steps": len(result.steps),
                "steps_info": steps_info,
                "tool_calls": tool_calls,
                "error": "File not created - write_file tool may not have been called",
                "final_answer": result.final_answer[:200] if result.final_answer else None,
            }
        
        # Read and validate the created file
        with open(skill_path) as f:
            content = f.read()
        
        validation = validate_skill(content)
        
        return {
            "model": model,
            "success": validation["valid"],
            "elapsed": elapsed,
            "steps": len(result.steps),
            "steps_info": steps_info,
            "tool_calls": tool_calls,
            "file_exists": True,
            "validation": validation,
            "content_preview": content[:500],
            "final_answer": result.final_answer[:200] if result.final_answer else None,
        }
            
    except Exception as e:
        elapsed = time.time() - start
        return {
            "model": model,
            "success": False,
            "elapsed": elapsed,
            "steps": 0,
            "steps_info": steps_info,
            "tool_calls": tool_calls,
            "error": f"{type(e).__name__}: {str(e)[:150]}",
        }


def main():
    print("🦞 LocalClaw R01 - Skill Creator Test")
    print("=" * 60)
    print(f"Goal: Create '{SKILL_NAME}' skill with valid YAML frontmatter")
    print(f"Testing models from smallest to largest...")
    print(f"Verbose: {VERBOSE}, Timeout: {TIMEOUT}s")
    print("=" * 60)
    
    client = OllamaClient()
    
    if not client.is_running():
        print("❌ Ollama is not running!")
        return False
    
    available = client.list_models()
    print(f"\nAvailable models: {len(available)}")
    
    # Find models to test (in order)
    models_to_test = []
    for m in MODEL_ORDER:
        found = None
        for avail in available:
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
    found_success = False
    
    for model in models_to_test:
        print(f"\n{'='*60}")
        print(f"🧪 Model: {model}")
        print("=" * 60)
        
        result = test_model(client, model, skills_dir)
        results.append(result)
        
        # Print result details
        if result.get("success"):
            print(f"\n✅ SUCCESS!")
            print(f"   Time: {result['elapsed']:.1f}s")
            print(f"   Steps: {result['steps']}")
            print(f"   Tools used: {result.get('tool_calls', [])}")
            if result.get("validation"):
                v = result["validation"]
                print(f"   Validation: name={v['has_name']}, desc={v['has_description']}, body={v['has_instructions']}")
            if result.get("content_preview"):
                print(f"\n📄 Created skill preview:")
                print("-" * 40)
                print(result["content_preview"][:400])
                print("-" * 40)
            print("\n🎉 Skill created successfully! Stopping.")
            found_success = True
            break
        else:
            print(f"\n❌ Failed")
            if result.get("error"):
                print(f"   Error: {result['error']}")
            print(f"   Time: {result.get('elapsed', 0):.1f}s")
            print(f"   Steps: {result.get('steps', 0)}")
            print(f"   Tools used: {result.get('tool_calls', [])}")
            if result.get("validation"):
                print(f"   Validation errors: {result['validation'].get('errors', [])}")
            if result.get("final_answer"):
                print(f"   Final answer: {result['final_answer'][:150]}...")
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print("=" * 60)
    
    for r in results:
        status = "✅" if r.get("success") else "❌"
        time_str = f"{r.get('elapsed', 0):.1f}s"
        tools = r.get("tool_calls", [])
        tools_str = f" [{', '.join(tools[:3])}]" if tools else ""
        print(f"  {status} {r['model']:<40} {time_str:>8}{tools_str}")
        if r.get("error") and not r.get("success"):
            print(f"      → {r['error'][:70]}")
    
    # Check final result
    skill_path = os.path.join(skills_dir, SKILL_NAME, "SKILL.md")
    if os.path.exists(skill_path):
        print(f"\n✅ Final skill created at: {skill_path}")
        with open(skill_path) as f:
            content = f.read()
        print(f"\n📄 Full skill content:")
        print("-" * 40)
        print(content)
        print("-" * 40)
    else:
        print(f"\n❌ No skill was successfully created")
        print("\n💡 Consider:")
        print("   - Using a larger model (≥3B params)")
        print("   - Increasing timeout: LOCALCLAW_TIMEOUT=300")
        print("   - Enable verbose: LOCALCLAW_VERBOSE=1")
    
    return found_success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
