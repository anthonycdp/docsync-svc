import os
import logging
import logging.handlers
import sys
import re
from pathlib import Path
from typing import Optional
from functools import reduce
try: 
    from ..config import Config
except ImportError: 
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import Config

class SensitiveDataFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        patterns_str = os.getenv('SENSITIVE_DATA_PATTERNS', 
            r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b,\b\d{1,2}\.?\d{3}\.?\d{3}-?\d{1}\b,\b[A-HJ-NPR-Z0-9]{17}\b,\b[A-Z]{3}-?\d{4}\b|\b[A-Z]{3}\d[A-Z]\d{2}\b')
        self.sensitive_patterns = [pattern.strip() for pattern in patterns_str.split(',') if pattern.strip()]
    
    def filter(self, record: logging.LogRecord) -> bool:
        sanitized_value = os.getenv('LOG_SANITIZED_VALUE', '***')
        
        for pattern in self.sensitive_patterns:
            record.msg = re.sub(pattern, sanitized_value, str(record.msg))
        
        if record.args:
            record.args = tuple(
                arg if not isinstance(arg, str) 
                else reduce(lambda s, p: re.sub(p, sanitized_value, s), self.sensitive_patterns, arg) 
                for arg in record.args
            )
        return True

class StructuredFormatter(logging.Formatter):
    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
    
    def format(self, record: logging.LogRecord) -> str:
        base_format = os.getenv('LOG_BASE_FORMAT', "%(asctime)s - %(name)s - %(levelname)s")
        log_format = base_format
        
        if self.include_extra:
            extra_formats = []
            if hasattr(record, 'process_id'):
                process_format = os.getenv('LOG_PROCESS_FORMAT', " - PID:%(process_id)s")
                extra_formats.append(process_format)
            if hasattr(record, 'thread_name'):
                thread_format = os.getenv('LOG_THREAD_FORMAT', " - Thread:%(thread_name)s")
                extra_formats.append(thread_format)
            log_format += "".join(extra_formats)
        
        message_format = os.getenv('LOG_MESSAGE_FORMAT', " - %(message)s")
        return logging.Formatter(log_format + message_format).format(record)


def setup_logging(config: Optional[Config] = None) -> logging.Logger:
    config = config or Config()
    
    logger_name = os.getenv('LOGGER_NAME', 'term_generator')
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper()))
    
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    log_dir = Path(config.LOGS_DIR)
    log_dir.mkdir(exist_ok=True)
    
    log_encoding = os.getenv('LOG_ENCODING', 'utf-8')
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(StructuredFormatter(include_extra=False))
    console_handler.addFilter(SensitiveDataFilter())
    logger.addHandler(console_handler)
    
    log_filename = os.getenv('LOG_FILENAME', 'term_generator.log')
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / log_filename, 
        maxBytes=config.LOG_MAX_BYTES, 
        backupCount=config.LOG_BACKUP_COUNT, 
        encoding=log_encoding
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = StructuredFormatter(include_extra=True)
    file_handler.setFormatter(file_formatter)
    file_handler.addFilter(SensitiveDataFilter())
    logger.addHandler(file_handler)
    
    error_filename = os.getenv('LOG_ERROR_FILENAME', 'term_generator_errors.log')
    error_max_bytes = int(os.getenv('LOG_ERROR_MAX_BYTES', str(config.LOG_MAX_BYTES // 2)))
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / error_filename, 
        maxBytes=error_max_bytes, 
        backupCount=config.LOG_BACKUP_COUNT, 
        encoding=log_encoding
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    error_handler.addFilter(SensitiveDataFilter())
    logger.addHandler(error_handler)
    
    init_message = os.getenv('LOG_INIT_MESSAGE', 'Sistema de logging inicializado')
    logger.info(init_message)
    return logger


def get_logger(name: str) -> logging.Logger:
    logger_name = os.getenv('LOGGER_NAME', 'term_generator')
    return logging.getLogger(f'{logger_name}.{name}')

class LoggerMixin:
    @property
    def logger(self) -> logging.Logger:
        return get_logger(self.__class__.__name__)
    
    def log_operation(self, operation: str, **kwargs) -> None:
        from .validators import sanitize_log_data
        operation_prefix = os.getenv('LOG_OPERATION_PREFIX', 'Operação: ')
        self.logger.info(f"{operation_prefix}{operation}", extra=sanitize_log_data(kwargs) if kwargs else {})
    
    def log_error(self, error: Exception, operation: str = "", **kwargs) -> None:
        from .validators import sanitize_log_data
        context = sanitize_log_data(kwargs) if kwargs else {}
        
        error_prefix = os.getenv('LOG_ERROR_PREFIX', 'Erro')
        operation_separator = os.getenv('LOG_OPERATION_SEPARATOR', ' em ')
        
        if operation:
            error_message = f"{error_prefix}{operation_separator}{repr(operation)}: {error}"
        else:
            error_message = f"{error_prefix}: {error}"
        
        self.logger.error(error_message, extra=context, exc_info=True)
    
    def log_warning(self, message: str, **kwargs) -> None:
        from .validators import sanitize_log_data
        context = sanitize_log_data(kwargs) if kwargs else {}
        self.logger.warning(message, extra=context)
    
    def log_info(self, message: str, **kwargs) -> None:
        from .validators import sanitize_log_data
        context = sanitize_log_data(kwargs) if kwargs else {}
        self.logger.info(message, extra=context)