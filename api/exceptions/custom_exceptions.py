from typing import Optional, Dict, Any


class DocSyncException(Exception):
    
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An internal error occurred"
    
    def __init__(
        self,
        message: Optional[str] = None,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message or self.message
        self.status_code = status_code or self.status_code
        self.error_code = error_code or self.error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": False,
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details
            }
        }


class ValidationError(DocSyncException):
    
    status_code = 400
    error_code = "VALIDATION_ERROR"
    message = "Validation failed"
    
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        if field:
            kwargs.setdefault("details", {})["field"] = field
        super().__init__(message=message, **kwargs)


class FileProcessingError(DocSyncException):
    
    status_code = 422
    error_code = "FILE_PROCESSING_ERROR"
    message = "File processing failed"


class PDFExtractionError(FileProcessingError):
    
    error_code = "PDF_EXTRACTION_ERROR"
    message = "Failed to extract data from PDF"
    
    def __init__(self, message: str, pdf_path: Optional[str] = None, **kwargs):
        if pdf_path:
            kwargs.setdefault("details", {})["file"] = pdf_path
        super().__init__(message=message, **kwargs)


class PDFConversionError(FileProcessingError):
    
    error_code = "PDF_CONVERSION_ERROR"
    message = "Failed to convert document to PDF"
    
    def __init__(self, message: str, source_file: Optional[str] = None, **kwargs):
        if source_file:
            kwargs.setdefault("details", {})["source_file"] = source_file
        super().__init__(message=message, **kwargs)


class TemplateProcessingError(FileProcessingError):
    
    error_code = "TEMPLATE_PROCESSING_ERROR"
    message = "Failed to process template"
    
    def __init__(self, message: str, template_type: Optional[str] = None, **kwargs):
        if template_type:
            kwargs.setdefault("details", {})["template_type"] = template_type
        super().__init__(message=message, **kwargs)


class FileNotFoundError(DocSyncException):
    
    status_code = 404
    error_code = "FILE_NOT_FOUND"
    message = "File not found"
    
    def __init__(self, filename: str, **kwargs):
        kwargs.setdefault("details", {})["filename"] = filename
        super().__init__(message=f"File not found: {filename}", **kwargs)


class SessionNotFoundError(DocSyncException):
    
    status_code = 404
    error_code = "SESSION_NOT_FOUND"
    message = "Session not found"
    
    def __init__(self, session_id: str, **kwargs):
        kwargs.setdefault("details", {})["session_id"] = session_id
        super().__init__(message=f"Session not found: {session_id}", **kwargs)


class AuthenticationError(DocSyncException):
    
    status_code = 401
    error_code = "AUTHENTICATION_ERROR"
    message = "Authentication failed"


class AuthorizationError(DocSyncException):
    
    status_code = 403
    error_code = "AUTHORIZATION_ERROR"
    message = "Access denied"


class RateLimitError(DocSyncException):
    
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Too many requests"
    
    def __init__(self, retry_after: Optional[int] = None, **kwargs):
        if retry_after:
            kwargs.setdefault("details", {})["retry_after"] = retry_after
        super().__init__(**kwargs)


class ExternalServiceError(DocSyncException):
    
    status_code = 503
    error_code = "EXTERNAL_SERVICE_ERROR"
    message = "External service unavailable"
    
    def __init__(self, service_name: str, message: Optional[str] = None, **kwargs):
        kwargs.setdefault("details", {})["service"] = service_name
        message = message or f"Service '{service_name}' is unavailable"
        super().__init__(message=message, **kwargs)


class ConfigurationError(DocSyncException):
    
    status_code = 500
    error_code = "CONFIGURATION_ERROR"
    message = "Invalid configuration"
    
    def __init__(self, config_key: str, message: Optional[str] = None, **kwargs):
        kwargs.setdefault("details", {})["config_key"] = config_key
        message = message or f"Invalid configuration for '{config_key}'"
        super().__init__(message=message, **kwargs)


class DataIntegrityError(DocSyncException):
    
    status_code = 422
    error_code = "DATA_INTEGRITY_ERROR"
    message = "Data integrity violation"


class SecurityError(DocSyncException):
    
    status_code = 403
    error_code = "SECURITY_ERROR"
    message = "Security violation detected"
    
    def __init__(self, message: Optional[str] = None, **kwargs):
        message = message or "Security check failed"
        super().__init__(message=message, **kwargs)