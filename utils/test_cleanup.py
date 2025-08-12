import os, tempfile, contextlib
from pathlib import Path
from typing import List, Generator, Callable

TEMP_FILE_EXTENSIONS = {'.pdf', '.docx', '.json', '.txt', '.log', '.csv', '.png', '.jpg', '.tmp'}

class TestFileManager:
    def __init__(self):
        self.created_files: List[Path] = []
        self.keep_files = os.getenv('KEEP_TEST_FILES', '0') == '1'
        self.keep_on_failure = os.getenv('KEEP_ON_FAILURE', '1') == '1'
    
    def create_temp_file(self, suffix: str = "", content: str = "", content_bytes: bytes = None) -> Path:
        temp_file = Path(tempfile.mktemp(suffix=suffix))
        temp_file.write_bytes(content_bytes) if content_bytes else temp_file.write_text(content, encoding='utf-8') if content else None
        self.created_files.append(temp_file)
        return temp_file
    
    def cleanup_files(self, test_passed: bool = True) -> None:
        should_cleanup = not self.keep_files and (test_passed or not self.keep_on_failure)
        if should_cleanup:
            for file_path in self.created_files:
                try:
                    file_path.exists() and file_path.unlink()
                except OSError:
                    pass
        self.created_files.clear()

@contextlib.contextmanager
def temp_test_files() -> Generator[Callable[[str, str, bytes], Path], None, None]:
    created_files: List[Path] = []
    def create_file(suffix: str = "", content: str = "", content_bytes: bytes = None) -> Path:
        temp_file = Path(tempfile.mktemp(suffix=suffix))
        temp_file.write_bytes(content_bytes) if content_bytes else temp_file.write_text(content, encoding='utf-8') if content else None
        created_files.append(temp_file)
        return temp_file
    try:
        yield create_file
    finally:
        for file_path in created_files:
            try:
                file_path.exists() and file_path.unlink()
            except OSError:
                pass

def cleanup_test_files(*file_paths: Path) -> None:
    for file_path in file_paths:
        try:
            file_path.exists() and file_path.unlink()
        except OSError:
            pass

def verify_no_temp_files_remain(base_dir: Path = None) -> bool:
    base_dir = base_dir or Path.cwd()
    remaining_files = [f for ext in TEMP_FILE_EXTENSIONS for f in base_dir.glob(f"*{ext}") if any(marker in f.name.lower() for marker in ['test_', 'temp_', 'tmp_'])]
    return len(remaining_files) == 0

def create_pytest_fixture():
    manager = TestFileManager()
    def fixture_function():
        yield manager
        manager.cleanup_files(test_passed=True)
    return fixture_function

def clean_all_temp_files(base_dir: Path = None, dry_run: bool = False) -> int:
    base_dir = base_dir or Path.cwd()
    temp_files = [f for ext in TEMP_FILE_EXTENSIONS for f in base_dir.glob(f"**/*{ext}") if any(marker in f.name.lower() for marker in ['test_', 'temp_', 'tmp_'])]
    if not dry_run:
        for file_path in temp_files:
            try:
                file_path.exists() and file_path.unlink()
            except OSError:
                pass
    return len(temp_files)

if __name__ == "__main__":
    import sys
    clean_all_temp_files(dry_run=len(sys.argv) > 1 and sys.argv[1] == "--dry-run")