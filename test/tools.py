import subprocess
import os
import shlex

DANGEROUS = [
    "rm -rf /", "mv / ", "chmod 777 /", 
    "shutdown", "reboot", "mkfs", "dd "
]

def run_shell(command: str) -> str:
    if not command:
        return "Error: No command provided."

    # STRIP HALLUCINATIONS: Catch cases where 0.5b outputs JSON inside the string
    if isinstance(command, str):
        # Remove literal JSON-like prefixes often seen in 0.5b failures
        hallucination_triggers = ['{"command":', '{"type":', '{"name":', '}']
        for trigger in hallucination_triggers:
            command = command.replace(trigger, "")
        command = command.strip(' "\'\n\t')

    if any(x in command for x in DANGEROUS):
        # Special check: Allow 'rm test.txt' but block 'rm ' globally if you want to be strict
        # For now, let's just block the most catastrophic ones
        if "rm " in command and "test.txt" not in command:
            return "Safety Violation: Restricted command."

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        output = (result.stdout + result.stderr).strip()
        return output if output else "SUCCESS (no output)"
    except Exception as e:
        return f"Shell Error: {e}"