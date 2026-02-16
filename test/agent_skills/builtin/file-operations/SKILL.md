---
name: file-operations
description: Read, write, create, delete, and manage files and directories. Use when the user needs to work with files, organize directories, or manipulate file contents.
license: MIT
metadata:
  author: VTSBot
  version: "1.0"
allowed-tools: Read Write Bash(cat:*) Bash(ls:*) Bash(mkdir:*) Bash(rm:*) Bash(mv:*) Bash(cp:*)
---

# File Operations Skill

This skill provides comprehensive file and directory management capabilities.

## When to Use This Skill

- User wants to read a file
- User wants to write or create a file
- User needs to organize or move files
- User wants to delete files or directories
- User asks about file contents or structure

## Capabilities

### Reading Files

Read file contents:

```bash
# Read entire file
cat file.txt

# Read with line numbers
cat -n file.txt

# Read first/last lines
head -20 file.txt
tail -20 file.txt

# Read specific lines
sed -n '10,20p' file.txt
```

### Writing Files

Create or modify files:

```bash
# Write content to file (overwrite)
cat > file.txt << 'EOF'
content here
EOF

# Append to file
cat >> file.txt << 'EOF'
additional content
EOF

# Create empty file
touch new_file.txt
```

### Directory Operations

Manage directories:

```bash
# Create directory
mkdir directory_name

# Create nested directories
mkdir -p path/to/nested/directory

# List directory contents
ls -la
ls -la directory/

# Remove empty directory
rmdir empty_directory

# Remove directory with contents
rm -rf directory/  # Use with caution
```

### File Management

Copy, move, and organize:

```bash
# Copy file
cp source.txt destination.txt

# Copy directory
cp -r source_dir/ destination_dir/

# Move/rename file
mv old_name.txt new_name.txt

# Move directory
mv old_dir/ new_dir/

# Delete file
rm file.txt

# Delete multiple files
rm file1.txt file2.txt
```

## Step-by-Step Process

### 1. Understand the Operation

Identify what the user wants:
- Read existing content?
- Create new file?
- Modify existing file?
- Organize files?
- Delete files?

### 2. Verify Paths

Before any operation:

```bash
# Check if file exists
[ -f file.txt ] && echo "exists" || echo "not found"

# Check if directory exists
[ -d directory ] && echo "exists" || echo "not found"

# Get absolute path
readlink -f relative_path
```

### 3. Execute Operation

Use appropriate commands based on the task.

### 4. Verify Results

```bash
# Check file was created
ls -la new_file.txt

# Check file content
cat new_file.txt | head -10

# Check permissions
stat file.txt
```

## Common Patterns

### Create File with Content

```bash
cat > filename.txt << 'EOF'
Line 1
Line 2
Line 3
EOF
```

### Read Configuration File

```bash
# Parse INI-style config
grep "^key" config.ini | cut -d'=' -f2

# Parse JSON config
cat config.json | jq '.key'

# Parse YAML config
grep "^key:" config.yaml | awk '{print $2}'
```

### Backup Before Modify

```bash
# Create backup
cp file.txt file.txt.bak

# Or with timestamp
cp file.txt "file.txt.$(date +%Y%m%d_%H%M%S).bak"
```

### Find and Organize

```bash
# Find all files of type
find . -name "*.txt" -exec mv {} text_files/ \;

# Find large files
find . -size +10M -exec ls -lh {} \;

# Find recently modified
find . -mtime -1 -type f
```

## File Content Operations

### Search in Files

```bash
# Basic search
grep "pattern" file.txt

# Case insensitive
grep -i "pattern" file.txt

# Show line numbers
grep -n "pattern" file.txt

# Recursive search
grep -rn "pattern" directory/
```

### Replace in Files

```bash
# Replace first occurrence per line
sed 's/old/new/' file.txt

# Replace all occurrences
sed 's/old/new/g' file.txt

# In-place replacement
sed -i 's/old/new/g' file.txt

# Replace in multiple files
sed -i 's/old/new/g' *.txt
```

### Extract Content

```bash
# Extract columns
awk '{print $1, $3}' file.txt

# Extract between patterns
sed -n '/START/,/END/p' file.txt

# Extract specific lines
awk 'NR>=10 && NR<=20' file.txt
```

## Error Handling

### File Not Found

```bash
if [ ! -f file.txt ]; then
  echo "Error: file.txt not found"
  exit 1
fi
```

### Permission Denied

```bash
if [ ! -r file.txt ]; then
  echo "Error: Cannot read file.txt"
fi

if [ ! -w directory ]; then
  echo "Error: Cannot write to directory"
fi
```

### Disk Full

```bash
# Check available space
df -h .

# Check directory size
du -sh .
```

## Best Practices

1. **Always check existence** before read
2. **Create backups** before destructive operations
3. **Use safe writes** (write to temp, then rename)
4. **Validate paths** to prevent traversal
5. **Handle encoding** appropriately
6. **Set proper permissions** for new files

## Output Format

When reporting file operations:

```
## File Operation Complete

**Operation:** Read / Write / Delete / Move
**Target:** /path/to/file
**Status:** Success / Failed

**Details:**
- Bytes processed: X
- Lines: Y
- Duration: Zs

**Preview:** (for reads, first few lines)
```

## Protected Operations

The following require extra caution:

- Overwriting existing files
- Deleting directories recursively
- Modifying system files
- Operations in `/etc`, `/usr`, `/var`
