import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class Config:
    # CKDEV-NOTE: Updated to use shared/output directory instead of local output
    TEMPLATES_DIR: Path = Path("shared/templates")
    OUTPUT_DIR: Path = Path("shared/output")
    ASSETS_DIR: Path = Path("shared/assets")
    LOGS_DIR: Path = Path("logs")
    
    MAX_PDF_SIZE_MB: int = 50
    PDF_TIMEOUT_SECONDS: int = 30
    OCR_LANGUAGE: str = "por"
    OCR_TIMEOUT_SECONDS: int = 60
    
    LOG_LEVEL: str = "ERROR"  # CKDEV-NOTE: Changed from INFO to ERROR for critical logs only
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_MAX_BYTES: int = 10_000_000
    LOG_BACKUP_COUNT: int = 5
    WINDOW_TITLE: str = "Document Generator"
    WINDOW_MIN_WIDTH: int = 800
    WINDOW_MIN_HEIGHT: int = 600
    REQUIRED_TEMPLATES: List[str] = None
    
    def __post_init__(self):
        if self.REQUIRED_TEMPLATES is None:
            templates_env = os.getenv('TERM_GEN_REQUIRED_TEMPLATES', '')
            if templates_env:
                self.REQUIRED_TEMPLATES = [t.strip() for t in templates_env.split(',') if t.strip()]
            else:
                self.REQUIRED_TEMPLATES = []
    
    @classmethod
    def from_env(cls) -> 'Config':
        return cls(
            MAX_PDF_SIZE_MB=int(os.getenv('TERM_GEN_MAX_PDF_SIZE_MB', '50')),
            PDF_TIMEOUT_SECONDS=int(os.getenv('TERM_GEN_PDF_TIMEOUT', '30')),
            OCR_LANGUAGE=os.getenv('TERM_GEN_OCR_LANGUAGE', 'por'),
            OCR_TIMEOUT_SECONDS=int(os.getenv('TERM_GEN_OCR_TIMEOUT', '60')),
            LOG_LEVEL=os.getenv('TERM_GEN_LOG_LEVEL', 'INFO'),
            WINDOW_TITLE=os.getenv('TERM_GEN_WINDOW_TITLE', 'Document Generator'))
    
    def get_templates_path(self, base_dir: Optional[Path] = None) -> Path:
        return base_dir / self.TEMPLATES_DIR if base_dir else self.TEMPLATES_DIR
    
    def get_output_path(self, base_dir: Optional[Path] = None) -> Path:
        return base_dir / self.OUTPUT_DIR if base_dir else self.OUTPUT_DIR
    
    def validate_paths(self, base_dir: Path) -> List[str]:
        errors = []
        templates_path = self.get_templates_path(base_dir)
        
        if not templates_path.exists():
            errors.append(f"Diretório de templates não encontrado: {templates_path}")
        elif self.REQUIRED_TEMPLATES:
            for template in self.REQUIRED_TEMPLATES:
                template_path = templates_path / template
                if not template_path.exists():
                    errors.append(f"Template obrigatório não encontrado: {template}")
        
        return errors

config = Config.from_env()