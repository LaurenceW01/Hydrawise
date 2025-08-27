#!/usr/bin/env python3
"""
Unicode Character Replacement Script
Replaces all Unicode emojis and symbols with ASCII-safe alternatives
for cloud-native deployment compatibility.
"""

import re
import os

# Define replacement mappings with comprehensive Unicode coverage
UNICODE_REPLACEMENTS = {
    # Time and scheduling
    '🌅': '[DAILY]',
    '🔄': '[PERIODIC]', 
    '🕐': '[TIME]',
    '📅': '[DATE]',
    '⏰': '[SCHEDULE]',
    
    # People and roles
    '👤': '[ADMIN]',
    
    # Data and results
    '📊': '[RESULTS]',
    '📋': '[LOG]',
    '🗄️': '[DATABASE]',
    '💾': '[SAVED]',
    '🆕': '[NEW]',
    
    # Status indicators - Success
    '✅': '[OK]',
    '✓': '[OK]',
    '🎉': '[SUCCESS]',
    '✨': '[COMPLETE]',
    
    # Status indicators - Warnings/Errors
    '❌': '[ERROR]',
    '⚠️': '[WARNING]',
    '🚨': '[ALERT]',
    
    # Actions and processes
    '🗑️': '[DELETE]',
    '🌐': '[WEB]',
    '🧪': '[TEST]',
    '💧': '[WATER]',
    '🔍': '[ANALYSIS]',
    '💡': '[INFO]',
    '⏹️': '[CANCELLED]',
    '🚰': '[HYDRAWISE]',
    
    # Navigation and UI
    '📂': '[FOLDER]',
    'ℹ️': '[INFO]',
    
    # Other symbols
    '•': '-',
    '→': '->',
}

def fix_unicode_in_file(filepath):
    """Fix Unicode characters in a single file"""
    print(f"Processing: {filepath}")
    
    try:
        # Read file content
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        changes_made = 0
        
        # First, apply specific replacements
        for unicode_char, replacement in UNICODE_REPLACEMENTS.items():
            if unicode_char in content:
                count = content.count(unicode_char)
                content = content.replace(unicode_char, replacement)
                changes_made += count
                print(f"  Replaced {count} instances of '{unicode_char}' with '{replacement}'")
        
        # Then, find any remaining non-ASCII characters
        remaining_unicode = []
        for i, char in enumerate(content):
            if ord(char) > 127:  # Non-ASCII character
                if char not in [c for c in UNICODE_REPLACEMENTS.keys()]:  # Not already handled
                    remaining_unicode.append((char, i))
        
        if remaining_unicode:
            print(f"  Found {len(remaining_unicode)} additional Unicode characters:")
            # Group by character
            char_counts = {}
            for char, pos in remaining_unicode:
                char_counts[char] = char_counts.get(char, 0) + 1
            
            for char, count in char_counts.items():
                print(f"    '{char}' (U+{ord(char):04X}): {count} times")
                # Apply generic replacement
                content = content.replace(char, '[SYMBOL]')
                changes_made += count
        
        # Write back if changes were made
        if changes_made > 0:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  Total changes: {changes_made}")
        else:
            print("  No Unicode characters found")
        
        return changes_made
            
    except Exception as e:
        print(f"  ERROR: {e}")
        return 0

def find_all_python_files():
    """Find all Python files in the project, excluding virtual environments and other non-project directories"""
    python_files = []
    
    # Directories to exclude (don't touch these!)
    exclude_dirs = {
        'venv', 'env', '.venv', '.env',           # Virtual environments
        'hydrawise-venv',                         # Your specific venv
        '__pycache__', '.git', '.pytest_cache',  # Cache/system directories
        'node_modules', '.vscode', '.idea',      # IDE/package directories
        'build', 'dist', '.eggs',                # Build directories
        'logs', 'docs', 'archive', 'data', 'reports',
    }
    
    # Directories to scan
    directories_to_scan = [
        '.',           # Root directory (filtered)
        'database',    # Database modules
        'utils',       # Utility modules  
        'config',      # Configuration modules
        'tests',       # Test files
    ]
    
    for directory in directories_to_scan:
        if os.path.exists(directory):
            print(f"Scanning directory: {directory}")
            for root, dirs, files in os.walk(directory):
                # Remove excluded directories from the walk
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                
                # Skip if we're in an excluded directory
                path_parts = root.split(os.sep)
                if any(part in exclude_dirs for part in path_parts):
                    continue
                
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        python_files.append(file_path)
                        print(f"  Found: {file_path}")
        else:
            print(f"Directory not found: {directory}")
    
    return python_files

def main():
    """Main function to process files"""
    print("Cloud-Native Unicode Replacement Script")
    print("=" * 50)
    print("Scanning for all Python files in the project...")
    print()
    
    # Find all Python files
    files_to_process = find_all_python_files()
    
    if not files_to_process:
        print("No Python files found!")
        return
    
    print(f"\nFound {len(files_to_process)} Python files to process")
    print("=" * 50)
    
    total_changes = 0
    files_changed = 0
    
    for filepath in files_to_process:
        if os.path.exists(filepath):
            changes = fix_unicode_in_file(filepath)
            total_changes += changes
            if changes > 0:
                files_changed += 1
        else:
            print(f"File not found: {filepath}")
        print()
    
    print("=" * 50)
    print(f"Unicode replacement completed!")
    print(f"Files processed: {len(files_to_process)}")
    print(f"Files changed: {files_changed}")
    print(f"Total changes: {total_changes}")
    
    if total_changes > 0:
        print(f"\n[SUCCESS] Successfully made codebase cloud-native!")
        print(f"[SUCCESS] All Unicode characters replaced with ASCII-safe alternatives")
    else:
        print(f"\n[SUCCESS] Codebase is already cloud-native (no Unicode characters found)")

if __name__ == "__main__":
    main()
's '