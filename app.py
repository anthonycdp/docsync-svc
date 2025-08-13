"""Doc Sync API - Main Application"""

import os
import atexit
from flask import Flask
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from api.config import get_config, Config
from api.exceptions import register_error_handlers
from api.middleware import SecurityMiddleware
from api.utils.logger import LoggerManager, get_app_logger
from api.utils.startup import StartupLogger, suppress_werkzeug_startup
from api.services import PDFConversionService, SessionService, FileService
from api.controllers import (
    create_file_controller,
    create_document_controller,
    create_session_controller,
    create_health_controller
)


def setup_cleanup_scheduler(app: Flask, file_service: FileService, config: Config) -> None:
    """Setup automatic cleanup scheduler for temporary files"""
    logger = get_app_logger()
    
    if not config.CLEANUP_ENABLED:
        logger.info("Automatic cleanup disabled via configuration")
        return
    
    def cleanup_temp_files():
        """Execute cleanup of temporary files with error handling"""
        try:
            logger.info("Iniciando limpeza automática de arquivos temporários")
            
            # CKDEV-NOTE: Log das configurações de limpeza ativas
            cleanup_features = []
            if getattr(config, 'CLEANUP_CACHE_ENABLED', True):
                cleanup_features.append("cache/sessions")
            if getattr(config, 'CLEANUP_SHARED_OUTPUT_ENABLED', True):
                cleanup_features.append("shared/output")
            
            logger.info(f"Recursos de limpeza habilitados: uploads, output, {', '.join(cleanup_features)}")
            
            with app.app_context():
                cleaned_count = file_service.cleanup_temp_files(
                    max_age_hours=config.CLEANUP_MAX_AGE_HOURS
                )
                
            if cleaned_count > 0:
                logger.info(f"Limpeza concluída: {cleaned_count} arquivos removidos de todas as pastas")
            else:
                logger.info("Limpeza concluída: nenhum arquivo removido")
                
        except PermissionError as e:
            logger.error(f"Erro de permissão durante limpeza automática: {e}")
        except OSError as e:
            logger.error(f"Erro do sistema durante limpeza automática: {e}")
        except Exception as e:
            logger.error(f"Erro inesperado durante limpeza automática: {e}")
    
    scheduler = BackgroundScheduler()
    
    scheduler.add_job(
        func=cleanup_temp_files,
        trigger=CronTrigger(
            hour=config.CLEANUP_HOUR,
            minute=config.CLEANUP_MINUTE
        ),
        id='cleanup_temp_files',
        name='Cleanup temporary files (daily) - uploads, cache, shared/output',
        replace_existing=True
    )
    logger.info(f"Limpeza automática configurada para executar diariamente às {config.CLEANUP_HOUR:02d}:{config.CLEANUP_MINUTE:02d}")
    logger.info(f"Configuração de limpeza: máximo {config.CLEANUP_MAX_AGE_HOURS}h para uploads/shared, cache habilitado: {getattr(config, 'CLEANUP_CACHE_ENABLED', True)}")
    
    scheduler.start()
    
    atexit.register(lambda: scheduler.shutdown())


