import os
import re
import tempfile
from pathlib import Path
from typing import Optional

class PathSanitizer:
    """Utility class to handle path sanitization for Windows systems"""
    
    PROBLEMATIC_CHARS = {
        '&': '_and_',
        ' ': '_',
        '(': '',
        ')': '',
        '[': '',
        ']': '',
        '{': '',
        '}': '',
        '#': '_hash_',
        '%': '_percent_',
        '+': '_plus_',
        '=': '_equals_',
        '~': '_tilde_',
        '`': '_backtick_',
        '!': '_exclamation_',
        '@': '_at_',
        '$': '_dollar_',
        '^': '_caret_',
        ',': '_comma_',
        ';': '_semicolon_',
        "'": '_quote_',
        '"': '_dquote_'
    }
    
    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Sanitize a filename by replacing problematic characters
        
        Args:
            filename: Original filename with potential problematic characters
            
        Returns:
            Sanitized filename safe for Windows paths
        """
        if not filename:
            return filename
            
        name, ext = os.path.splitext(filename)
        
        sanitized_name = name
        for char, replacement in cls.PROBLEMATIC_CHARS.items():
            sanitized_name = sanitized_name.replace(char, replacement)
        
        sanitized_name = re.sub(r'_+', '_', sanitized_name)
        sanitized_name = sanitized_name.strip('_')
        
        if not sanitized_name:
            sanitized_name = 'sanitized_file'
            
        return f"{sanitized_name}{ext}"
    
    @classmethod
    def sanitize_path(cls, path: str) -> str:
        """
        Sanitize a full path by fixing directory and filename issues
        
        Args:
            path: Original path with potential issues
            
        Returns:
            Sanitized path safe for Windows
        """
        if not path:
            return path
            
        path_obj = Path(path)
        
        parts = []
        for part in path_obj.parts:
            if ':' in part and len(part) <= 3:
                parts.append(part)
            else:
                sanitized_part = part
                for char, replacement in cls.PROBLEMATIC_CHARS.items():
                    sanitized_part = sanitized_part.replace(char, replacement)
                
                sanitized_part = re.sub(r'_+', '_', sanitized_part)
                sanitized_part = sanitized_part.strip('_')
                
                if sanitized_part:
                    parts.append(sanitized_part)
        
        if parts:
            return str(Path(*parts))
        else:
            return tempfile.gettempdir()
    
    @classmethod
    def create_safe_copy(cls, original_path: str, target_dir: Optional[str] = None) -> str:
        """
        Create a safe copy of file with sanitized path
        
        Args:
            original_path: Path to original file
            target_dir: Target directory for safe copy (defaults to temp dir)
            
        Returns:
            Path to safe copy of the file
        """
        if not os.path.exists(original_path):
            raise FileNotFoundError(f"Original file not found: {original_path}")
        
        if target_dir is None:
            target_dir = tempfile.gettempdir()
        
        original_filename = os.path.basename(original_path)
        safe_filename = cls.sanitize_filename(original_filename)
        
        safe_path = os.path.join(target_dir, safe_filename)
        
        os.makedirs(target_dir, exist_ok=True)
        
        import shutil
        shutil.copy2(original_path, safe_path)
        
        return safe_path
    
    @classmethod
    def quote_path_for_powershell(cls, path: str) -> str:
        """
        Properly quote a path for PowerShell execution
        
        Args:
            path: Path to quote
            
        Returns:
            Properly quoted path for PowerShell
        """
        if not path:
            return path
        
        if "'" in path:
            escaped_path = path.replace('"', '""')
            return f'"{escaped_path}"'
        else:
            return f"'{path}'"
    
    @classmethod
    def get_safe_temp_path(cls, original_filename: str) -> str:
        """
        Generate a safe temporary path for a file
        
        Args:
            original_filename: Original filename
            
        Returns:
            Safe temporary path
        """
        safe_filename = cls.sanitize_filename(original_filename)
        return os.path.join(tempfile.gettempdir(), safe_filename)

def sanitize_filename(filename: str) -> str:
    """Sanitize a filename - convenience function"""
    return PathSanitizer.sanitize_filename(filename)

def sanitize_path(path: str) -> str:
    """Sanitize a path - convenience function"""
    return PathSanitizer.sanitize_path(path)

def create_safe_copy(original_path: str, target_dir: Optional[str] = None) -> str:
    """Create safe copy - convenience function"""
    return PathSanitizer.create_safe_copy(original_path, target_dir)

def quote_for_powershell(path: str) -> str:
    """Quote path for PowerShell - convenience function"""
    return PathSanitizer.quote_path_for_powershell(path)

if __name__ == "__main__":
    # Test code removed for production
    pass