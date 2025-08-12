import os
from pathlib import Path
from typing import List, Optional
from datetime import timedelta


class Config:
    
    APP_NAME: str = "Doc Sync API"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    TESTING: bool = False
    
    HOST: str = os.getenv("API_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("API_PORT", "5000"))
    
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES: timedelta = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES: timedelta = timedelta(days=30)
    
    CORS_ORIGINS: List[str] = [
        "https://doc-sync-original.netlify.app/*"
    ]
    CORS_METHODS: List[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: List[str] = ["Content-Type", "Authorization"]
    CORS_EXPOSE_HEADERS: List[str] = ["Content-Disposition", "Content-Length"]
    
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024
    UPLOAD_FOLDER: Path = Path(os.getenv("UPLOAD_FOLDER", Path.home() / "tmp" / "doc-sync" / "uploads"))
    ALLOWED_EXTENSIONS: set = {"pdf", "jpg", "jpeg", "png"}
    
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    # CKDEV-NOTE: Updated to use absolute path for shared directory
    SHARED_DIR: Path = BASE_DIR / "shared"
    TEMPLATES_DIR: Path = SHARED_DIR / "templates"
    OUTPUT_DIR: Path = SHARED_DIR / "output"
    
    SESSION_TYPE: str = "filesystem"
    SESSION_FILE_DIR: Path = Path.home() / "tmp" / "doc-sync" / "sessions"
    SESSION_PERMANENT: bool = False
    SESSION_USE_SIGNER: bool = True
    SESSION_KEY_PREFIX: str = "docsync_"
    SESSION_COOKIE_NAME: str = "docsync_session"
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SAMESITE: str = "Lax"
    
    RATELIMIT_ENABLED: bool = True
    RATELIMIT_STORAGE_URL: str = os.getenv("REDIS_URL", "memory://")
    RATELIMIT_DEFAULT: str = "100 per hour"
    RATELIMIT_HEADERS_ENABLED: bool = True
    
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DIR: Path = Path.home() / "tmp" / "doc-sync" / "logs"
    LOG_FILE: str = "app.log"
    LOG_MAX_BYTES: int = 10485760
    LOG_BACKUP_COUNT: int = 10
    LOG_FORMAT_CONSOLE: Optional[str] = os.getenv("LOG_FORMAT_CONSOLE")
    
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    
    # CKDEV-NOTE: API base URL for generating download URLs
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://127.0.0.1:5000")
    
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: List[str] = ["json"]
    CELERY_TIMEZONE: str = "America/Sao_Paulo"
    CELERY_ENABLE_UTC: bool = True
    
    # CKDEV-NOTE: Use only docx2pdf conversion method for consistency across all templates
    PDF_CONVERSION_TIMEOUT: int = 120
    
    ENABLE_CACHE: bool = True
    CACHE_TYPE: str = "simple"
    CACHE_DEFAULT_TIMEOUT: int = 300
    
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    
    CLEANUP_ENABLED: bool = os.getenv("CLEANUP_ENABLED", "true").lower() == "true"
    CLEANUP_HOUR: int = int(os.getenv("CLEANUP_HOUR", "2"))
    CLEANUP_MINUTE: int = int(os.getenv("CLEANUP_MINUTE", "0"))
    CLEANUP_MAX_AGE_HOURS: int = int(os.getenv("CLEANUP_MAX_AGE_HOURS", "24"))
    CLEANUP_CACHE_ENABLED: bool = os.getenv("CLEANUP_CACHE_ENABLED", "true").lower() == "true"
    CLEANUP_SHARED_OUTPUT_ENABLED: bool = os.getenv("CLEANUP_SHARED_OUTPUT_ENABLED", "true").lower() == "true"
    CLEANUP_SHARED_OUTPUT_PATH: Path = Path(os.getenv("CLEANUP_SHARED_OUTPUT_PATH", BASE_DIR / "shared" / "output"))
    CLEANUP_LOG_RETENTION_MULTIPLIER: int = int(os.getenv("CLEANUP_LOG_RETENTION_MULTIPLIER", "3"))
    
    @classmethod
    def init_app(cls):
        cls.UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
        cls.SESSION_FILE_DIR.mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(Config):
    ENV = "Development"
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    LOG_FORMAT_CONSOLE = "%(asctime)s - %(levelname)s - %(message)s"
    SESSION_COOKIE_SECURE = False
    RATELIMIT_ENABLED = False
    CLEANUP_MAX_AGE_HOURS = 1


class TestingConfig(Config):
    ENV = "Testing"
    TESTING = True
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    UPLOAD_FOLDER = Path("/tmp/test_uploads")
    OUTPUT_DIR = Path("/tmp/test_output")
    SESSION_FILE_DIR = Path("/tmp/test_sessions")


class ProductionConfig(Config):
    ENV = "Production"
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    
    SECRET_KEY = os.environ.get("SECRET_KEY", Config.SECRET_KEY)
    
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "").split(",") if os.environ.get("CORS_ORIGINS") else []
    
    RATELIMIT_DEFAULT = "50 per hour"
    
    LOG_LEVEL = "WARNING"


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}


def get_config(env: Optional[str] = None) -> Config:
    if env is None:
        env = os.getenv("FLASK_ENV", "development")
    return config.get(env, config["default"])