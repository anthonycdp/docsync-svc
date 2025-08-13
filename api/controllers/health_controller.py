from flask import Blueprint
import os
import psutil
from datetime import datetime

from ..config import Config
from ..services import PDFConversionService
from ..utils.helpers import ResponseBuilder
from ..utils.logger import get_api_logger


def create_health_controller(config: Config, pdf_service: PDFConversionService = None) -> Blueprint:
    
    bp = Blueprint('health', __name__, url_prefix='/api/health')
    logger = get_api_logger()
    
    @bp.route('', methods=['GET'])
    def health_check():
        try:
            directories_status = {}
            for dir_name, dir_path in [
                ('upload', config.UPLOAD_FOLDER),
                ('output', config.OUTPUT_DIR),
                ('templates', config.TEMPLATES_DIR),
                ('logs', config.LOG_DIR)
            ]:
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    test_file = dir_path / f".write_test_{os.getpid()}"
                    test_file.touch()
                    test_file.unlink()
                    directories_status[dir_name] = {
                        "path": str(dir_path),
                        "exists": True,
                        "writable": True,
                        "status": "healthy"
                    }
                except Exception as e:
                    directories_status[dir_name] = {
                        "path": str(dir_path),
                        "exists": dir_path.exists() if hasattr(dir_path, 'exists') else False,
                        "writable": False,
                        "status": "error",
                        "error": str(e)
                    }
            
            all_healthy = all(d["status"] == "healthy" for d in directories_status.values())
            
            response_data = {
                "status": "healthy" if all_healthy else "degraded",
                "timestamp": datetime.utcnow().isoformat(),
                "version": config.APP_VERSION,
                "directories": directories_status
            }
            
            status_code = 200 if all_healthy else 503
            
            return ResponseBuilder.success(data=response_data), status_code
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return ResponseBuilder.error("Health check failed"), 503
    
    @bp.route('/detailed', methods=['GET'])
    def detailed_health_check():
        try:
            basic_health = health_check()
            basic_data = basic_health[0].json.get('data', {})
            
            system_info = {
                "cpu": {
                    "percent": psutil.cpu_percent(interval=1),
                    "count": psutil.cpu_count()
                },
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available,
                    "percent": psutil.virtual_memory().percent
                },
                "disk": {}
            }
            
            for dir_name, dir_path in [
                ('upload', config.UPLOAD_FOLDER),
                ('output', config.OUTPUT_DIR)
            ]:
                try:
                    if dir_path.exists():
                        disk_usage = psutil.disk_usage(str(dir_path))
                        system_info["disk"][dir_name] = {
                            "total": disk_usage.total,
                            "free": disk_usage.free,
                            "percent": (disk_usage.used / disk_usage.total) * 100
                        }
                except Exception:
                    system_info["disk"][dir_name] = {"error": "Unable to get disk usage"}
            
            pdf_info = {}
            if pdf_service:
                try:
                    pdf_info = pdf_service.get_method_info()
                except Exception as e:
                    pdf_info = {"error": str(e)}
            
            detailed_data = {
                **basic_data,
                "system": system_info,
                "pdf_conversion": pdf_info,
                "config": {
                    "debug": False,  # CKDEV-NOTE: Debug mode always disabled
                    "environment": os.getenv("FLASK_ENV", "unknown"),
                    "max_content_length": config.MAX_CONTENT_LENGTH,
                    "cors_origins": config.CORS_ORIGINS
                }
            }
            
            return ResponseBuilder.success(data=detailed_data), 200
            
        except Exception as e:
            logger.error(f"Detailed health check failed: {e}")
            return ResponseBuilder.error("Detailed health check failed"), 503
    
    @bp.route('/ready', methods=['GET'])
    def readiness_check():
        try:
            ready = True
            checks = {}
            
            for dir_name, dir_path in [
                ('upload', config.UPLOAD_FOLDER),
                ('output', config.OUTPUT_DIR)
            ]:
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    checks[f"{dir_name}_directory"] = True
                except Exception:
                    checks[f"{dir_name}_directory"] = False
                    ready = False
            
            if pdf_service:
                try:
                    available_methods = pdf_service.get_available_methods()
                    checks["pdf_conversion"] = len(available_methods) > 0
                    if not checks["pdf_conversion"]:
                        ready = False
                except Exception:
                    checks["pdf_conversion"] = False
                    ready = False
            
            response_data = {
                "ready": ready,
                "checks": checks,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return ResponseBuilder.success(data=response_data), 200 if ready else 503
            
        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            return ResponseBuilder.error("Readiness check failed"), 503
    
    @bp.route('/live', methods=['GET'])
    def liveness_check():
        try:
            return ResponseBuilder.success(
                data={
                    "alive": True,
                    "timestamp": datetime.utcnow().isoformat()
                }
            ), 200
            
        except Exception as e:
            logger.error(f"Liveness check failed: {e}")
            return ResponseBuilder.error("Liveness check failed"), 503
    
    @bp.route('/version', methods=['GET'])
    def get_version():
        try:
            import sys
            import platform
            
            version_info = {
                "app": {
                    "name": config.APP_NAME,
                    "version": config.APP_VERSION,
                    "environment": os.getenv("FLASK_ENV", "unknown")
                },
                "runtime": {
                    "python": sys.version,
                    "platform": platform.platform(),
                    "architecture": platform.architecture()[0]
                }
            }
            
            return ResponseBuilder.success(data=version_info), 200
            
        except Exception as e:
            logger.error(f"Get version failed: {e}")
            return ResponseBuilder.error("Version check failed"), 500
    
    return bp