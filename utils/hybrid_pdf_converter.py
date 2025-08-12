import os
import platform
from pathlib import Path
from typing import Tuple, Optional
import logging

# CKDEV-NOTE: Enhanced hybrid converter with formatting preservation
try:
    from .enhanced_docx_to_pdf import convert_docx_to_pdf_enhanced
except ImportError:
    try:
        from enhanced_docx_to_pdf import convert_docx_to_pdf_enhanced
    except ImportError:
        convert_docx_to_pdf_enhanced = None

try:
    from .libreoffice_converter import convert_docx_to_pdf_libreoffice
except ImportError:
    try:
        from libreoffice_converter import convert_docx_to_pdf_libreoffice
    except ImportError:
        convert_docx_to_pdf_libreoffice = None

try:
    from docx2pdf import convert as docx2pdf_convert
except ImportError:
    docx2pdf_convert = None


class HybridPDFConverter:
    """
    Enhanced hybrid PDF converter with formatting preservation priority.
    Ensures PDF generation works with proper layout in any environment.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._timeout = 60
    
    def convert_docx_to_pdf(
        self, 
        docx_path: str, 
        pdf_path: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Convert DOCX to PDF using enhanced hybrid approach prioritizing formatting preservation:
        1. Enhanced converter (best formatting preservation)
        2. LibreOffice (preferred for Linux/high fidelity) 
        3. docx2pdf (Windows/compatibility)
        4. Basic python-docx + reportlab (pure Python fallback)
        
        Args:
            docx_path: Path to the .docx file
            pdf_path: Output path for PDF (optional)
        
        Returns:
            Tuple[bool, str, Optional[str]]: (success, message, pdf_path)
        """
        if not os.path.exists(docx_path):
            return False, f"DOCX file not found: {docx_path}", None
        
        if pdf_path is None:
            pdf_path = str(Path(docx_path).with_suffix('.pdf'))
        
        # CKDEV-NOTE: Try enhanced converter first for best formatting preservation
        if convert_docx_to_pdf_enhanced:
            try:
                success, message, result_path = convert_docx_to_pdf_enhanced(docx_path, pdf_path)
                if success and result_path:
                    self.logger.info(f"Enhanced converter successful: {result_path}")
                    return success, f"Enhanced: {message}", result_path
                else:
                    self.logger.warning(f"Enhanced converter failed: {message}")
            except Exception as e:
                self.logger.warning(f"Enhanced converter error: {e}")
        
        # CKDEV-NOTE: Fall back to LibreOffice for high fidelity conversion
        if convert_docx_to_pdf_libreoffice:
            try:
                success, message, result_path = convert_docx_to_pdf_libreoffice(docx_path, pdf_path)
                if success and result_path:
                    self.logger.info(f"LibreOffice conversion successful: {result_path}")
                    return success, f"LibreOffice: {message}", result_path
                else:
                    self.logger.warning(f"LibreOffice conversion failed: {message}")
            except Exception as e:
                self.logger.warning(f"LibreOffice conversion error: {e}")
        
        # CKDEV-NOTE: Fall back to docx2pdf for Windows compatibility
        if docx2pdf_convert and platform.system().lower() == 'windows':
            try:
                success, message, result_path = self._convert_with_docx2pdf(docx_path, pdf_path)
                if success and result_path:
                    self.logger.info(f"docx2pdf fallback successful: {result_path}")
                    return success, f"docx2pdf: {message}", result_path
                else:
                    self.logger.warning(f"docx2pdf fallback failed: {message}")
            except Exception as e:
                self.logger.warning(f"docx2pdf fallback error: {e}")
        
        # CKDEV-NOTE: Last resort - basic Python conversion
        try:
            success, message, result_path = self._convert_with_python_libs(docx_path, pdf_path)
            if success and result_path:
                self.logger.info(f"Python library fallback successful: {result_path}")
                return success, f"Python libs: {message}", result_path
            else:
                self.logger.error(f"Python library fallback failed: {message}")
        except Exception as e:
            self.logger.error(f"Python library fallback error: {e}")
        
        return False, "All PDF conversion methods failed. Enhanced converter, LibreOffice, docx2pdf, and Python libraries all failed.", None
    
    def _convert_with_docx2pdf(self, docx_path: str, pdf_path: str) -> Tuple[bool, str, Optional[str]]:
        """Convert using docx2pdf (Windows primary method)"""
        if not docx2pdf_convert:
            return False, "docx2pdf library not available", None
        
        try:
            # CKDEV-NOTE: Clean up existing PDF first
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            
            # CKDEV-NOTE: Ensure output directory exists
            output_dir = os.path.dirname(pdf_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            # CKDEV-NOTE: Use absolute paths for docx2pdf
            docx_path_abs = os.path.abspath(docx_path)
            pdf_path_abs = os.path.abspath(pdf_path)
            
            self.logger.info(f"Converting with docx2pdf: {docx_path_abs} -> {pdf_path_abs}")
            
            # CKDEV-NOTE: Perform conversion with timeout protection
            import threading
            import time
            
            conversion_result = {'success': False, 'error': None}
            
            def convert_worker():
                try:
                    docx2pdf_convert(docx_path_abs, pdf_path_abs)
                    conversion_result['success'] = True
                except Exception as e:
                    conversion_result['error'] = e
            
            thread = threading.Thread(target=convert_worker)
            thread.daemon = True
            thread.start()
            thread.join(timeout=self._timeout)
            
            if thread.is_alive():
                return False, f"docx2pdf conversion timed out after {self._timeout} seconds", None
            
            if conversion_result.get('error'):
                raise conversion_result['error']
            
            # CKDEV-NOTE: Validate generated PDF
            if not os.path.exists(pdf_path_abs):
                return False, f"docx2pdf completed but no PDF file found at {pdf_path_abs}", None
            
            file_size = os.path.getsize(pdf_path_abs)
            if file_size == 0:
                os.remove(pdf_path_abs)
                return False, "docx2pdf generated empty PDF file", None
            
            if file_size < 100:
                os.remove(pdf_path_abs)
                return False, f"docx2pdf generated suspiciously small PDF ({file_size} bytes)", None
            
            # CKDEV-NOTE: Validate PDF header
            try:
                with open(pdf_path_abs, 'rb') as f:
                    header = f.read(4)
                    if not header.startswith(b'%PDF'):
                        os.remove(pdf_path_abs)
                        return False, "docx2pdf generated invalid PDF (bad header)", None
            except Exception:
                pass  # Header validation is optional
            
            return True, f"PDF generated successfully with docx2pdf ({file_size} bytes)", pdf_path_abs
            
        except Exception as e:
            self.logger.error(f"docx2pdf conversion error: {e}")
            return False, f"docx2pdf conversion error: {str(e)}", None
    
    def _convert_with_python_libs(self, docx_path: str, pdf_path: str) -> Tuple[bool, str, Optional[str]]:
        """Last resort conversion using pure Python libraries"""
        try:
            from docx import Document
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import inch
            
            self.logger.info(f"Attempting Python library conversion for {docx_path}")
            
            # CKDEV-NOTE: Load DOCX document
            doc = Document(docx_path)
            
            # CKDEV-NOTE: Create PDF with ReportLab
            c = canvas.Canvas(pdf_path, pagesize=A4)
            width, height = A4
            
            y_position = height - inch
            line_height = 14
            margin = inch
            
            # CKDEV-NOTE: Extract text from DOCX and write to PDF
            for paragraph in doc.paragraphs:
                text = paragraph.text.strip()
                if text:
                    # CKDEV-NOTE: Simple text wrapping
                    words = text.split()
                    line = ""
                    
                    for word in words:
                        test_line = line + (" " if line else "") + word
                        if len(test_line) > 80:  # Character limit per line
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
                    
                    y_position -= line_height / 2  # Paragraph spacing
                    
                    # CKDEV-NOTE: Check if new page needed
                    if y_position < inch:
                        c.showPage()
                        y_position = height - inch
            
            c.save()
            
            if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                file_size = os.path.getsize(pdf_path)
                return True, f"PDF generated with Python libraries ({file_size} bytes)", pdf_path
            else:
                return False, "Python libraries generated empty or invalid PDF", None
                
        except ImportError as e:
            missing_lib = str(e).split()[-1] if 'reportlab' in str(e) else 'python-docx'
            return False, f"Missing library for Python conversion: {missing_lib}", None
        except Exception as e:
            self.logger.error(f"Python library conversion error: {e}")
            return False, f"Python library conversion error: {str(e)}", None


def convert_docx_to_pdf_hybrid(
    docx_path: str, 
    pdf_path: Optional[str] = None
) -> Tuple[bool, str, Optional[str]]:
    """
    Convenience function for hybrid DOCX to PDF conversion.
    
    Args:
        docx_path: Path to the .docx file
        pdf_path: Output path for PDF (optional)
    
    Returns:
        Tuple[bool, str, Optional[str]]: (success, message, pdf_path)
    """
    converter = HybridPDFConverter()
    return converter.convert_docx_to_pdf(docx_path, pdf_path)