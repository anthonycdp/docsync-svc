from pathlib import Path
from typing import Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.enhanced_pdf_converter import convert_docx_to_pdf_enhanced
from ..exceptions import PDFConversionError
from ..utils.logger import get_service_logger


class PDFConversionService:
    """
    CKDEV-NOTE: Simple PDF conversion service using LibreOffice only
    """
    
    def __init__(self, config=None):
        self.logger = get_service_logger('pdf_conversion')
    
    def convert_docx_to_pdf(
        self, 
        docx_path: Path, 
        pdf_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        CKDEV-NOTE: PDF conversion using LibreOffice for best formatting preservation
        """
        try:
            success, message, result_path = convert_docx_to_pdf_enhanced(
                str(docx_path), 
                str(pdf_path) if pdf_path else None
            )
            
            if success and result_path:
                self.logger.info(f"PDF generated successfully: {result_path}")
                return Path(result_path)
            else:
                self.logger.error(f"LibreOffice PDF converter failed: {message}")
                raise PDFConversionError(f"Failed to convert {docx_path.name} to PDF: {message}")
                
        except Exception as e:
            self.logger.error(f"PDF conversion error: {e}")
            raise PDFConversionError(f"Failed to convert {docx_path.name} to PDF: {str(e)}")