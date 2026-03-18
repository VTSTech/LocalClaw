"""
examples/10_skills_demo_acp.py
----------------------------
Demonstrate the Agent Skills system with ACP integration.

Demonstrates:
- ACP activity tracking during skill creation
- Token tracking for skill operations
- Session notes for context recovery

Run: python examples/10_skills_demo_acp.py

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

import os
import sys
import time
import shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw.skills import SkillLoader, SkillRegistry
from localclaw import Agent, get_default_client, LOCALCLAW_BACKEND, StepResult
from localclaw.tools.builtins import make_builtin_registry
from localclaw.acp_plugin import ACPPlugin
from localclaw.model_discovery import pick_best_model, get_available_models

BACKEND_NAME = LOCALCLAW_BACKEND.upper()


def main():
    print("🦞 LocalClaw R03 - Skills Demo (ACP Enabled)")
    print("=" * 60)
    
    # ── Create and bootstrap ACP ─────────────────────────────────
    acp = ACPPlugin(
        agent_name="LocalClaw-SkillsDemo",
        model_name="skill-demo",
        debug=os.environ.get("ACP_DEBUG", "").lower() in ("1", "true"),
    )
    
    bootstrap = acp.bootstrap(claim_primary=False)
    acp_connected = bootstrap.get("status") is not None
    print(f"ACP: {'connected' if acp_connected else 'unavailable'}\n")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    skills_dir = os.path.join(base_dir, "localclaw", "skills")
    
    # ========================================
    # STEP 1: DISCOVER skills
    # ========================================
    print("\n📦 Step 1: Discovering skills...")
    acp.log_chat("system", "Step 1: Discovering skills", complete=True)
    
    loader = SkillLoader()
    skills = loader.list_skills()
    print(f"   Found {len(skills)} skill(s): {skills}")
    
    skill_creator = loader.load("skill-creator")
    print(f"   ✓ Loaded: {skill_creator.name}")
    print(f"   ✓ Description: {skill_creator.description[:60]}...")
    
    # ========================================
    # STEP 2: DISCLOSE catalog (tier 1)
    # ========================================
    print("\n" + "=" * 60)
    print("📋 Step 2: Building skill catalog (tier 1)")
    acp.log_chat("system", "Step 2: Building skill catalog", complete=True)
    
    registry = SkillRegistry()
    registry.add(skill_creator)
    
    catalog = registry.to_system_prompt_addition()
    print(f"   Catalog size: {len(catalog)} chars")
    
    # ========================================
    # STEP 3: CREATE AGENT with TOOLS
    # ========================================
    print("\n" + "=" * 60)
    print("🤖 Step 3: Creating Agent with tools")
    
    client = get_default_client()
    
    if not client.is_running():
        print(f"   ❌ {BACKEND_NAME} is not running!")
        if LOCALCLAW_BACKEND == "bitnet":
            print("   Start llama-server from bitnet.cpp directory")
        else:
            print("   Start with: ollama serve")
        return
    
    models = client.list_models()

    # Models known to NOT support tool calling (hallucinate instead of calling tools)
    # Note: SIZE is not the issue - Granite 350m and qwen 0.5b are excellent tool callers
    # This is model-specific, some architectures don't support Ollama's tool format
    NO_TOOL_SUPPORT = ["gemma3:270m"]  # Add others as discovered

    def supports_tools(m):
        """Check if model supports tool calling."""
        m_lower = m.lower()
        for bad in NO_TOOL_SUPPORT:
            if bad in m_lower:
                return False
        return True

    # Pick best model dynamically, preferring tool-supporting models
    model = pick_best_model(preferred=os.environ.get("LOCALCLAW_MODEL"), client=client)
    if not model:
        for m in models:
            if supports_tools(m):
                model = m
                break

    if not model:
        print("   ❌ No models available that support tool calling!")
        print(f"   💡 Models found: {', '.join(models) if models else 'none'}")
        print(f"   💡 Blocked (no tool support): {NO_TOOL_SUPPORT}")
        return

    print(f"   Using: {model}")
    acp.model_name = model  # Update model name
    
    tools = make_builtin_registry().subset(["write_file"])
    
    # Combined step callback
    def print_step(step: StepResult):
        acp.on_step(step)
        if step.type == "tool_call":
            print(f"      TOOL: {step.tool_name}")
            if step.tool_name == "write_file":
                p = step.tool_args.get("path", "?")
                print(f"         path: {p}")
        elif step.type == "tool_result":
            content = str(step.content)
            print(f"         → {content[:80]}...")
    
    skill_creator_brief = """
