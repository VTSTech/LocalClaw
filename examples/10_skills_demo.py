"""
examples/10_skills_demo.py
--------------------------
Demonstrate the Agent Skills system.

This demo shows:
1. Discovering skills (loading metadata)
2. Disclosing available skills as catalog (tier 1)
3. Agent using write_file tool to CREATE a new skill

Run: python examples/10_skills_demo.py

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


def main():
    print("🦞 LocalClaw R01 - Skills Demo")
    print("=" * 60)
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    skills_dir = os.path.join(base_dir, "localclaw", "skills")
    
    # ========================================
    # STEP 1: DISCOVER skills
    # ========================================
    print("\n📦 Step 1: Discovering skills...")
    loader = SkillLoader()
    skills = loader.list_skills()
    print(f"   Found {len(skills)} skill(s): {skills}")
    
    skill_creator = loader.load("skill-creator")
    print(f"   ✓ Loaded: {skill_creator.name}")
    print(f"   ✓ Description: {skill_creator.description[:60]}...")
    print(f"   ✓ Instructions: {len(skill_creator.instructions)} chars")
    print(f"   ✓ Has scripts/: {skill_creator.scripts_dir is not None}")
    print(f"   ✓ Has references/: {skill_creator.references_dir is not None}")
    print(f"   ✓ Has assets/: {skill_creator.assets_dir is not None}")
    
    # Show what's in the scripts directory
    if skill_creator.scripts_dir:
        scripts = list(skill_creator.scripts_dir.glob("*.py"))
        print(f"   ✓ Scripts: {[s.name for s in scripts[:3]]}...")
    
    # ========================================
    # STEP 2: DISCLOSE catalog (tier 1)
    # ========================================
    print("\n" + "=" * 60)
    print("📋 Step 2: Building skill catalog (tier 1)")
    print("   (Only name + description - NOT full instructions)")
    print("=" * 60)
    
    registry = SkillRegistry()
    registry.add(skill_creator)
    
    catalog = registry.to_system_prompt_addition()
    print(f"   Catalog size: {len(catalog)} chars")
    print("   Preview (first 10 lines):")
    for line in catalog.split("\n")[2:12]:
        print(f"      {line[:60]}")
    
    # ========================================
    # STEP 3: CREATE AGENT with TOOLS
    # ========================================
    print("\n" + "=" * 60)
    print("🤖 Step 3: Creating Agent with tools")
    print("=" * 60)
    
    client = OllamaClient()
    
    if not client.is_running():
        print("   ❌ Ollama is not running!")
        print("   Start with: ollama serve")
        return
    
    models = client.list_models()
    print(f"   Models: {len(models)} available")
    
    # Find best model
    model = None
    for m in models:
        if "qwen2.5-coder" in m:
            model = m
            break
    if not model:
        model = models[0] if models else None
    
    if not model:
        print("   ❌ No models available!")
        return
    
    print(f"   Using: {model}")
    
    tools = make_builtin_registry()
    tool_names = [t.name for t in tools.all()]
    print(f"   Tools: {tool_names[:5]}...")
    
    # Create agent with catalog (tier 1)
    agent = Agent(
        model=model,
        tools=tools,
        system_prompt="You create files using the write_file tool.",
        max_steps=5,
        client=client,
        model_options={"num_ctx": 512},
    )
    
    # ========================================
    # STEP 4: AGENT CREATES SKILL
    # ========================================
    print("\n" + "=" * 60)
    print("🔨 Step 4: Agent creates a skill file")
    print("   (Agent ACTUALLY uses write_file tool!)")
    print("=" * 60)
    
    skill_dir = os.path.join(skills_dir, "demo-skill")
    skill_path = os.path.join(skill_dir, "SKILL.md")
    
    # Clean up previous run
    if os.path.exists(skill_dir):
        shutil.rmtree(skill_dir)
    
    os.makedirs(skill_dir, exist_ok=True)
    
    # Simple content
    skill_content = """---
