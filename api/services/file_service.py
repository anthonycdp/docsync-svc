import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from werkzeug.datastructures import FileStorage

from ..config import Config
from ..models import FileUpload
from ..exceptions import ValidationError, SecurityError, FileProcessingError
from ..utils.file_utils import FileManager, TemporaryFileManager
from ..utils.logger import get_service_logger, log_file_operation
from ..utils.validators import DataValidator


class FileService:
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = get_service_logger('file')
        self.upload_dir = Path(config.UPLOAD_FOLDER)
        
        # CKDEV-NOTE: Use the correct output directory from config
        # This ensures PDFs are found in the same location where they're generated
        self.output_dir = Path(config.OUTPUT_DIR)
        
        # CKDEV-NOTE: Ensure both directories exist
        FileManager.ensure_directory(self.upload_dir)
        FileManager.ensure_directory(self.output_dir)
        
        # CKDEV-NOTE: No logging during initialization to reduce noise
        # Only log errors when they occur
    
    def upload_files(self, files: List[FileStorage]) -> List[Dict[str, Any]]:
        if not files:
            raise ValidationError("No files provided")
        
        results = []
        uploaded_files = []
        
        try:
            for file in files:
                if file and file.filename:
                    result = self._process_single_file(file)
                    results.append(result)
                    uploaded_files.append(result['file_path'])
            
            if not results:
                raise ValidationError("No valid files found")
            
            # CKDEV-NOTE: No logging for successful operations to reduce noise
            # Only log errors when they occur
            
            return results
            
        except Exception as e:
            self._cleanup_files(uploaded_files)
            raise
    
    def _process_single_file(self, file: FileStorage) -> Dict[str, Any]:
        filename = file.filename
        
        if not filename:
            raise ValidationError("Empty filename")
        
        self._validate_file_security(file, filename)
        
        safe_filename = FileManager.create_unique_filename(self.upload_dir, filename)
        file_path = self.upload_dir / safe_filename
        
        try:
            file.save(str(file_path))
            
            file_info = self._validate_uploaded_file(file_path, filename)
            
            log_file_operation("upload", str(file_path), True, **file_info)
            
            return {
                "filename": safe_filename,
                "original_filename": filename,
                "file_path": str(file_path),
                "content_type": file_info["content_type"],
                "size": file_info["size"],
                "file_type": file_info["file_type"]
            }
            
        except Exception as e:
            if file_path.exists():
                file_path.unlink()
            
            log_file_operation("upload", filename, False, error=str(e))
            raise FileProcessingError(f"Failed to process file {filename}: {e}")
    
    def _validate_file_security(self, file: FileStorage, filename: str) -> None:
        if not FileManager.validate_file_extension(filename):
            raise SecurityError(f"File type not allowed: {filename}")
        
        if hasattr(file, 'content_length') and file.content_length:
            if file.content_length > self.config.MAX_CONTENT_LENGTH:
                raise SecurityError(f"File too large: {file.content_length} bytes")
        
        try:
            FileManager.generate_safe_path(self.upload_dir, filename)
        except Exception as e:
            raise SecurityError(f"Invalid filename: {filename}")
    
    def _validate_uploaded_file(self, file_path: Path, original_filename: str) -> Dict[str, Any]:
        if not file_path.exists():
            raise FileProcessingError(f"File was not saved: {original_filename}")
        
        file_size = file_path.stat().st_size
        if file_size == 0:
            file_path.unlink()
            raise FileProcessingError(f"Uploaded file is empty: {original_filename}")
        
        content_type = FileManager.determine_content_type(original_filename)
        file_type = FileManager.get_file_type(original_filename)
        
        return {
            "content_type": content_type,
            "size": file_size,
            "file_type": file_type
        }
    
    def _cleanup_files(self, file_paths: List[str]) -> None:
        for file_path in file_paths:
            try:
                Path(file_path).unlink()
                # CKDEV-NOTE: No logging for cleanup operations to reduce noise
            except Exception as e:
                self.logger.warning(f"Failed to cleanup file {file_path}: {e}")
    
    def get_file(self, filename: str, directory: str = "upload") -> Path:
        # CKDEV-NOTE: Use the correct directory based on the request
        if directory in ["upload", "uploads"]:
            base_dir = self.upload_dir
        elif directory == "output":
            base_dir = self.output_dir
        else:
            raise SecurityError(f"Invalid directory: {directory}")
        
        # CKDEV-NOTE: Security check for path traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            raise SecurityError(f"Invalid filename: {filename}")
        
        file_path = base_dir / filename
        
        # CKDEV-NOTE: No logging for successful file access to reduce noise
        # Only log errors when they occur
        
        if not file_path.exists():
            if base_dir.exists():
                self.logger.warning(f"File not found: {filename} in {directory}")
            else:
                self.logger.error(f"Base directory does not exist: {base_dir}")
            
            from ..exceptions import FileNotFoundError
            raise FileNotFoundError(filename)
        
        # CKDEV-NOTE: Security check to prevent path traversal
        if not str(file_path.resolve()).startswith(str(base_dir.resolve())):
            raise SecurityError(f"Path traversal attempt: {filename}")
        
        return file_path
    
    def delete_file(self, filename: str, directory: str = "upload") -> bool:
        try:
            file_path = self.get_file(filename, directory)
            file_path.unlink()
            
            log_file_operation("delete", str(file_path), True)
            # CKDEV-NOTE: No logging for successful delete operations to reduce noise
            return True
            
        except Exception as e:
            log_file_operation("delete", filename, False, error=str(e))
            return False
    
    def cleanup_temp_files(self, max_age_hours: int = 24) -> int:
        cleaned_count = 0
        
        # CKDEV-NOTE: Limpeza da pasta uploads (arquivos temporários de upload)
        cleaned_count += FileManager.clean_temporary_files(self.upload_dir, max_age_hours)
        
        # CKDEV-NOTE: Limpeza da pasta output (mesmo tempo padrão de 24h)
        cleaned_count += FileManager.clean_temporary_files(self.output_dir, max_age_hours)
        
        # CKDEV-NOTE: Limpeza das pastas de cache e sessões (se habilitado)
        if getattr(self.config, 'CLEANUP_CACHE_ENABLED', True):
            cleaned_count += self._cleanup_cache_directories(max_age_hours)
        
        # CKDEV-NOTE: Limpeza da pasta shared/output específica do projeto (se habilitado)
        if getattr(self.config, 'CLEANUP_SHARED_OUTPUT_ENABLED', True):
            cleaned_count += self._cleanup_shared_output_directory(max_age_hours)
        
        # CKDEV-NOTE: No logging for successful cleanup operations to reduce noise
        # Only log errors when they occur
        
        return cleaned_count
    
    def _cleanup_cache_directories(self, max_age_hours: int = 24) -> int:
        """Clean cache directories including sessions and logs"""
        cleaned_count = 0
        
        try:
            # CKDEV-NOTE: Limpeza da pasta de sessões
            session_dir = Path(self.config.SESSION_FILE_DIR)
            if session_dir.exists():
                cleaned_count += FileManager.clean_temporary_files(session_dir, max_age_hours)
                # CKDEV-NOTE: No logging for successful cleanup operations
            
            # CKDEV-NOTE: Limpeza da pasta de logs (apenas arquivos .log antigos)
            log_dir = Path(self.config.LOG_DIR)
            if log_dir.exists():
                # CKDEV-NOTE: Logs mantidos por mais tempo (configurável via CLEANUP_LOG_RETENTION_MULTIPLIER)
                log_retention_multiplier = getattr(self.config, 'CLEANUP_LOG_RETENTION_MULTIPLIER', 3)
                cleaned_count += self._cleanup_log_files(log_dir, max_age_hours * log_retention_multiplier)
                # CKDEV-NOTE: No logging for successful cleanup operations
                
        except Exception as e:
            self.logger.error(f"Error cleaning cache directories: {e}")
            
        return cleaned_count
    
    def _cleanup_shared_output_directory(self, max_age_hours: int = 24) -> int:
        """Clean the specific shared/output directory"""
        cleaned_count = 0
        
        try:
            # CKDEV-NOTE: Caminho configurável para a pasta shared/output específica do projeto
            shared_output_path = getattr(self.config, 'CLEANUP_SHARED_OUTPUT_PATH', 
                                       Path("D:/QA/Development/Portfolio/doc-sync/backend/shared/output"))
            
            if shared_output_path.exists() and shared_output_path.is_dir():
                cleaned_count += FileManager.clean_temporary_files(shared_output_path, max_age_hours)
                # CKDEV-NOTE: No logging for successful cleanup operations
            else:
                self.logger.warning(f"Shared output directory not found or not accessible: {shared_output_path}")
                
        except Exception as e:
            self.logger.error(f"Error cleaning shared output directory: {e}")
            
        return cleaned_count
    
    def _cleanup_log_files(self, log_dir: Path, max_age_hours: int) -> int:
        """Clean old log files specifically"""
        cleaned_count = 0
        
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            for log_file in log_dir.glob("*.log*"):
                if log_file.is_file():
                    file_age = current_time - log_file.stat().st_mtime
                    if file_age > max_age_seconds:
                        log_file.unlink()
                        cleaned_count += 1
                        # CKDEV-NOTE: No logging for successful log file cleanup
                        
        except Exception as e:
            self.logger.error(f"Error cleaning log files: {e}")
            
        return cleaned_count
    
    def get_file_info(self, filename: str, directory: str = "upload") -> Dict[str, Any]:
        file_path = self.get_file(filename, directory)
        info = FileManager.get_file_info(file_path)
        
        return {
            "filename": filename,
            "full_path": str(file_path),
            "size": info["size"],
            "size_human": self._format_file_size(info["size"]),
            "created": info["created"],
            "modified": info["modified"],
            "extension": info["extension"],
            "file_type": self._determine_file_type(file_path)
        }
    
    def list_files(self, directory: str = "upload", pattern: str = "*") -> List[Dict[str, Any]]:
        base_dir = self.upload_dir if directory in ["upload", "uploads"] else self.output_dir
        
        files = []
        for file_path in base_dir.glob(pattern):
            if file_path.is_file():
                try:
                    info = self.get_file_info(file_path.name, directory)
                    files.append(info)
                except Exception as e:
                    self.logger.warning(f"Error getting info for {file_path}: {e}")
        
        return sorted(files, key=lambda x: x["modified"], reverse=True)
    
    def _format_file_size(self, size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    
    def create_temporary_file(self, suffix: str = None, prefix: str = "docsync_") -> TemporaryFileManager:
        return TemporaryFileManager(
            suffix=suffix,
            prefix=prefix,
            dir=str(self.upload_dir)
        )