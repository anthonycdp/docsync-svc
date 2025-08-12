import os
import sys
import platform
from pathlib import Path
from typing import Tuple, Optional

try:
    from docx2pdf import convert
except ImportError:
    convert = None

try:
    from ..utils.logging_config import LoggerMixin
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from utils.logging_config import LoggerMixin

# CKDEV-NOTE: Import both LibreOffice converters for cross-platform support
try:
    from .simple_pdf_converter import convert_with_libreoffice, is_linux
except ImportError:
    try:
        from simple_pdf_converter import convert_with_libreoffice, is_linux
    except ImportError:
        convert_with_libreoffice = None
        is_linux = lambda: False

try:
    from .linux_pdf_converter import convert_docx_to_pdf_linux
except ImportError:
    try:
        from linux_pdf_converter import convert_docx_to_pdf_linux
    except ImportError:
        convert_docx_to_pdf_linux = None


class PDFConverter(LoggerMixin):
    """Conversor de DOCX para PDF com tratamento robusto de erros"""
    
    def __init__(self):
        super().__init__()
        self._validate_dependencies()
    
    def _validate_dependencies(self):
        # CKDEV-NOTE: Check for appropriate converter based on OS and available libraries
        if is_linux():
            if convert_with_libreoffice is None and convert_docx_to_pdf_linux is None:
                raise ImportError("No PDF converter available for Linux. Install LibreOffice or required libraries: pip install python-docx reportlab")
        else:
            if convert is None and convert_docx_to_pdf_linux is None:
                raise ImportError("No PDF converter available for Windows. Install: pip install docx2pdf")
    
    def convert_to_pdf(self, docx_path: str, pdf_path: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """
        Converter arquivo DOCX para PDF
        
        Args:
            docx_path: Caminho para o arquivo .docx
            pdf_path: Caminho de saída para o PDF (opcional)
        
        Returns:
            Tuple[bool, str, Optional[str]]: (sucesso, mensagem, caminho_do_pdf)
        """
        try:
            if not os.path.exists(docx_path):
                return False, f"Arquivo DOCX não encontrado: {docx_path}", None
            
            if not docx_path.lower().endswith('.docx'):
                return False, f"Arquivo deve ter extensão .docx: {docx_path}", None
            
            if pdf_path is None:
                pdf_path = self._generate_pdf_path(docx_path)
            
            output_dir = os.path.dirname(pdf_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            self.logger.info(f"Converting {docx_path} to {pdf_path}")
            
            # CKDEV-NOTE: Enhanced Windows-focused conversion with proper error handling
            if platform.system().lower() == 'windows' and convert is not None:
                self.logger.info("Using docx2pdf for Windows PDF conversion")
                return self._convert_docx2pdf_windows(docx_path, pdf_path)
            elif convert_with_libreoffice:
                self.logger.info("Using LibreOffice for PDF conversion")
                return convert_with_libreoffice(docx_path, pdf_path)
            elif convert is not None:
                self.logger.info("Using docx2pdf as fallback")
                return self._convert_docx2pdf_windows(docx_path, pdf_path)
            else:
                return False, "Nenhum método de conversão PDF disponível. Instale docx2pdf ou LibreOffice.", None
        
        except Exception as e:
            error_msg = f"Erro na conversão para PDF: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg, None
    
    def _convert_docx2pdf_windows(self, docx_path: str, pdf_path: str) -> Tuple[bool, str, Optional[str]]:
        """Enhanced docx2pdf conversion for Windows with comprehensive error handling"""
        if convert is None:
            return False, "docx2pdf library not available", None
            
        try:
            # CKDEV-NOTE: Ensure paths are absolute and normalized
            docx_path_abs = os.path.abspath(docx_path)
            pdf_path_abs = os.path.abspath(pdf_path)
            
            self.logger.info(f"Converting: {docx_path_abs} -> {pdf_path_abs}")
            
            # CKDEV-NOTE: Clean up any existing PDF file first
            if os.path.exists(pdf_path_abs):
                try:
                    os.remove(pdf_path_abs)
                    self.logger.info(f"Removed existing PDF: {pdf_path_abs}")
                except OSError as cleanup_error:
                    self.logger.warning(f"Could not remove existing PDF: {cleanup_error}")
            
            # CKDEV-NOTE: Try docx2pdf conversion with timeout protection
            import threading
            import time
            
            conversion_result = {'success': False, 'error': None}
            
            def convert_worker():
                try:
                    convert(docx_path_abs, pdf_path_abs)
                    conversion_result['success'] = True
                except Exception as e:
                    conversion_result['error'] = e
            
            # CKDEV-NOTE: Run conversion in thread with timeout
            thread = threading.Thread(target=convert_worker)
            thread.daemon = True
            thread.start()
            thread.join(timeout=60)  # 60 second timeout
            
            if thread.is_alive():
                self.logger.error("docx2pdf conversion timed out after 60 seconds")
                return False, "docx2pdf conversion timed out", None
            
            if conversion_result.get('error'):
                raise conversion_result['error']
            
            # CKDEV-NOTE: Comprehensive validation of generated PDF
            if not os.path.exists(pdf_path_abs):
                return False, f"docx2pdf completed but no PDF file found at {pdf_path_abs}", None
            
            file_size = os.path.getsize(pdf_path_abs)
            if file_size == 0:
                os.remove(pdf_path_abs)
                return False, "docx2pdf generated empty PDF file", None
            
            if file_size < 100:  # PDFs should be at least 100 bytes
                os.remove(pdf_path_abs)
                return False, f"docx2pdf generated suspiciously small PDF ({file_size} bytes)", None
            
            # CKDEV-NOTE: Validate PDF header
            try:
                with open(pdf_path_abs, 'rb') as f:
                    header = f.read(4)
                    if not header.startswith(b'%PDF'):
                        os.remove(pdf_path_abs)
                        return False, "docx2pdf generated invalid PDF (bad header)", None
            except Exception as header_error:
                self.logger.warning(f"Could not validate PDF header: {header_error}")
            
            self.logger.info(f"docx2pdf conversion successful: {pdf_path_abs} ({file_size} bytes)")
            return True, f"PDF gerado com sucesso ({file_size} bytes)", pdf_path_abs
                
        except Exception as e:
            error_str = str(e).lower()
            
            # CKDEV-NOTE: Handle specific Windows/Office errors
            if any(keyword in error_str for keyword in ['word', 'office', 'com', 'ole']):
                return False, "Microsoft Word/Office não está disponível ou não está funcionando corretamente", None
            elif any(keyword in error_str for keyword in ['permission', 'access', 'denied']):
                return False, f"Erro de permissão: {e}", None
            elif 'timeout' in error_str:
                return False, f"Conversão demorou muito para completar: {e}", None
            else:
                self.logger.error(f"docx2pdf unexpected error: {e}")
                return False, f"Erro na conversão docx2pdf: {e}", None
    

    def _generate_pdf_path(self, docx_path: str) -> str:
        docx_file = Path(docx_path)
        pdf_path = docx_file.with_suffix('.pdf')
        return str(pdf_path)
    
    @staticmethod
    def is_conversion_available() -> bool:
        return convert is not None or convert_docx_to_pdf_linux is not None or convert_with_libreoffice is not None


def convert_docx_to_pdf(docx_path: str, pdf_path: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """
    Função conveniente para conversão DOCX -> PDF
    
    Args:
        docx_path: Caminho para o arquivo .docx
        pdf_path: Caminho de saída para o PDF (opcional)
    
    Returns:
        Tuple[bool, str, Optional[str]]: (sucesso, mensagem, caminho_do_pdf)
    """
    converter = PDFConverter()
    return converter.convert_to_pdf(docx_path, pdf_path)