name: demo-skill
description: A demo skill created by an agent.
---

# Demo Skill

This skill was created by an AI agent using the write_file tool.
"""
    
    # Escape for prompt
    escaped = skill_content.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    
    # Short prompt
    prompt = f'write_file(path="{skill_path}", content="{escaped}")'
    
    print(f"   Target: {skill_path}")
    print("   Running agent...")
    
    start = time.time()
    try:
        result = agent.run(prompt)
        elapsed = time.time() - start
        
        print(f"\n   ⏱️ Completed in {elapsed:.1f}s")
        print(f"   Steps: {len(result.steps)}")
        
        for s in result.steps:
            if s.type == "tool_call":
                print(f"      TOOL: {s.tool_name}")
                if s.tool_name == "write_file":
                    p = s.tool_args.get("path", "?")
                    print(f"         path: {p}")
            elif s.type == "tool_result":
                content = str(s.content)[:60]
                print(f"         → {content}")
    except Exception as e:
        elapsed = time.time() - start
        print(f"   ⚠️ Error after {elapsed:.1f}s: {type(e).__name__}")
        print("   (Remote connection may have timed out)")
        print("\n   Creating skill directly for demo...")
        with open(skill_path, "w") as f:
            f.write(skill_content)
    
    # ========================================
    # STEP 5: VERIFY FILE
    # ========================================
    print("\n" + "=" * 60)
    print("📁 Step 5: Verifying file creation")
    print("=" * 60)
    
    if os.path.exists(skill_path):
        print("   ✅ FILE CREATED!")
        with open(skill_path) as f:
            content = f.read()
        print(f"   Size: {len(content)} chars")
        print("   Content preview:")
        for line in content.split("\n")[:8]:
            print(f"      {line}")
    else:
        print("   ❌ File not found")
        return
    
    # ========================================
    # STEP 6: LOAD NEW SKILL
    # ========================================
    print("\n" + "=" * 60)
    print("📚 Step 6: Loading the newly created skill")
    print("=" * 60)
    
    loader = SkillLoader()
    skills = loader.list_skills()
    print(f"   Available skills: {skills}")
    
    demo_skill = loader.load("demo-skill")
    print(f"   ✓ Loaded: {demo_skill.name}")
    print(f"   ✓ Description: {demo_skill.description}")
    
    # ========================================
    # STEP 7: TEST SKILL
    # ========================================
    print("\n" + "=" * 60)
    print("🧪 Step 7: Testing Agent with the new skill")
    print("=" * 60)
    
    test_registry = SkillRegistry()
    test_registry.add(demo_skill)
    
    test_agent = Agent(
        model=model,
        tools=None,
        system_prompt="You help with demos." + test_registry.to_system_prompt_addition(),
        max_steps=2,
        client=client,
        model_options={"num_ctx": 256},
    )
    
    question = "Tell me about the demo skill."
    print(f"   Question: {question}")
    
    try:
        response = test_agent.chat(question)
        print(f"\n   Response: {response[:200]}...")
    except Exception as e:
        print(f"   ⚠️ Error: {type(e).__name__}")
    
    # ========================================
    # SUMMARY
    # ========================================
    print("\n" + "=" * 60)
    print("✅ Skills demo complete!")
    print("=" * 60)
    print("""
💡 Summary:

   Progressive Disclosure (3 tiers):
   ─────────────────────────────────
   1. Catalog (name + description) - Always visible
   2. Instructions (SKILL.md body) - When activated
   3. Resources (scripts, refs) - When referenced

   Skills vs Tools:
   ────────────────
   Skills = Knowledge (markdown documents)
   Tools  = Execution (Python functions)

   skill-creator:
   ──────────────
   - Full skill from Anthropic's repository
   - Teaches how to create new skills
   - Includes scripts for evaluation
   - Includes references for schemas
    """)


if __name__ == "__main__":
    main()