def create_app(config_name: str = None) -> Flask:
    """Application factory"""
    # Get configuration
    config = get_config(config_name)
    
    # Initialize directories
    config.init_app()
    
    # Configure logging (suppress JSON output during startup)
    LoggerManager.configure(config)
    logger = get_app_logger()
    
    # CKDEV-NOTE: Avoid duplicate logs when using reloader
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        StartupLogger.info(f"Starting {config.APP_NAME} v{config.APP_VERSION}")
    
    # Create Flask app
    app = Flask(__name__)
    app.config.from_object(config)
    
    # Configure CORS
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": config.CORS_ORIGINS,
                "methods": config.CORS_METHODS,
                "allow_headers": config.CORS_ALLOW_HEADERS,
                "expose_headers": config.CORS_EXPOSE_HEADERS
            }
        }
    )
    
    # Initialize security middleware
    security_middleware = SecurityMiddleware(app)
    
    # Register error handlers
    register_error_handlers(app)
    # CKDEV-NOTE: Avoid duplicate logs when using reloader
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        StartupLogger.success("Error handlers registered")
    
    # Initialize services
    pdf_service = PDFConversionService(config)
    session_service = SessionService(
        session_dir=config.SESSION_FILE_DIR,
        max_age_hours=72  # CKDEV-NOTE: Increased to 72h to prevent premature session expiration
    )
    file_service = FileService(config)
    
    # Register blueprints (controllers)
    app.register_blueprint(create_health_controller(config, pdf_service))
    app.register_blueprint(create_file_controller(file_service, pdf_service))
    app.register_blueprint(create_document_controller(file_service, session_service, pdf_service))
    app.register_blueprint(create_session_controller(session_service))
    
    # Store services in app context for access from other parts of the app
    app.pdf_service = pdf_service
    app.session_service = session_service
    app.file_service = file_service
    
    # Setup automatic cleanup scheduler
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        setup_cleanup_scheduler(app, file_service, config)
    
    @app.route('/api/process', methods=['POST'])
    def legacy_process_documents():
        """Legacy endpoint that redirects to new documents/process endpoint"""
        from flask import request as flask_request
        from api.controllers.document_controller import create_document_controller
        
        # Get the document controller
        doc_controller = create_document_controller(file_service, session_service, pdf_service)
        
        # Forward the request to the process_documents function
        with app.test_request_context():
            # Copy the request data
            files = flask_request.files.getlist('files')
            template_type = flask_request.form.get('template', 'cessao_credito')
            
            if not files:
                return {"error": {"message": "No files provided"}, "success": False}, 400
            
            # Process documents using the real document controller endpoint
            try:
                # Forward to the actual documents/process endpoint instead of mocking data
                from flask import request as flask_request
                from werkzeug.test import Client
                from werkzeug.wrappers import Response
                
                # Create test client to call the actual endpoint
                with app.test_client() as client:
                    # Prepare form data for the real endpoint
                    data = {
                        'template': template_type
                    }
                    
                    # Add files to the request
                    files_data = {}
                    for i, file in enumerate(files):
                        files_data[f'files'] = (file.stream, file.filename, file.content_type)
                    
                    # Call the real endpoint
                    response = client.post('/api/documents/process', 
                                         data=data, 
                                         files=files_data,
                                         content_type='multipart/form-data')
                    
                    if response.status_code == 200:
                        result = response.get_json()
                        return result
                    else:
                        logger.error(f"Documents processing failed with status {response.status_code}")
                        return {"error": {"message": "Processing failed"}, "success": False}, response.status_code
                
            except Exception as e:
                logger.error(f"Legacy process documents failed: {e}")
                return {"error": {"message": f"Processing failed: {str(e)}"}, "success": False}, 500

    # CKDEV-NOTE: Avoid duplicate logs when using reloader
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        StartupLogger.success("Application initialized successfully")
    
    return app


def create_development_app() -> Flask:
    """Create development application"""
    return create_app('development')


def create_production_app() -> Flask:
    """Create production application"""
    return create_app('production')


# Create application instance
app = create_app()


if __name__ == '__main__':
    """Run application directly"""
    import signal
    import sys
    from api.utils.startup import print_startup_banner, print_shutdown_message
    
    config = get_config()
    
    # CKDEV-NOTE: Setup graceful shutdown handler
    def signal_handler(sig, frame):
        print_shutdown_message()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    suppress_werkzeug_startup()
    
    # CKDEV-NOTE: Only print banner once, avoiding duplication with reloader
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        print_startup_banner(config)
    
    # Run development server
    try:
        app.run(
            host=config.HOST,
            port=config.PORT,
            debug=config.DEBUG,
            use_reloader=config.DEBUG
        )
    except KeyboardInterrupt:
        print_shutdown_message()
        sys.exit(0)