## Creating Skills

Skills are markdown files with YAML frontmatter:

---
name: skill-name
description: What the skill does and when to use it
---

# Skill Title

Instructions for using the skill.
"""
    
    agent = Agent(
        model=model,
        tools=tools,
        system_prompt="You create skill files using the write_file tool.\n\n" + skill_creator_brief,
        max_steps=5,
        client=client,
        on_step=print_step,
        model_options={
            "temperature": 0.0,
            "num_ctx": 2048,
            "num_predict": 1024,
        },
    )
    
    # ========================================
    # STEP 4: AGENT CREATES SKILL AUTONOMOUSLY
    # ========================================
    print("\n" + "=" * 60)
    print("🔨 Step 4: Agent creates a skill file AUTONOMOUSLY")
    
    skill_dir = os.path.join(skills_dir, "demo-skill")
    skill_path = os.path.join(skill_dir, "SKILL.md")
    
    if os.path.exists(skill_dir):
        shutil.rmtree(skill_dir)
    
    os.makedirs(skill_dir, exist_ok=True)
    
    prompt = f"""Create a skill named 'demo-skill' at: {skill_path}

The skill should help with basic text operations like:
- Counting words and characters
- Converting case (uppercase, lowercase)
- Finding and replacing text

Write a complete SKILL.md file with:
1. YAML frontmatter (name and description)
2. Markdown instructions

Use write_file to create the file."""
    
    print(f"   Target: {skill_path}")
    print("   Running agent...")
    
    # Log to ACP
    acp.log_user_message(f"Create demo-skill at {skill_path}")
    
    start = time.time()
    try:
        result = agent.run(prompt)
        elapsed = time.time() - start
        
        print(f"\n   ⏱️ Completed in {elapsed:.1f}s")
        print(f"   Steps: {len(result.steps)}")
        
        # Log to ACP
        acp.log_assistant_message(f"Skill created at {skill_path}")
    except Exception as e:
        elapsed = time.time() - start
        print(f"   ⚠️ Error after {elapsed:.1f}s: {type(e).__name__}")
        print(f"   Error: {e}")
        acp.log_assistant_message(f"[ERROR] {str(e)[:200]}")
    
    # ========================================
    # STEP 5: VERIFY FILE
    # ========================================
    print("\n" + "=" * 60)
    print("📁 Step 5: Verifying file creation")
    
    if os.path.exists(skill_path):
        print("   ✅ FILE CREATED!")
        with open(skill_path) as f:
            content = f.read()
        print(f"   Size: {len(content)} chars")
        print("   Content preview:")
        print("   " + "-" * 50)
        for line in content.split("\n")[:15]:
            print(f"   {line}")
        print("   ...")
        
        # Add note to ACP
        acp.add_note("decision", f"Created demo-skill: {len(content)} chars")
    else:
        print("   ❌ File not found")
        return
    
    # ========================================
    # STEP 6: LOAD NEW SKILL
    # ========================================
    print("\n" + "=" * 60)
    print("📚 Step 6: Loading the newly created skill")
    
    loader = SkillLoader()
    skills = loader.list_skills()
    print(f"   Available skills: {skills}")
    
    demo_skill = loader.load("demo-skill")
    if demo_skill:
        print(f"   ✓ Loaded: {demo_skill.name}")
        print(f"   ✓ Description: {demo_skill.description}")
    else:
        print("   ⚠️ Could not load demo-skill")
        return
    
    # ========================================
    # SUMMARY with ACP stats
    # ========================================
    print("\n" + "=" * 60)
    print("✅ Skills demo complete!")
    print("=" * 60)
    
    if acp_connected:
        status = acp.get_status()
        agent_tokens = acp.get_agent_tokens()
        print(f"\n📊 ACP Summary:")
        print(f"   Session tokens: {status.get('session_tokens', 0)}")
        print(f"   Agent tokens: {agent_tokens}")
    
    print("""
💡 Summary:

   What Happened:
   ──────────────
   - Agent received a request to create a skill
   - Agent autonomously generated the skill content
   - Agent used write_file tool to save it
   - All activities logged to ACP
   - Skill was loaded and verified successfully
    """)


if __name__ == "__main__":
    main()
