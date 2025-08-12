"""Security middleware"""

import time
import hashlib
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Callable, Tuple
from flask import request, g, current_app

from ..utils.logger import get_security_logger, log_security_event
from ..utils.helpers import RequestHelper
from ..exceptions import RateLimitError, SecurityError


class RateLimiter:
    """Rate limiting implementation"""
    
    def __init__(self):
        self._requests: Dict[str, deque] = defaultdict(lambda: deque())
        self._last_cleanup = time.time()
        self.cleanup_interval = 3600
    
    def is_allowed(self, key: str, limit: int, window: int) -> Tuple[bool, Dict[str, int]]:
        current_time = time.time()
        
        if current_time - self._last_cleanup > self.cleanup_interval:
            self._cleanup_old_entries()
            self._last_cleanup = current_time
        
        request_times = self._requests[key]
        
        cutoff_time = current_time - window
        while request_times and request_times[0] <= cutoff_time:
            request_times.popleft()
        
        current_count = len(request_times)
        is_allowed = current_count < limit
        
        if is_allowed:
            request_times.append(current_time)
        
        remaining = max(0, limit - current_count - (1 if is_allowed else 0))
        reset_time = int(current_time + window) if request_times else int(current_time)
        
        rate_limit_info = {
            "limit": limit,
            "remaining": remaining,
            "reset": reset_time,
            "retry_after": window if not is_allowed else 0
        }
        
        return is_allowed, rate_limit_info
    
    def _cleanup_old_entries(self):
        cutoff_time = time.time() - 86400
        
        keys_to_remove = []
        for key, request_times in self._requests.items():
            while request_times and request_times[0] <= cutoff_time:
                request_times.popleft()
            
            if not request_times:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._requests[key]


_rate_limiter = RateLimiter()


class SecurityMiddleware:
    """Security middleware for the application"""
    
    def __init__(self, app=None):
        self.app = app
        self.logger = get_security_logger()
        
        self.security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
        }
        
        self.excluded_paths = {
            '/api/health',
            '/api/health/live',
            '/api/health/ready'
        }
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        app.before_request(self.before_request)
        app.after_request(self.after_request)
    
    def before_request(self):
        request.request_id = RequestHelper.get_request_id()
        
        g.start_time = time.time()
        
        self._check_request_security()
        
        if current_app.config.get('RATELIMIT_ENABLED', True):
            self._check_rate_limit()
    
    def after_request(self, response):
        for header, value in self.security_headers.items():
            response.headers[header] = value
        
        if hasattr(g, 'rate_limit_info'):
            self._add_rate_limit_headers(response, g.rate_limit_info)
        
        self._log_request(response)
        
        return response
    
    def _check_request_security(self):
        if request.path in self.excluded_paths:
            return
        
        suspicious_patterns = [
            '..',
            '/etc/',
            '/proc/',
            '/var/',
            '<script',
            'javascript:',
            'data:text/html',
        ]
        
        path_lower = request.path.lower()
        for pattern in suspicious_patterns:
            if pattern in path_lower:
                log_security_event(
                    "suspicious_path",
                    {
                        "path": request.path,
                        "pattern": pattern,
                        "ip": RequestHelper.get_client_ip(),
                        "user_agent": RequestHelper.get_user_agent()
                    },
                    "WARNING"
                )
                break
        
        content_length = request.content_length
        max_size = current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)
        
        if content_length and content_length > max_size:
            log_security_event(
                "oversized_request",
                {
                    "content_length": content_length,
                    "max_allowed": max_size,
                    "ip": RequestHelper.get_client_ip()
                },
                "WARNING"
            )
            raise SecurityError("Request too large")
        
        suspicious_headers = [
            'x-forwarded-host',
            'x-rewrite-url',
            'x-original-url'
        ]
        
        for header in suspicious_headers:
            if header in request.headers:
                log_security_event(
                    "suspicious_header",
                    {
                        "header": header,
                        "value": request.headers[header],
                        "ip": RequestHelper.get_client_ip()
                    },
                    "WARNING"
                )
    
    def _check_rate_limit(self):
        client_ip = RequestHelper.get_client_ip()
        endpoint = request.endpoint or 'unknown'
        rate_key = f"{client_ip}:{endpoint}"
        
        default_limit = current_app.config.get('RATELIMIT_DEFAULT', '100 per hour')
        limit_parts = default_limit.split()
        
        if len(limit_parts) >= 3:
            limit_count = int(limit_parts[0])
            limit_period = limit_parts[2]
            
            period_map = {
                'second': 1,
                'minute': 60,
                'hour': 3600,
                'day': 86400
            }
            
            window = period_map.get(limit_period, 3600)
            
            is_allowed, rate_info = _rate_limiter.is_allowed(rate_key, limit_count, window)
            
            g.rate_limit_info = rate_info
            
            if not is_allowed:
                log_security_event(
                    "rate_limit_exceeded",
                    {
                        "ip": client_ip,
                        "endpoint": endpoint,
                        "limit": limit_count,
                        "window": window
                    },
                    "WARNING"
                )
                
                raise RateLimitError(retry_after=rate_info.get('retry_after'))
    
    def _add_rate_limit_headers(self, response, rate_info):
        if current_app.config.get('RATELIMIT_HEADERS_ENABLED', True):
            response.headers['X-RateLimit-Limit'] = str(rate_info['limit'])
            response.headers['X-RateLimit-Remaining'] = str(rate_info['remaining'])
            response.headers['X-RateLimit-Reset'] = str(rate_info['reset'])
            
            if rate_info.get('retry_after', 0) > 0:
                response.headers['Retry-After'] = str(rate_info['retry_after'])
    
    def _log_request(self, response):
        from ..utils.logger import log_api_request
        
        duration = time.time() - g.start_time
        
        log_api_request(
            endpoint=request.path,
            method=request.method,
            status_code=response.status_code,
            duration=duration,
            ip=RequestHelper.get_client_ip(),
            user_agent=RequestHelper.get_user_agent(),
            request_id=getattr(request, 'request_id', 'unknown')
        )


def require_auth(f: Callable) -> Callable:
    @wraps(f)
    def decorated_function(*args, **kwargs):
        log_security_event(
            "protected_endpoint_access",
            {
                "endpoint": request.path,
                "method": request.method,
                "ip": RequestHelper.get_client_ip()
            },
            "INFO"
        )
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f: Callable) -> Callable:
    @wraps(f)
    def decorated_function(*args, **kwargs):
        log_security_event(
            "admin_endpoint_access",
            {
                "endpoint": request.path,
                "method": request.method,
                "ip": RequestHelper.get_client_ip()
            },
            "WARNING"
        )
        return f(*args, **kwargs)
    return decorated_function


def rate_limit(limit: str = None):
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_app.config.get('RATELIMIT_ENABLED', True):
                return f(*args, **kwargs)
            
            limit_str = limit or current_app.config.get('RATELIMIT_DEFAULT', '100 per hour')
            limit_parts = limit_str.split()
            
            if len(limit_parts) >= 3:
                limit_count = int(limit_parts[0])
                limit_period = limit_parts[2]
                
                period_map = {
                    'second': 1,
                    'minute': 60,
                    'hour': 3600,
                    'day': 86400
                }
                
                window = period_map.get(limit_period, 3600)
                
                client_ip = RequestHelper.get_client_ip()
                endpoint = f.__name__
                rate_key = f"{client_ip}:{endpoint}"
                
                is_allowed, rate_info = _rate_limiter.is_allowed(rate_key, limit_count, window)
                
                if not is_allowed:
                    raise RateLimitError(retry_after=rate_info.get('retry_after'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator