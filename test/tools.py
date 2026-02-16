import subprocess
import os
import re

DANGEROUS = [
    "rm -rf /", "rm -rf /*", "mv / ", "chmod 777 /", 
    "shutdown", "reboot", "halt", "poweroff",
    "mkfs", "dd if=", "mkfs.", "fdisk",
    "> /dev/sd", "> /dev/hd", "> /dev/nvme",
    ":(){ :|:& };:",  # Fork bomb
]

# Directories to protect
PROTECTED_PATHS = [
    "/", "/bin", "/sbin", "/usr", "/etc", "/boot",
    "/lib", "/lib64", "/var", "/sys", "/proc", "/dev"
]

def is_dangerous_command(command: str) -> bool:
    """Enhanced safety check"""
    cmd_lower = command.lower().strip()
    
    # Check against dangerous patterns
    for pattern in DANGEROUS:
        if pattern in cmd_lower:
            return True
    
    # Check for path traversal
    if ".." in cmd_lower and any(protected in cmd_lower for protected in ["rm", "mv", "cp", "chmod", "chown"]):
        return True
    
    # Check for protected paths
    if any(cmd_lower.startswith(f"rm {path}") or f"rm {path}/" in cmd_lower for path in PROTECTED_PATHS):
        return True
    
    # Check for redirect to system devices
    if re.search(r'>\s*/dev/(sd[a-z]|hd[a-z]|nvme[0-9])', cmd_lower):
        return True
    
    return False

def run_shell(command: str) -> str:
    if not command:
        return "Error: No command provided."

    # Clean the command
    command = str(command).strip()
    
    # Remove markdown and JSON artifacts
    command = re.sub(r'```[a-z]*\s*', '', command)
    command = re.sub(r'\s*```\s*', '', command)
    command = re.sub(r'^\s*{\s*".*', '', command)  # Remove JSON start
    command = command.strip(' "\'\n\t')

    # Safety check
    if is_dangerous_command(command):
        return "Safety Violation: Command blocked by security policy."
    
    try:
        # Timeout based on command complexity
        timeout = 30 if any(x in command for x in ['find', 'grep -r', 'rsync']) else 10
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, 'LANG': 'C.UTF-8'}
        )
        
        # Combine output, stderr first if present
        if result.stderr:
            output = f"[stderr] {result.stderr.strip()}"
            if result.stdout:
                output += f"\n[stdout] {result.stdout.strip()}"
        else:
            output = result.stdout.strip() if result.stdout else ""
        
        return output if output else "SUCCESS (no output)"
        
    except subprocess.TimeoutExpired:
        return "Error: Command timed out."
    except subprocess.CalledProcessError as e:
        return f"Command failed with exit code {e.returncode}: {e.stderr or e.stdout}"
    except Exception as e:
        return f"Execution Error: {str(e)}"