import os
import subprocess
from pathlib import Path
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

CONVERSION_TIMEOUT = 90  # seconds
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

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
    
    # CKDEV-NOTE: Simplified LibreOffice command for Render deployment
    cmd = [
        'libreoffice',
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
        
        if result.returncode != 0:
            error_msg = f"LibreOffice conversion failed: {result.stderr}"
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

