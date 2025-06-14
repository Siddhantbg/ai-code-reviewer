import re
import hashlib
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime


def generate_unique_id(prefix: str = "") -> str:
    """Generate a unique identifier with optional prefix."""
    unique_id = uuid.uuid4().hex[:12]
    return f"{prefix}_{unique_id}" if prefix else unique_id


def calculate_code_hash(code: str) -> str:
    """Calculate SHA-256 hash of code content."""
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing potentially dangerous characters."""
    if not filename:
        return ""
    
    # Remove path separators and dangerous characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    
    # Limit length
    if len(sanitized) > 255:
        name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
        max_name_length = 255 - len(ext) - 1 if ext else 255
        sanitized = f"{name[:max_name_length]}.{ext}" if ext else name[:255]
    
    return sanitized or "untitled"


def detect_language_from_code(code: str, filename: Optional[str] = None) -> Optional[str]:
    """Attempt to detect programming language from code content and filename."""
    
    # First try to detect from filename extension
    if filename:
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        extension_map = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'tsx': 'typescript',
            'jsx': 'javascript',
            'java': 'java',
            'cpp': 'cpp',
            'cxx': 'cpp',
            'cc': 'cpp',
            'c': 'c',
            'h': 'c',
            'hpp': 'cpp',
            'go': 'go',
            'rs': 'rust',
            'php': 'php',
            'rb': 'ruby'
        }
        if ext in extension_map:
            return extension_map[ext]
    
    # Try to detect from code patterns
    code_lower = code.lower()
    
    # Python patterns
    if any(pattern in code for pattern in ['def ', 'import ', 'from ', 'print(', '__name__']):
        return 'python'
    
    # JavaScript/TypeScript patterns
    if any(pattern in code for pattern in ['function ', 'const ', 'let ', 'var ', 'console.log']):
        if 'interface ' in code or ': string' in code or ': number' in code:
            return 'typescript'
        return 'javascript'
    
    # Java patterns
    if any(pattern in code for pattern in ['public class', 'private ', 'public static void main']):
        return 'java'
    
    # C/C++ patterns
    if any(pattern in code for pattern in ['#include', 'int main(', 'printf(', 'cout <<']):
        if any(pattern in code for pattern in ['std::', 'class ', 'namespace ']):
            return 'cpp'
        return 'c'
    
    return None


def count_lines_of_code(code: str, exclude_empty: bool = True, exclude_comments: bool = False) -> int:
    """Count lines of code with various filtering options."""
    lines = code.split('\n')
    
    if not exclude_empty and not exclude_comments:
        return len(lines)
    
    count = 0
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines if requested
        if exclude_empty and not stripped:
            continue
        
        # Skip comment lines if requested (basic detection)
        if exclude_comments:
            if (stripped.startswith('#') or  # Python, shell
                stripped.startswith('//') or  # C++, Java, JavaScript
                stripped.startswith('/*') or  # C++, Java, JavaScript
                stripped.startswith('*') or   # Multi-line comments
                stripped.startswith('"""') or  # Python docstrings
                stripped.startswith("'''")):
                continue
        
        count += 1
    
    return count


def extract_functions(code: str, language: str) -> List[Dict[str, Any]]:
    """Extract function definitions from code."""
    functions = []
    lines = code.split('\n')
    
    if language == 'python':
        pattern = r'^\s*def\s+(\w+)\s*\('
    elif language in ['javascript', 'typescript']:
        pattern = r'^\s*(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:function|\())'
    elif language == 'java':
        pattern = r'^\s*(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\('
    elif language in ['c', 'cpp']:
        pattern = r'^\s*(?:\w+\s+)*?(\w+)\s*\([^)]*\)\s*\{?\s*$'
    else:
        return functions
    
    for line_num, line in enumerate(lines, 1):
        match = re.search(pattern, line)
        if match:
            function_name = match.group(1)
            functions.append({
                'name': function_name,
                'line_number': line_num,
                'code': line.strip()
            })
    
    return functions


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def validate_code_input(code: str, max_size: int = 50000) -> Dict[str, Any]:
    """Validate code input and return validation results."""
    result = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'info': {}
    }
    
    # Check if code is empty
    if not code or not code.strip():
        result['valid'] = False
        result['errors'].append("Code cannot be empty")
        return result
    
    # Check code size
    code_size = len(code.encode('utf-8'))
    if code_size > max_size:
        result['valid'] = False
        result['errors'].append(f"Code size ({format_file_size(code_size)}) exceeds maximum allowed size ({format_file_size(max_size)})")
    
    # Check for potentially malicious content
    suspicious_patterns = [
        r'rm\s+-rf',  # Dangerous shell commands
        r'del\s+/[sf]',  # Windows delete commands
        r'format\s+c:',  # Format commands
        r'__import__\s*\(\s*["\']os["\']\s*\)',  # Dynamic imports
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, code, re.IGNORECASE):
            result['warnings'].append(f"Potentially suspicious pattern detected: {pattern}")
    
    # Add info
    result['info'] = {
        'size_bytes': code_size,
        'size_formatted': format_file_size(code_size),
        'line_count': len(code.split('\n')),
        'character_count': len(code)
    }
    
    return result


def get_current_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.utcnow().isoformat() + 'Z'


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to specified length with suffix."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix