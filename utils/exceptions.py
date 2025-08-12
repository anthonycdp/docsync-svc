import os
from typing import Optional, Dict, Any


class TermGeneratorError(Exception):
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Inicializa exceção com mensagem e detalhes opcionais
        
        Args:
            message: Mensagem de erro
            details: Detalhes adicionais do erro (serão sanitizados em logs)
        """
        super().__init__(message)
        self.details = details or {}


class PDFExtractionError(TermGeneratorError):
    
    def __init__(
        self, 
        message: str, 
        pdf_path: Optional[str] = None,
        page_number: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Erro específico de extração de PDF
        
        Args:
            message: Mensagem de erro
            pdf_path: Caminho do PDF que causou erro
            page_number: Página específica onde ocorreu erro
            details: Detalhes adicionais
        """
        error_details = details or {}
        if pdf_path:
            error_details['pdf_path'] = pdf_path
        if page_number:
            error_details['page_number'] = page_number
            
        super().__init__(message, error_details)
        self.pdf_path = pdf_path
        self.page_number = page_number


class DocumentProcessingError(TermGeneratorError):
    """Erro no processamento de documentos DOCX"""
    
    def __init__(
        self,
        message: str,
        template_path: Optional[str] = None,
        field_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Erro específico de processamento de documento
        
        Args:
            message: Mensagem de erro
            template_path: Caminho do template que causou erro
            field_name: Campo específico que causou erro
            details: Detalhes adicionais
        """
        error_details = details or {}
        if template_path:
            error_details['template_path'] = template_path
        if field_name:
            error_details['field_name'] = field_name
            
        super().__init__(message, error_details)
        self.template_path = template_path
        self.field_name = field_name


class TemplateNotFoundError(DocumentProcessingError):
    
    def __init__(self, template_path: str):
        """Erro de template não encontrado
        
        Args:
            template_path: Caminho do template não encontrado
        """
        super().__init__(
            f"Template não encontrado: {template_path}",
            template_path=template_path
        )


class ValidationError(TermGeneratorError):
    
    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        field_value: Optional[str] = None,
        validation_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Erro específico de validação
        
        Args:
            message: Mensagem de erro
            field_name: Nome do campo que falhou na validação
            field_value: Valor que falhou (será sanitizado em logs)
            validation_type: Tipo de validação (cpf, placa, etc.)
            details: Detalhes adicionais
        """
        error_details = details or {}
        if field_name:
            error_details['field_name'] = field_name
        if field_value:
            sanitized_value = os.getenv('ERROR_SANITIZED_VALUE', '***')
            error_details['field_value'] = sanitized_value
        if validation_type:
            error_details['validation_type'] = validation_type
            
        super().__init__(message, error_details)
        self.field_name = field_name
        self.field_value = field_value
        self.validation_type = validation_type


class ConfigurationError(TermGeneratorError):
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        expected_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Erro de configuração
        
        Args:
            message: Mensagem de erro
            config_key: Chave de configuração problemática
            expected_type: Tipo esperado para a configuração
            details: Detalhes adicionais
        """
        error_details = details or {}
        if config_key:
            error_details['config_key'] = config_key
        if expected_type:
            error_details['expected_type'] = expected_type
            
        super().__init__(message, error_details)
        self.config_key = config_key
        self.expected_type = expected_type


class OCRError(PDFExtractionError):
    
    def __init__(
        self,
        message: str,
        pdf_path: Optional[str] = None,
        ocr_language: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Erro específico de OCR
        
        Args:
            message: Mensagem de erro
            pdf_path: Caminho do PDF
            ocr_language: Idioma usado no OCR
            details: Detalhes adicionais
        """
        error_details = details or {}
        if ocr_language:
            error_details['ocr_language'] = ocr_language
            
        super().__init__(message, pdf_path, details=error_details)
        self.ocr_language = ocr_language


class BrandLookupError(TermGeneratorError):
    
    def __init__(
        self,
        message: str,
        vehicle_model: Optional[str] = None,
        lookup_method: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Erro de lookup de marca
        
        Args:
            message: Mensagem de erro
            vehicle_model: Modelo do veículo pesquisado
            lookup_method: Método de busca utilizado
            details: Detalhes adicionais
        """
        error_details = details or {}
        if vehicle_model:
            error_details['vehicle_model'] = vehicle_model
        if lookup_method:
            error_details['lookup_method'] = lookup_method
            
        super().__init__(message, error_details)
        self.vehicle_model = vehicle_model
        self.lookup_method = lookup_method


def handle_exception(
    error: Exception,
    operation: str = "",
    logger = None,
    reraise: bool = True
) -> Optional[Exception]:
    """Manipulador centralizado de exceções
    
    Args:
        error: Exceção a ser tratada
        operation: Nome da operação que causou erro
        logger: Logger para registrar erro
        reraise: Se deve relançar a exceção
        
    Returns:
        Exceção processada se não for relançada
    """
    
    if logger:
        if isinstance(error, TermGeneratorError):
            logger.error(
                f"Erro em '{operation}': {error}",
                extra={'error_type': error.__class__.__name__, **error.details}
            )
        else:
            logger.exception(f"Erro inesperado em '{operation}': {error}")
    
    if reraise:
        raise error
    
    return error