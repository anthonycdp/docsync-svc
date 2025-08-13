import logging
import traceback
from typing import Tuple, Dict, Any
from flask import jsonify, request, current_app
from werkzeug.exceptions import HTTPException
from datetime import datetime
import uuid

from .custom_exceptions import DocSyncException

logger = logging.getLogger(__name__)


def generate_error_id() -> str:
    return str(uuid.uuid4())


def log_error(error: Exception, error_id: str) -> None:
    logger.error(
        f"Error ID: {error_id} | "
        f"Path: {request.path} | "
        f"Method: {request.method} | "
        f"IP: {request.remote_addr} | "
        f"Error: {str(error)}",
        exc_info=True
    )


def create_error_response(
    message: str,
    status_code: int,
    error_code: str = "UNKNOWN_ERROR",
    details: Dict[str, Any] = None,
    error_id: str = None
) -> Tuple[Dict[str, Any], int]:
    
    response = {
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
            "details": details or {}
        },
        "meta": {
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.path,
            "method": request.method
        }
    }
    
    if error_id:
        response["meta"]["error_id"] = error_id
    
    if hasattr(request, "trace_id"):
        response["meta"]["trace_id"] = request.trace_id
    
    return response, status_code


def handle_docsync_exception(error: DocSyncException) -> Tuple[Dict[str, Any], int]:
    error_id = generate_error_id()
    log_error(error, error_id)
    
    response = error.to_dict()
    response["meta"] = {
        "timestamp": datetime.utcnow().isoformat(),
        "error_id": error_id,
        "path": request.path,
        "method": request.method
    }
    
    return jsonify(response), error.status_code


def handle_http_exception(error: HTTPException) -> Tuple[Dict[str, Any], int]:
    error_id = generate_error_id()
    
    if error.code >= 500:
        log_error(error, error_id)
    
    response, status_code = create_error_response(
        message=error.description or "HTTP error occurred",
        status_code=error.code,
        error_code=f"HTTP_{error.code}",
        error_id=error_id if error.code >= 500 else None
    )
    
    return jsonify(response), status_code


def handle_validation_error(error: Exception) -> Tuple[Dict[str, Any], int]:
    error_id = generate_error_id()
    logger.warning(f"Validation error: {str(error)} | Error ID: {error_id}")
    
    details = {}
    if hasattr(error, "messages"):
        details["validation_errors"] = error.messages
    elif hasattr(error, "errors"):
        details["validation_errors"] = error.errors
    
    response, status_code = create_error_response(
        message="Validation failed",
        status_code=400,
        error_code="VALIDATION_ERROR",
        details=details,
        error_id=error_id
    )
    
    return jsonify(response), status_code


def handle_generic_exception(error: Exception) -> Tuple[Dict[str, Any], int]:
    error_id = generate_error_id()
    log_error(error, error_id)
    
    # CKDEV-NOTE: Debug mode always disabled - no detailed error information
    message = "An internal server error occurred"
    details = {}
    
    response, status_code = create_error_response(
        message=message,
        status_code=500,
        error_code="INTERNAL_ERROR",
        details=details,
        error_id=error_id
    )
    
    return jsonify(response), status_code


def register_error_handlers(app):
    
    @app.errorhandler(DocSyncException)
    def handle_custom_exception(error):
        return handle_docsync_exception(error)
    
    @app.errorhandler(HTTPException)
    def handle_http(error):
        return handle_http_exception(error)
    
    @app.errorhandler(422)
    def handle_unprocessable_entity(error):
        return handle_validation_error(error)
    
    @app.errorhandler(Exception)
    def handle_generic(error):
        return handle_generic_exception(error)
    
    @app.errorhandler(404)
    def handle_not_found(error):
        response, status_code = create_error_response(
            message="Resource not found",
            status_code=404,
            error_code="NOT_FOUND"
        )
        return jsonify(response), status_code
    
    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        response, status_code = create_error_response(
            message=f"Method {request.method} not allowed for this endpoint",
            status_code=405,
            error_code="METHOD_NOT_ALLOWED",
            details={"allowed_methods": error.valid_methods if hasattr(error, "valid_methods") else []}
        )
        return jsonify(response), status_code
    
    @app.errorhandler(413)
    def handle_request_entity_too_large(error):
        max_size = current_app.config.get("MAX_CONTENT_LENGTH", 16777216)
        response, status_code = create_error_response(
            message=f"Request entity too large. Maximum size is {max_size / 1048576:.1f}MB",
            status_code=413,
            error_code="ENTITY_TOO_LARGE",
            details={"max_size_bytes": max_size}
        )
        return jsonify(response), status_code
    
    @app.errorhandler(429)
    def handle_too_many_requests(error):
        response, status_code = create_error_response(
            message="Too many requests. Please try again later.",
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED"
        )
        return jsonify(response), status_code