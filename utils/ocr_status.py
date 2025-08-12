import logging
from typing import Dict, List

class OCRStatusChecker:
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._tesseract_available = None
        self._poppler_available = None
    
    def check_tesseract(self) -> bool:
        if self._tesseract_available is not None: return self._tesseract_available
        try:
            import pytesseract; pytesseract.get_tesseract_version()
            self._tesseract_available = True; return True
        except Exception:
            self._tesseract_available = False; return False
    
    def check_poppler(self) -> bool:
        if self._poppler_available is not None: return self._poppler_available
        try:
            from pdf2image import convert_from_path
            self._poppler_available = True; return True
        except Exception:
            self._poppler_available = False; return False
    
    def get_ocr_status(self) -> Dict[str, bool]:
        tess, popp = self.check_tesseract(), self.check_poppler()
        return {'tesseract': tess, 'poppler': popp, 'ocr_available': tess and popp}
    
    def get_user_friendly_status(self) -> str:
        status = self.get_ocr_status()
        return ("OCR completo disponível - Extração automática de CNH-e ativada" if status['ocr_available'] 
                else "Tesseract OK, mas Poppler não encontrado - Funcionalidade OCR limitada" if status['tesseract'] and not status['poppler']
                else "Poppler OK, mas Tesseract não encontrado - Funcionalidade OCR limitada" if not status['tesseract'] and status['poppler']
                else "OCR não disponível - Sistema usa dados de teste seguros (funcionalidade normal)")
    
    def get_installation_instructions(self) -> List[str]:
        status = self.get_ocr_status()
        instructions = []
        if not status['tesseract']: instructions.append("Para instalar Tesseract: ver seção 'Tesseract OCR' em INSTALL_DEPENDENCIES.md")
        if not status['poppler']: instructions.append("Para instalar Poppler: ver seção 'Poppler' em INSTALL_DEPENDENCIES.md")
        return instructions or ["Todas as dependências OCR estão instaladas"]
    
    def log_friendly_status(self):
        self.logger.info(self.get_user_friendly_status())
        instructions = self.get_installation_instructions()
        if instructions and instructions[0] != "Todas as dependências OCR estão instaladas":
            [self.logger.info(instruction) for instruction in instructions]

ocr_checker = OCRStatusChecker()

def log_ocr_status_once():
    if not hasattr(log_ocr_status_once, '_logged'):
        ocr_checker.log_friendly_status(); log_ocr_status_once._logged = True

def is_ocr_available() -> bool:
    return ocr_checker.get_ocr_status()['ocr_available']

def get_ocr_fallback_message() -> str:
    return "OCR não disponível - usando dados de teste seguros (sistema funcionando normalmente)"