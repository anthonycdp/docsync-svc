"""Exceptions module"""

from .custom_exceptions import (
    DocSyncException,
    ValidationError,
    FileProcessingError,
    PDFExtractionError,
    PDFConversionError,
    TemplateProcessingError,
    FileNotFoundError,
    SessionNotFoundError,
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
    ExternalServiceError,
    ConfigurationError,
    DataIntegrityError,
    SecurityError
)

from .handlers import register_error_handlers

__all__ = [
    "DocSyncException",
    "ValidationError", 
    "FileProcessingError",
    "PDFExtractionError",
    "PDFConversionError",
    "TemplateProcessingError",
    "FileNotFoundError",
    "SessionNotFoundError",
    "AuthenticationError",
    "AuthorizationError",
    "RateLimitError",
    "ExternalServiceError",
    "ConfigurationError",
    "DataIntegrityError",
    "SecurityError",
    "register_error_handlers"
]