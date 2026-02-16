---
name: shell-execution
description: Execute shell commands safely, run scripts, manage processes, and perform system operations. Use when the user wants to run commands, execute scripts, or perform system administration tasks.
license: MIT
metadata:
  author: VTSBot
  version: "1.0"
  dangerous: "true"
allowed-tools: Bash
---

# Shell Execution Skill

This skill provides safe and controlled shell command execution capabilities.

## When to Use This Skill

- User explicitly asks to run a command
- User wants to execute a script
- User needs system administration tasks
- User wants to manage files or processes
- User asks for system information

## Safety First

**CRITICAL**: Always validate commands before execution.

### Blocked Commands

The following patterns are automatically blocked:

- `rm -rf /` or `rm -rf /*`
- Fork bombs: `:(){ :|:& };:`
- System destruction: `mkfs`, `dd if=`, `fdisk`
- Shutdown/reboot commands
- Writing to device files: `> /dev/sd*`

### Protected Paths

The following paths cannot be modified:

- `/`, `/bin`, `/sbin`, `/usr`, `/etc`, `/boot`
- `/lib`, `/lib64`, `/var`, `/sys`, `/proc`, `/dev`

## Capabilities

### Basic Commands

```bash
# List files
ls -la
ls -lah

# Current directory
pwd

# System information
uname -a
hostname
whoami
```

### File Operations

```bash
# Create directories
mkdir -p path/to/directory

# Copy files
cp source.txt destination.txt
cp -r source_dir/ destination_dir/

# Move/rename
mv old_name.txt new_name.txt

# Remove (with caution)
rm file.txt
rm -r directory/
rm -rf directory/  # Use with extreme caution
```

### Process Management

```bash
# List processes
ps aux
ps aux | grep process_name

# Find process
pgrep -f "pattern"

# Kill process (graceful)
kill PID

# Kill process (force)
kill -9 PID
```

### Text Processing

```bash
# Search in files
grep "pattern" file.txt
grep -r "pattern" directory/

# Stream processing
cat file.txt | head -20
cat file.txt | tail -20

# Text manipulation
sed 's/old/new/g' file.txt
awk '{print $1}' file.txt
```

## Step-by-Step Execution Process

### 1. Command Validation

Before executing any command:

```bash
# Check if command exists
which command_name

# Check command location
type command_name
```

### 2. Safety Check

Evaluate the command for:
- Dangerous patterns
- Protected path access
- Destructive operations
- Network operations

### 3. Execute with Timeout

```bash
# Standard execution (default 30s timeout)
command

# Long-running operations
timeout 60 long_running_command

# With output capture
command 2>&1
```

### 4. Result Handling

- Capture stdout and stderr
- Check exit code
- Handle timeouts gracefully
- Report results clearly

## Common Tasks

### Find Files

```bash
# Find by name
find . -name "*.py"

# Find by content
grep -rn "pattern" --include="*.py" .

# Find recent files
find . -mtime -1 -type f
```

### Disk Usage

```bash
# Directory size
du -sh directory/

# File sizes
du -h --max-depth=1

# Disk space
df -h
```

### Archive Operations

```bash
# Create tarball
tar -czvf archive.tar.gz directory/

# Extract tarball
tar -xzvf archive.tar.gz

# Create zip
zip -r archive.zip directory/

# Extract zip
unzip archive.zip
```

### Network Diagnostics

```bash
# Check connectivity
ping -c 3 hostname

# DNS lookup
nslookup hostname
dig hostname

# Port check
nc -zv hostname port
```

## Error Handling

### Command Not Found

```bash
if ! command -v tool &> /dev/null; then
  echo "Tool not installed"
fi
```

### Permission Denied

```bash
# Check permissions
ls -la file

# Add execute permission
chmod +x script.sh

# Check if directory is writable
[ -w directory ] && echo "writable" || echo "not writable"
```

### Timeout Handling

```bash
# Set explicit timeout
timeout 30 command
exit_code=$?

case $exit_code in
  124) echo "Command timed out" ;;
  0)   echo "Success" ;;
  *)   echo "Failed with code $exit_code" ;;
esac
```

## Best Practices

1. **Always validate input** before executing
2. **Use absolute paths** for important operations
3. **Check exit codes** for success/failure
4. **Capture stderr** for error messages
5. **Use timeouts** for potentially long operations
6. **Log operations** for debugging
7. **Test destructive operations** with echo first

## Output Format

When reporting command results:

```
## Command Execution

**Command:** `your-command-here`

**Status:** Success / Failed

**Output:**
```
[command output here]
```

**Exit Code:** 0

**Execution Time:** 0.5s
```
