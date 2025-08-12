import os
import platform
from pathlib import Path
from typing import Tuple, Optional
import logging
import subprocess

def is_linux() -> bool:
    """Check if running on Linux"""
    return platform.system().lower() == 'linux'

def convert_docx_to_pdf_linux(docx_path: str, pdf_path: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """
    Convert DOCX to PDF using Linux-compatible methods
    
    This function tries multiple Linux-compatible conversion methods in order:
    1. LibreOffice headless conversion (most reliable)
    2. Python-docx + ReportLab (fallback)
    
    Args:
        docx_path: Path to the .docx file
        pdf_path: Output path for PDF (optional)
    
    Returns:
        Tuple[bool, str, Optional[str]]: (success, message, pdf_path)
    """
    logger = logging.getLogger(__name__)
    
    if not os.path.exists(docx_path):
        return False, f"DOCX file not found: {docx_path}", None
    
    if pdf_path is None:
        pdf_path = str(Path(docx_path).with_suffix('.pdf'))
    
    output_dir = os.path.dirname(pdf_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # Method 1: Try LibreOffice headless conversion
    success, message, result_path = _try_libreoffice_conversion(docx_path, pdf_path, logger)
    if success and result_path:
        return success, message, result_path
    
    logger.warning(f"LibreOffice conversion failed: {message}")
    
    # Method 2: Try python-docx + ReportLab conversion
    success, message, result_path = _try_reportlab_conversion(docx_path, pdf_path, logger)
    if success and result_path:
        return success, message, result_path
    
    logger.error(f"All Linux conversion methods failed")
    return False, f"DOCX to PDF conversion failed on Linux. LibreOffice: {message}", None

def _try_libreoffice_conversion(docx_path: str, pdf_path: str, logger) -> Tuple[bool, str, Optional[str]]:
    """
    CKDEV-NOTE: Try LibreOffice headless conversion - most reliable Linux method
    """
    try:
        # Check if LibreOffice is available
        result = subprocess.run(['which', 'libreoffice'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return False, "LibreOffice not found in system PATH", None
        
        output_dir = os.path.dirname(pdf_path)
        
        # CKDEV-NOTE: LibreOffice headless conversion command
        cmd = [
            'libreoffice', 
            '--headless', 
            '--convert-to', 'pdf',
            '--outdir', output_dir,
            docx_path
        ]
        
        logger.info(f"Running LibreOffice conversion: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            # LibreOffice creates PDF with same name as DOCX
            expected_pdf = os.path.join(output_dir, 
                                      os.path.splitext(os.path.basename(docx_path))[0] + '.pdf')
            
            if os.path.exists(expected_pdf):
                # Move to desired location if different
                if expected_pdf != pdf_path:
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)
                    os.rename(expected_pdf, pdf_path)
                
                if os.path.getsize(pdf_path) > 0:
                    logger.info(f"LibreOffice PDF conversion successful: {pdf_path}")
                    return True, "PDF generated successfully with LibreOffice", pdf_path
                else:
                    return False, "LibreOffice generated empty PDF file", None
            else:
                return False, f"LibreOffice did not create expected PDF: {expected_pdf}", None
        else:
            error_msg = result.stderr or result.stdout or "Unknown LibreOffice error"
            return False, f"LibreOffice conversion failed: {error_msg}", None
            
    except subprocess.TimeoutExpired:
        return False, "LibreOffice conversion timed out", None
    except Exception as e:
        logger.error(f"LibreOffice conversion error: {e}")
        return False, f"LibreOffice conversion error: {str(e)}", None

def _try_reportlab_conversion(docx_path: str, pdf_path: str, logger) -> Tuple[bool, str, Optional[str]]:
    """
    CKDEV-NOTE: Fallback method using python-docx + ReportLab
    """
    try:
        from docx import Document
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        
        logger.info(f"Attempting ReportLab conversion for {docx_path}")
        
        # Load DOCX document
        doc = Document(docx_path)
        
        # Create PDF
        c = canvas.Canvas(pdf_path, pagesize=A4)
        width, height = A4
        
        # Start position
        y_position = height - inch
        line_height = 14
        margin = inch
        
        # CKDEV-NOTE: Extract text from DOCX and write to PDF
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if text:
                # Simple text wrapping
                words = text.split()
                line = ""
                
                for word in words:
                    test_line = line + (" " if line else "") + word
                    # Simple width check (approximate)
                    if len(test_line) > 80:  # Approximate character limit
                        if line:
                            c.drawString(margin, y_position, line)
                            y_position -= line_height
                            line = word
                        else:
                            c.drawString(margin, y_position, word)
                            y_position -= line_height
                    else:
                        line = test_line
                
                if line:
                    c.drawString(margin, y_position, line)
                    y_position -= line_height
                
                # Add extra space after paragraph
                y_position -= line_height / 2
                
                # Check if new page needed
                if y_position < inch:
                    c.showPage()
                    y_position = height - inch
        
        c.save()
        
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            logger.info(f"ReportLab PDF conversion successful: {pdf_path}")
            return True, "PDF generated successfully with ReportLab", pdf_path
        else:
            return False, "ReportLab generated empty or invalid PDF", None
            
    except ImportError as e:
        missing_lib = str(e).split()[-1] if 'reportlab' in str(e) else 'python-docx'
        return False, f"Missing library for ReportLab conversion: {missing_lib}", None
    except Exception as e:
        logger.error(f"ReportLab conversion error: {e}")
        return False, f"ReportLab conversion error: {str(e)}", None

def install_linux_requirements():
    """
    CKDEV-NOTE: Install required packages for Linux PDF conversion
    """
    requirements = [
        "python-docx",
        "reportlab"
    ]
    
    logger = logging.getLogger(__name__)
    
    for package in requirements:
        try:
            __import__(package.replace('-', '_'))
            logger.info(f"Package {package} is already installed")
        except ImportError:
            logger.warning(f"Package {package} not found - install with: pip install {package}")