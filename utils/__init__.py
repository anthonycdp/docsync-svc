from .brand_lookup import get_brand_lookup
from .validators import (validate_cpf, validate_vehicle_plate, validate_chassis_number, sanitize_log_data)
from .logging_config import setup_logging, get_logger, LoggerMixin
from .exceptions import (TermGeneratorError, PDFExtractionError, DocumentProcessingError, TemplateNotFoundError, ValidationError, ConfigurationError, OCRError, BrandLookupError, handle_exception)
from .pdf_converter import convert_docx_to_pdf

def format_currency_value(value_str: str) -> str:
    """CKDEV-NOTE: Centralized currency formatting to ensure consistency across all processors"""
    import re
    if not value_str or not value_str.strip(): 
        return ""
    try:
        clean_value = re.sub(r'[^\d.,]', '', value_str.strip())
        if ',' in clean_value and clean_value.count(',') == 1: 
            parts = clean_value.split(',')
            return f"R$ {clean_value}" if len(parts) == 2 and len(parts[1]) == 2 else f"R$ {value_str}"
        if '.' in clean_value: 
            float_value = float(clean_value)
            formatted = f"{float_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return f"R$ {formatted}"
        else: 
            num_value = int(clean_value)
            return f"R$ {num_value},00" if num_value <= 999 else f"R$ {f'{num_value:,}'.replace(',', '.')},00"
    except (ValueError, TypeError): 
        return ""

__all__ = ['get_brand_lookup', 'validate_cpf', 'validate_vehicle_plate', 'validate_chassis_number', 'sanitize_log_data', 'setup_logging', 'get_logger', 'LoggerMixin', 'TermGeneratorError', 'PDFExtractionError', 'DocumentProcessingError', 'TemplateNotFoundError', 'ValidationError', 'ConfigurationError', 'OCRError', 'BrandLookupError', 'handle_exception', 'convert_docx_to_pdf', 'format_currency_value']