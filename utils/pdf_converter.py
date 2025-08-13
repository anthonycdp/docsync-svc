import os
import subprocess
import platform
from pathlib import Path
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

CONVERSION_TIMEOUT = 90  # seconds
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

def get_libreoffice_command() -> Optional[str]:
    """
    Auto-detect LibreOffice executable path based on operating system.
    
    Returns:
        str: Path to LibreOffice executable or None if not found
    """
    system = platform.system().lower()
    
    if system == "windows":
        # CKDEV-NOTE: Windows-specific LibreOffice detection with common paths
        possible_paths = [
            "soffice.exe",  # If in PATH
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            r"C:\Program Files\LibreOffice 7.6\program\soffice.exe",
            r"C:\Program Files\LibreOffice 7.5\program\soffice.exe",
            r"C:\Program Files\LibreOffice 7.4\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice 7.6\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice 7.5\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice 7.4\program\soffice.exe"
        ]
        
        for path in possible_paths:
            try:
                if path == "soffice.exe":
                    # Test if in PATH
                    result = subprocess.run(
                        ["where", "soffice.exe"], 
                        capture_output=True, 
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        return "soffice.exe"
                else:
                    if os.path.exists(path):
                        return path
            except Exception:
                continue
                
    elif system in ["linux", "darwin"]:
        # CKDEV-NOTE: Unix-like systems typically use 'libreoffice' command
        try:
            result = subprocess.run(
                ["which", "libreoffice"], 
                capture_output=True, 
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return "libreoffice"
        except Exception:
            pass
            
        # Fallback paths for Unix systems
        possible_paths = [
            "/usr/bin/libreoffice",
            "/usr/local/bin/libreoffice",
            "/opt/libreoffice/program/soffice"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
    
    return None

def convert_docx_to_pdf(
    docx_path: str, 
    pdf_path: Optional[str] = None
) -> Tuple[bool, str, Optional[str]]:
    """
    Convert DOCX to PDF using LibreOffice headless mode.
    
    Args:
        docx_path: Path to the .docx file
        pdf_path: Output path for PDF (optional)
    
    Returns:
        Tuple[bool, str, Optional[str]]: (success, message, pdf_path)
    """
    if not os.path.exists(docx_path):
        return False, f"DOCX file not found: {docx_path}", None
    
    file_size = os.path.getsize(docx_path)
    if file_size > MAX_FILE_SIZE:
        return False, f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE})", None
    
    if pdf_path is None:
        pdf_path = str(Path(docx_path).with_suffix('.pdf'))
    
    output_dir = str(Path(pdf_path).parent)
    input_path = Path(docx_path)
    
    # CKDEV-NOTE: Auto-detect LibreOffice executable for cross-platform support
    libreoffice_cmd = get_libreoffice_command()
    
    if not libreoffice_cmd:
        return False, "LibreOffice not found. Please install LibreOffice.", None
    
    cmd = [
        libreoffice_cmd,
        '--headless',
        '--nologo',
        '--nodefault',
        '--nofirststartwizard',
        '--convert-to', 'pdf',
        '--outdir', output_dir,
        str(input_path)
    ]
    
    try:
        logger.info(f"Executing conversion: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=CONVERSION_TIMEOUT
        )
        
        logger.info(f"LibreOffice stdout: {result.stdout}")
        logger.info(f"LibreOffice stderr: {result.stderr}")
        logger.info(f"LibreOffice return code: {result.returncode}")
        
        if result.returncode != 0:
            error_msg = f"LibreOffice conversion failed (code {result.returncode}): {result.stderr}"
            logger.error(error_msg)
            return False, error_msg, None
        
        if os.path.exists(pdf_path):
            file_size = os.path.getsize(pdf_path)
            logger.info(f"PDF generated successfully: {pdf_path} ({file_size} bytes)")
            return True, f"Conversion successful ({file_size} bytes)", pdf_path
        else:
            return False, f"PDF not generated at expected path: {pdf_path}", None
            
    except subprocess.TimeoutExpired:
        logger.error("Conversion timeout")
        return False, "Conversion timeout", None
    except Exception as e:
        error_msg = f"Conversion error: {str(e)}"
        logger.error(error_msg)
        return False, error_msg, None

