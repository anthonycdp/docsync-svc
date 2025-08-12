import os
import sys
from pathlib import Path
from typing import Tuple, Optional

try:
    from docx2pdf import convert
except ImportError:
    convert = None

try:
    from ..utils.logging_config import LoggerMixin
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from utils.logging_config import LoggerMixin


class PDFConverter(LoggerMixin):
    """Conversor de DOCX para PDF com tratamento robusto de erros"""
    
    def __init__(self):
        super().__init__()
        self._validate_dependencies()
    
    def _validate_dependencies(self):
        if convert is None:
            raise ImportError("docx2pdf library not found. Install with: pip install docx2pdf")
    
    def convert_to_pdf(self, docx_path: str, pdf_path: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """
        Converter arquivo DOCX para PDF
        
        Args:
            docx_path: Caminho para o arquivo .docx
            pdf_path: Caminho de saída para o PDF (opcional)
        
        Returns:
            Tuple[bool, str, Optional[str]]: (sucesso, mensagem, caminho_do_pdf)
        """
        try:
            if not os.path.exists(docx_path):
                return False, f"Arquivo DOCX não encontrado: {docx_path}", None
            
            if not docx_path.lower().endswith('.docx'):
                return False, f"Arquivo deve ter extensão .docx: {docx_path}", None
            
            if pdf_path is None:
                pdf_path = self._generate_pdf_path(docx_path)
            
            output_dir = os.path.dirname(pdf_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            self.logger.info(f"Converting {docx_path} to {pdf_path}")
            
            try:
                convert(docx_path, pdf_path)
                
                if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                    self.logger.info(f"PDF created successfully: {pdf_path}")
                    return True, f"PDF gerado com sucesso: {os.path.basename(pdf_path)}", pdf_path
                else:
                    return False, "PDF foi criado mas parece estar vazio ou corrompido", None
                    
            except Exception as convert_error:
                error_str = str(convert_error).lower()
                if "word" in error_str or "office" in error_str or "com" in error_str:
                    return False, f"Erro de conversão: Microsoft Word não está disponível ou não pode ser acessado. Erro: {convert_error}", None
                elif "permission" in error_str or "access" in error_str:
                    return False, f"Erro de permissão: Verifique se o arquivo não está aberto em outro programa. Erro: {convert_error}", None
                else:
                    return False, f"Erro na conversão para PDF: {convert_error}", None
        
        except Exception as e:
            error_msg = f"Erro na conversão para PDF: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg, None
    
    def _generate_pdf_path(self, docx_path: str) -> str:
        docx_file = Path(docx_path)
        pdf_path = docx_file.with_suffix('.pdf')
        return str(pdf_path)
    
    @staticmethod
    def is_conversion_available() -> bool:
        return convert is not None


def convert_docx_to_pdf(docx_path: str, pdf_path: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """
    Função conveniente para conversão DOCX -> PDF
    
    Args:
        docx_path: Caminho para o arquivo .docx
        pdf_path: Caminho de saída para o PDF (opcional)
    
    Returns:
        Tuple[bool, str, Optional[str]]: (sucesso, mensagem, caminho_do_pdf)
    """
    converter = PDFConverter()
    return converter.convert_to_pdf(docx_path, pdf_path)