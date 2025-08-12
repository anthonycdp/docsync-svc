import os
import subprocess
from pathlib import Path
from typing import Tuple, Optional
import logging

class EnhancedPDFConverter:
    """
    DOCX to PDF converter using LibreOffice for best formatting preservation.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def convert_docx_to_pdf(self, docx_path: str, pdf_path: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """
        Convert DOCX to PDF using LibreOffice headless mode.
        
        Args:
            docx_path: Path to DOCX file
            pdf_path: Output PDF path (optional)
            
        Returns:
            Tuple[bool, str, Optional[str]]: (success, message, pdf_path)
        """
        if not os.path.exists(docx_path):
            return False, f"DOCX file not found: {docx_path}", None
        
        if pdf_path is None:
            pdf_path = str(Path(docx_path).with_suffix('.pdf'))
        
        # Ensure output directory exists
        output_dir = os.path.dirname(pdf_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        return self._convert_with_libreoffice(docx_path, pdf_path)
    
    def _convert_with_libreoffice(self, docx_path: str, pdf_path: str) -> Tuple[bool, str, Optional[str]]:
        """Convert using LibreOffice headless - best quality and formatting preservation."""
        
        # Check if LibreOffice is available
        libreoffice_cmd = None
        for cmd in ['libreoffice', 'soffice', '/usr/bin/libreoffice', '/opt/libreoffice/program/soffice']:
            try:
                result = subprocess.run([cmd, '--version'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    libreoffice_cmd = cmd
                    break
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        if not libreoffice_cmd:
            return False, "LibreOffice not found in system", None
        
        try:
            output_dir = os.path.dirname(pdf_path)
            
            # CKDEV-NOTE: LibreOffice headless conversion with optimized settings
            cmd = [
                libreoffice_cmd,
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', output_dir,
                '--writer',  # Force Writer mode for better DOCX handling
                docx_path
            ]
            
            self.logger.info(f"Running LibreOffice command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=60,
                                  cwd=output_dir)
            
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
                    
                    file_size = os.path.getsize(pdf_path)
                    if file_size > 1024:
                        return True, f"LibreOffice conversion successful ({file_size} bytes)", pdf_path
                    else:
                        return False, "LibreOffice generated empty PDF", None
                else:
                    return False, f"LibreOffice did not create expected PDF: {expected_pdf}", None
            else:
                error_msg = result.stderr or result.stdout or "Unknown LibreOffice error"
                return False, f"LibreOffice conversion failed: {error_msg}", None
                
        except subprocess.TimeoutExpired:
            return False, "LibreOffice conversion timed out", None
        except Exception as e:
            return False, f"LibreOffice conversion error: {str(e)}", None


def convert_docx_to_pdf_enhanced(docx_path: str, pdf_path: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """
    DOCX to PDF conversion function using LibreOffice.
    
    Args:
        docx_path: Path to DOCX file
        pdf_path: Output PDF path (optional)
        
    Returns:
        Tuple[bool, str, Optional[str]]: (success, message, pdf_path)
    """
    converter = EnhancedPDFConverter()
    return converter.convert_docx_to_pdf(docx_path, pdf_path)