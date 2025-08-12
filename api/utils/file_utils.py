import os
import re
import shutil
import tempfile
import hashlib
import time
from pathlib import Path
from typing import Optional, List, Tuple, Union
from werkzeug.utils import secure_filename

from ..exceptions import SecurityError, FileNotFoundError as CustomFileNotFoundError


class FileManager:
    
    ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.docx'}
    MAX_FILENAME_LENGTH = 200
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        if not filename:
            raise ValueError("Filename cannot be empty")
        
        safe_name = secure_filename(filename)
        
        if not safe_name:
            safe_name = "upload"
        
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', safe_name)
        safe_name = re.sub(r'[^\w\s\-_.]', '', safe_name)
        safe_name = re.sub(r'[-\s]+', '-', safe_name)
        
        if len(safe_name) > FileManager.MAX_FILENAME_LENGTH:
            name, ext = os.path.splitext(safe_name)
            max_name_len = FileManager.MAX_FILENAME_LENGTH - len(ext)
            safe_name = name[:max_name_len] + ext
        
        safe_name = safe_name.strip('.-_ ')
        
        if not safe_name:
            safe_name = "upload"
        
        return safe_name
    
    @staticmethod
    def validate_file_extension(filename: str) -> bool:
        if not filename:
            return False
        
        ext = os.path.splitext(filename.lower())[1]
        return ext in FileManager.ALLOWED_EXTENSIONS
    
    @staticmethod
    def generate_safe_path(base_dir: Union[str, Path], filename: str) -> Path:
        base_path = Path(base_dir).resolve()
        safe_filename = FileManager.sanitize_filename(filename)
        
        target_path = (base_path / safe_filename).resolve()
        
        if not str(target_path).startswith(str(base_path)):
            raise SecurityError(f"Path traversal attempt detected: {filename}")
        
        return target_path
    
    @staticmethod
    def create_unique_filename(directory: Union[str, Path], filename: str) -> str:
        dir_path = Path(directory)
        safe_filename = FileManager.sanitize_filename(filename)
        target_path = dir_path / safe_filename
        
        if not target_path.exists():
            return safe_filename
        
        name, ext = os.path.splitext(safe_filename)
        counter = 1
        
        while target_path.exists():
            new_filename = f"{name}_{counter}{ext}"
            target_path = dir_path / new_filename
            counter += 1
            
            if counter > 9999:
                timestamp = int(time.time() * 1000)
                new_filename = f"{name}_{timestamp}{ext}"
                break
        
        return new_filename
    
    @staticmethod
    def ensure_directory(directory: Union[str, Path]) -> Path:
        dir_path = Path(directory)
        
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise SecurityError(f"Permission denied creating directory: {dir_path}")
        except OSError as e:
            raise SecurityError(f"Error creating directory {dir_path}: {e}")
        
        try:
            test_file = dir_path / f".write_test_{os.getpid()}"
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            raise SecurityError(f"No write permission for directory: {dir_path}")
        except OSError as e:
            raise SecurityError(f"Cannot write to directory {dir_path}: {e}")
        
        return dir_path
    
    @staticmethod
    def calculate_file_hash(file_path: Union[str, Path], algorithm: str = 'md5') -> str:
        hash_obj = hashlib.new(algorithm)
        
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except FileNotFoundError:
            raise CustomFileNotFoundError(str(file_path))
        except OSError as e:
            raise SecurityError(f"Error reading file {file_path}: {e}")
    
    @staticmethod
    def get_file_info(file_path: Union[str, Path]) -> dict:
        path = Path(file_path)
        
        if not path.exists():
            raise CustomFileNotFoundError(str(file_path))
        
        stat = path.stat()
        
        return {
            'name': path.name,
            'size': stat.st_size,
            'created': stat.st_ctime,
            'modified': stat.st_mtime,
            'extension': path.suffix.lower(),
            'is_file': path.is_file(),
            'is_dir': path.is_dir()
        }
    
    @staticmethod
    def clean_temporary_files(directory: Union[str, Path], max_age_hours: int = 24) -> int:
        import time
        
        dir_path = Path(directory)
        if not dir_path.exists():
            return 0
        
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        cleaned_count = 0
        
        for file_path in dir_path.iterdir():
            if file_path.is_file():
                try:
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        file_path.unlink()
                        cleaned_count += 1
                except OSError:
                    continue
        
        return cleaned_count
    
    @staticmethod
    def copy_file_safely(src: Union[str, Path], dst: Union[str, Path]) -> Path:
        src_path = Path(src)
        dst_path = Path(dst)
        
        if not src_path.exists():
            raise CustomFileNotFoundError(str(src_path))
        
        if not src_path.is_file():
            raise ValueError(f"Source is not a file: {src_path}")
        
        FileManager.ensure_directory(dst_path.parent)
        
        try:
            shutil.copy2(src_path, dst_path)
            return dst_path
        except PermissionError:
            raise SecurityError(f"Permission denied copying to: {dst_path}")
        except OSError as e:
            raise SecurityError(f"Error copying file: {e}")
    
    @staticmethod
    def validate_file_content(file_path: Union[str, Path], expected_type: str = None) -> bool:
        import magic
        
        path = Path(file_path)
        if not path.exists():
            return False
        
        try:
            mime_type = magic.from_file(str(path), mime=True)
            
            if expected_type == 'pdf':
                return mime_type == 'application/pdf'
            elif expected_type == 'image':
                return mime_type.startswith('image/')
            elif expected_type == 'docx':
                return mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            
            return True
        except:
            ext = path.suffix.lower()
            if expected_type == 'pdf':
                return ext == '.pdf'
            elif expected_type == 'image':
                return ext in {'.jpg', '.jpeg', '.png'}
            elif expected_type == 'docx':
                return ext == '.docx'
            
            return ext in FileManager.ALLOWED_EXTENSIONS


class TemporaryFileManager:
    
    def __init__(self, suffix: str = None, prefix: str = "docsync_", dir: str = None):
        self.suffix = suffix
        self.prefix = prefix
        self.dir = dir
        self.temp_file = None
        self.file_path = None
    
    def __enter__(self) -> Path:
        self.temp_file = tempfile.NamedTemporaryFile(
            suffix=self.suffix,
            prefix=self.prefix,
            dir=self.dir,
            delete=False
        )
        self.file_path = Path(self.temp_file.name)
        self.temp_file.close()
        return self.file_path
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file_path and self.file_path.exists():
            try:
                self.file_path.unlink()
            except OSError:
                pass


class BulkFileManager:
    
    @staticmethod
    def process_multiple_files(
        file_paths: List[Union[str, Path]], 
        processor_func,
        max_workers: int = 4
    ) -> List[Tuple[Path, bool, str]]:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {
                executor.submit(processor_func, path): path 
                for path in file_paths
            }
            
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    result = future.result()
                    results.append((path, True, str(result)))
                except Exception as e:
                    results.append((path, False, str(e)))
        
        return results