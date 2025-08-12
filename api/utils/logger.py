"""Structured logging system"""

import logging
import logging.handlers
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union
from contextlib import contextmanager

from ..config import Config


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def __init__(self):
        super().__init__()
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        if hasattr(record, 'process'):
            log_entry["process_id"] = record.process
        
        if hasattr(record, 'thread'):
            log_entry["thread_id"] = record.thread
        
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in [
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                'thread', 'threadName', 'processName', 'process', 'message'
            ]:
                extra_fields[key] = value
        
        if extra_fields:
            log_entry["extra"] = extra_fields
        
        return json.dumps(log_entry, ensure_ascii=False)


class FriendlyFormatter(logging.Formatter):
    """User-friendly log formatter"""
    
    def format(self, record: logging.LogRecord) -> str:
        return super().format(record)


class ContextualLogger:
    """Logger with contextual information"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.context = {}
    
    def set_context(self, **kwargs):
        self.context.update(kwargs)
    
    def clear_context(self):
        self.context = {}
    
    def _log_with_context(self, level: int, message: str, *args, **kwargs):
        extra = kwargs.get('extra', {})
        extra.update(self.context)
        kwargs['extra'] = extra
        
        self.logger.log(level, message, *args, **kwargs)
    
    def debug(self, message: str, *args, **kwargs):
        self._log_with_context(logging.DEBUG, message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        self._log_with_context(logging.INFO, message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        self._log_with_context(logging.WARNING, message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        self._log_with_context(logging.ERROR, message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        self._log_with_context(logging.CRITICAL, message, *args, **kwargs)


class LoggerManager:
    """Centralized logger management"""
    
    _configured = False
    _loggers = {}
    
    @classmethod
    def configure(cls, config: Config):
        if cls._configured:
            return
        
        log_dir = Path(config.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, config.LOG_LEVEL.upper()))
        
        root_logger.handlers.clear()
        
        # Use friendly formatter for console in development
        if config.DEBUG and config.LOG_FORMAT_CONSOLE:
            console_formatter = FriendlyFormatter(config.LOG_FORMAT_CONSOLE)
        else:
            console_formatter = JSONFormatter()
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(getattr(logging, config.LOG_LEVEL.upper()))
        root_logger.addHandler(console_handler)
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_dir / config.LOG_FILE,
            maxBytes=config.LOG_MAX_BYTES,
            backupCount=config.LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setFormatter(JSONFormatter())
        file_handler.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)
        
        error_handler = logging.handlers.RotatingFileHandler(
            filename=log_dir / 'errors.log',
            maxBytes=config.LOG_MAX_BYTES,
            backupCount=config.LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        error_handler.setFormatter(JSONFormatter())
        error_handler.setLevel(logging.ERROR)
        root_logger.addHandler(error_handler)
        
        perf_handler = logging.handlers.RotatingFileHandler(
            filename=log_dir / 'performance.log',
            maxBytes=config.LOG_MAX_BYTES,
            backupCount=5,
            encoding='utf-8'
        )
        perf_handler.setFormatter(JSONFormatter())
        perf_handler.setLevel(logging.INFO)
        
        perf_logger = logging.getLogger('performance')
        perf_logger.addHandler(perf_handler)
        perf_logger.setLevel(logging.INFO)
        perf_logger.propagate = False
        
        security_handler = logging.handlers.RotatingFileHandler(
            filename=log_dir / 'security.log',
            maxBytes=config.LOG_MAX_BYTES,
            backupCount=10,
            encoding='utf-8'
        )
        security_handler.setFormatter(JSONFormatter())
        security_handler.setLevel(logging.WARNING)
        
        security_logger = logging.getLogger('security')
        security_logger.addHandler(security_handler)
        security_logger.setLevel(logging.WARNING)
        security_logger.propagate = False
        
        cls._configured = True
    
    @classmethod
    def get_logger(cls, name: str) -> ContextualLogger:
        if name not in cls._loggers:
            cls._loggers[name] = ContextualLogger(name)
        return cls._loggers[name]


def get_app_logger() -> ContextualLogger:
    return LoggerManager.get_logger('docsync.app')


def get_api_logger() -> ContextualLogger:
    return LoggerManager.get_logger('docsync.api')


def get_service_logger(service_name: str) -> ContextualLogger:
    return LoggerManager.get_logger(f'docsync.service.{service_name}')


def get_security_logger() -> ContextualLogger:
    return LoggerManager.get_logger('security')


def get_performance_logger() -> ContextualLogger:
    return LoggerManager.get_logger('performance')


@contextmanager
def log_performance(operation_name: str, logger: ContextualLogger = None):
    if logger is None:
        logger = get_performance_logger()
    
    start_time = datetime.utcnow()
    
    try:
        logger.info(
            f"Starting operation: {operation_name}",
            extra={
                "operation": operation_name,
                "event": "start",
                "start_time": start_time.isoformat()
            }
        )
        yield
        
    except Exception as e:
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        logger.error(
            f"Operation failed: {operation_name}",
            extra={
                "operation": operation_name,
                "event": "error",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "error": str(e),
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        raise
        
    else:
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(
            f"Operation completed: {operation_name}",
            extra={
                "operation": operation_name,
                "event": "success",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration
            }
        )


def log_api_request(endpoint: str, method: str, status_code: int, duration: float, **kwargs):
    logger = get_api_logger()
    
    log_data = {
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "duration_seconds": duration,
        "event": "api_request"
    }
    log_data.update(kwargs)
    
    if status_code >= 500:
        logger.error(f"API Error: {method} {endpoint}", extra=log_data)
    elif status_code >= 400:
        logger.warning(f"API Client Error: {method} {endpoint}", extra=log_data)
    else:
        logger.info(f"API Request: {method} {endpoint}", extra=log_data)


def log_security_event(event_type: str, details: Dict[str, Any], severity: str = "WARNING"):
    logger = get_security_logger()
    
    log_data = {
        "event_type": event_type,
        "event": "security",
        "severity": severity
    }
    log_data.update(details)
    
    if severity.upper() == "CRITICAL":
        logger.critical(f"Security Event: {event_type}", extra=log_data)
    elif severity.upper() == "ERROR":
        logger.error(f"Security Event: {event_type}", extra=log_data)
    else:
        logger.warning(f"Security Event: {event_type}", extra=log_data)


def log_file_operation(operation: str, file_path: str, success: bool, **kwargs):
    logger = get_service_logger('file')
    
    log_data = {
        "operation": operation,
        "file_path": file_path,
        "success": success,
        "event": "file_operation"
    }
    log_data.update(kwargs)
    
    if success:
        logger.info(f"File operation successful: {operation}", extra=log_data)
    else:
        logger.error(f"File operation failed: {operation}", extra=log_data)


class RequestIDFilter(logging.Filter):
    """Filter to add request ID to logs"""
    
    def filter(self, record):
        try:
            from flask import has_request_context, request
            if has_request_context() and hasattr(request, 'request_id'):
                record.request_id = request.request_id
        except:
            pass
        return True