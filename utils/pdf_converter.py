import os
import subprocess
import tempfile
import shutil
import platform
from pathlib import Path
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

CONVERSION_TIMEOUT = 90  # seconds
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

def find_libreoffice_binary() -> Optional[str]:
    """Find LibreOffice/soffice binary on the system"""
    system = platform.system().lower()
    
    if system == 'windows':
        possible_paths = [
            'C:\\Program Files\\LibreOffice\\program\\soffice.exe',
            'C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe',
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
    else:
        # CKDEV-NOTE: Try common Linux/Mac binary names
        for cmd in ['libreoffice', 'soffice']:
            if shutil.which(cmd):
                return cmd
    
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
    
    # CKDEV-NOTE: Find LibreOffice binary
    soffice_path = find_libreoffice_binary()
    if not soffice_path:
        logger.warning("LibreOffice not found, trying docx2pdf fallback")
        return _convert_with_docx2pdf_fallback(docx_path, pdf_path)
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_docx_path = os.path.join(temp_dir, Path(docx_path).name)
            shutil.copy2(docx_path, temp_docx_path)
            
            cmd = [
                soffice_path,
                '--headless',
                '--nologo',
                '--nodefault',
                '--nofirststartwizard',
                '--convert-to', 'pdf',
                '--outdir', temp_dir,
                temp_docx_path
            ]
            
            logger.info(f"Executing conversion: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=CONVERSION_TIMEOUT
            )
            
            if result.returncode != 0:
                logger.error(f"LibreOffice failed: {result.stderr}")
                return _convert_with_docx2pdf_fallback(docx_path, pdf_path)
            
            temp_pdf_path = os.path.join(temp_dir, Path(docx_path).stem + '.pdf')
            
            if not os.path.exists(temp_pdf_path):
                return _convert_with_docx2pdf_fallback(docx_path, pdf_path)
            
            shutil.move(temp_pdf_path, pdf_path)
            
            if os.path.exists(pdf_path):
                file_size = os.path.getsize(pdf_path)
                logger.info(f"PDF generated successfully: {pdf_path} ({file_size} bytes)")
                return True, f"Conversion successful ({file_size} bytes)", pdf_path
            
    except subprocess.TimeoutExpired:
        logger.error("Conversion timeout")
        return False, "Conversion timeout", None
    except Exception as e:
        logger.error(f"Conversion error: {str(e)}")
        return _convert_with_docx2pdf_fallback(docx_path, pdf_path)
    
    return False, "Conversion failed", None

def _convert_with_docx2pdf_fallback(
    docx_path: str, 
    pdf_path: str
) -> Tuple[bool, str, Optional[str]]:
    """Fallback to docx2pdf for Windows systems"""
    if platform.system().lower() != 'windows':
        return False, "LibreOffice not available and docx2pdf only works on Windows", None
    
    try:
        from docx2pdf import convert as docx2pdf_convert
        
        logger.info("Using docx2pdf fallback for Windows")
        
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        
        docx2pdf_convert(docx_path, pdf_path)
        
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            file_size = os.path.getsize(pdf_path)
            return True, f"docx2pdf conversion successful ({file_size} bytes)", pdf_path
        
        return False, "docx2pdf generated empty PDF", None
        
    except ImportError:
        logger.error("docx2pdf not installed")
        return False, "Neither LibreOffice nor docx2pdf available", None
    except Exception as e:
        logger.error(f"docx2pdf error: {str(e)}")
        return False, f"docx2pdf conversion failed: {str(e)}", None