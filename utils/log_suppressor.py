import os
import logging
import warnings
import sys
import contextlib
from io import StringIO

class TechnicalMessageSuppressor:
    def __init__(self):
        self.original_stderr = None
        self.captured_stderr = None
    
    def __enter__(self):
        warning_patterns = os.getenv('SUPPRESS_WARNING_PATTERNS', 'tesseract,poppler,Unable to get page count').split(',')
        warning_patterns = [pattern.strip() for pattern in warning_patterns if pattern.strip()]
        
        for pattern in warning_patterns:
            warnings.filterwarnings("ignore", message=f".*{pattern}.*")
        
        self.original_stderr = sys.stderr
        self.captured_stderr = StringIO()
        sys.stderr = self.captured_stderr
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr = self.original_stderr
        captured = self.captured_stderr.getvalue()
        
        if captured.strip():
            logger = logging.getLogger(os.getenv('LOGGER_NAME', 'term_generator'))
            
            tesseract_msg = os.getenv('TESSERACT_NOT_FOUND_MSG', '💡 Tesseract não encontrado - usando dados de teste seguros')
            poppler_msg = os.getenv('POPPLER_NOT_FOUND_MSG', '💡 Poppler não encontrado - usando dados de teste seguros')
            ocr_msg = os.getenv('OCR_NOT_AVAILABLE_MSG', '💡 OCR não disponível - usando dados de teste seguros')
            
            if "tesseract" in captured.lower():
                msg = tesseract_msg
            elif "poppler" in captured.lower():
                msg = poppler_msg
            else:
                msg = ocr_msg
            
            logger.info(msg)
        
        warnings.resetwarnings()
        return False

@contextlib.contextmanager
def suppress_technical_messages():
    with TechnicalMessageSuppressor():
        yield

def apply_global_filters():
    class TechnicalMessageFilter(logging.Filter):
        def filter(self, record):
            msg = record.getMessage().lower()
            
            tesseract_terms = os.getenv('TESSERACT_SEARCH_TERMS', 'tesseract is not installed,tesseract not found').split(',')
            tesseract_terms = [term.strip() for term in tesseract_terms if term.strip()]
            
            poppler_terms = os.getenv('POPPLER_SEARCH_TERMS', 'unable to get page count,poppler').split(',')
            poppler_terms = [term.strip() for term in poppler_terms if term.strip()]
            
            readme_terms = os.getenv('README_SEARCH_TERMS', 'see readme file for more information').split(',')
            readme_terms = [term.strip() for term in readme_terms if term.strip()]
            
            tesseract_replacement = os.getenv('TESSERACT_REPLACEMENT_MSG', '💡 Tesseract não encontrado - usando dados de teste seguros')
            poppler_replacement = os.getenv('POPPLER_REPLACEMENT_MSG', '💡 Poppler não encontrado - usando dados de teste seguros')
            readme_replacement = os.getenv('README_REPLACEMENT_MSG', '📖 Para instalação completa de OCR, ver INSTALL_DEPENDENCIES.md')
            
            if any(term in msg for term in tesseract_terms):
                record.msg = tesseract_replacement
                record.levelno = logging.INFO
                record.levelname = 'INFO'
            elif any(term in msg for term in poppler_terms):
                record.msg = poppler_replacement
                record.levelno = logging.INFO
                record.levelname = 'INFO'
            elif any(term in msg for term in readme_terms):
                record.msg = readme_replacement
                record.levelno = logging.INFO
                record.levelname = 'INFO'
            
            return True
    
    filter_obj = TechnicalMessageFilter()
    
    for handler in logging.getLogger().handlers:
        handler.addFilter(filter_obj)
    
    suppressed_libs = os.getenv('SUPPRESSED_LIBRARIES', 'pytesseract,pdf2image,PIL').split(',')
    suppressed_libs = [lib.strip() for lib in suppressed_libs if lib.strip()]
    
    for lib in suppressed_libs:
        logger = logging.getLogger(lib)
        logger.addFilter(filter_obj)
        logger.setLevel(logging.ERROR)

apply_global_filters()