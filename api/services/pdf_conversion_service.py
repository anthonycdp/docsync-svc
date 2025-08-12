from pathlib import Path
from typing import Optional, Tuple

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.enhanced_pdf_converter import convert_docx_to_pdf_enhanced
from utils.pdf_converter import convert_docx_to_pdf as simple_convert_docx_to_pdf
from ..exceptions import PDFConversionError
from ..utils.logger import get_service_logger


class PDFConversionService:
    """
    CKDEV-NOTE: Wrapper simples que usa apenas o metodo que funciona corretamente
    Removida toda a logica complicada que estava causando problemas na formatacao
    """
    
    def __init__(self, config=None):
        self.logger = get_service_logger('pdf_conversion')
    
    def convert_docx_to_pdf(
        self, 
        docx_path: Path, 
        pdf_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        CKDEV-NOTE: Enhanced conversion with better formatting preservation
        Uses multiple methods prioritizing LibreOffice for best results
        """
        try:
            # Try enhanced converter first (LibreOffice, mammoth, etc.)
            success, message, result_path = convert_docx_to_pdf_enhanced(
                str(docx_path), 
                str(pdf_path) if pdf_path else None
            )
            
            if success and result_path:
                self.logger.info(f"PDF generated successfully with enhanced converter: {result_path}")
                return Path(result_path)
            else:
                self.logger.warning(f"Enhanced PDF converter failed: {message}")
                
                # Fallback to simple converter
                self.logger.info("Falling back to simple PDF converter...")
                success_simple, message_simple, result_path_simple = simple_convert_docx_to_pdf(
                    str(docx_path), 
                    str(pdf_path) if pdf_path else None
                )
                
                if success_simple and result_path_simple:
                    self.logger.info(f"PDF generated with fallback converter: {result_path_simple}")
                    return Path(result_path_simple)
                else:
                    self.logger.error(f"All PDF conversion methods failed. Enhanced: {message}, Simple: {message_simple}")
                    raise PDFConversionError(f"Failed to convert {docx_path.name} to PDF: Enhanced converter: {message}, Simple converter: {message_simple}")
                
        except Exception as e:
            self.logger.error(f"PDF conversion error: {e}")
            raise PDFConversionError(f"Failed to convert {docx_path.name} to PDF: {str(e)}")