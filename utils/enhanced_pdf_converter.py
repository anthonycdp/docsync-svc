import os
import sys
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Optional, List
import logging

class EnhancedPDFConverter:
    """
    Enhanced DOCX to PDF converter with better formatting preservation.
    Prioritizes high-quality conversion methods.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.temp_dir = tempfile.gettempdir()
    
    def convert_docx_to_pdf(self, docx_path: str, pdf_path: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """
        Convert DOCX to PDF using the best available method.
        
        Priority order:
        1. LibreOffice headless (best formatting preservation)
        2. docx2pdf (Windows only, good quality)
        3. mammoth + wkhtmltopdf (HTML intermediate, good for complex docs)
        4. ReportLab (fallback, basic formatting)
        
        Args:
            docx_path: Path to DOCX file
            pdf_path: Output PDF path (optional)
            
        Returns:
            Tuple[bool, str, Optional[str]]: (success, message, pdf_path)
        """
        if not os.path.exists(docx_path):
            return False, f"DOCX file not found: {docx_path}", None
        
        if pdf_path is None:
            pdf_path = str(Path(docx_path).with_suffix('.pdf'))
        
        # Ensure output directory exists
        output_dir = os.path.dirname(pdf_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # Try conversion methods in priority order
        methods = [
            self._convert_with_libreoffice,
            self._convert_with_docx2pdf,
            self._convert_with_mammoth_wkhtmltopdf,
            self._convert_with_pandoc,
        ]
        
        for method in methods:
            try:
                self.logger.info(f"Trying conversion method: {method.__name__}")
                success, message, result_path = method(docx_path, pdf_path)
                
                if success and result_path and os.path.exists(result_path):
                    # Verify PDF is valid and not empty
                    if os.path.getsize(result_path) > 1024:  # At least 1KB
                        self.logger.info(f"Successfully converted using {method.__name__}: {result_path}")
                        return True, f"PDF generated successfully using {method.__name__}", result_path
                    else:
                        self.logger.warning(f"{method.__name__} generated empty or tiny PDF")
                        continue
                else:
                    self.logger.warning(f"{method.__name__} failed: {message}")
                    continue
                    
            except Exception as e:
                self.logger.error(f"{method.__name__} error: {e}")
                continue
        
        return False, "All PDF conversion methods failed", None
    
    def _convert_with_libreoffice(self, docx_path: str, pdf_path: str) -> Tuple[bool, str, Optional[str]]:
        """Convert using LibreOffice headless - best quality and formatting preservation."""
        
        # Check if LibreOffice is available
        libreoffice_cmd = None
        for cmd in ['libreoffice', 'soffice', '/usr/bin/libreoffice', '/opt/libreoffice/program/soffice']:
            try:
                result = subprocess.run([cmd, '--version'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    libreoffice_cmd = cmd
                    break
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        if not libreoffice_cmd:
            return False, "LibreOffice not found in system", None
        
        try:
            output_dir = os.path.dirname(pdf_path)
            
            # CKDEV-NOTE: LibreOffice headless conversion with optimized settings
            cmd = [
                libreoffice_cmd,
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', output_dir,
                '--writer',  # Force Writer mode for better DOCX handling
                docx_path
            ]
            
            self.logger.info(f"Running LibreOffice command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=60,
                                  cwd=output_dir)
            
            if result.returncode == 0:
                # LibreOffice creates PDF with same name as DOCX
                expected_pdf = os.path.join(output_dir, 
                                          os.path.splitext(os.path.basename(docx_path))[0] + '.pdf')
                
                if os.path.exists(expected_pdf):
                    # Move to desired location if different
                    if expected_pdf != pdf_path:
                        if os.path.exists(pdf_path):
                            os.remove(pdf_path)
                        os.rename(expected_pdf, pdf_path)
                    
                    file_size = os.path.getsize(pdf_path)
                    if file_size > 1024:
                        return True, f"LibreOffice conversion successful ({file_size} bytes)", pdf_path
                    else:
                        return False, "LibreOffice generated empty PDF", None
                else:
                    return False, f"LibreOffice did not create expected PDF: {expected_pdf}", None
            else:
                error_msg = result.stderr or result.stdout or "Unknown LibreOffice error"
                return False, f"LibreOffice conversion failed: {error_msg}", None
                
        except subprocess.TimeoutExpired:
            return False, "LibreOffice conversion timed out", None
        except Exception as e:
            return False, f"LibreOffice conversion error: {str(e)}", None
    
    def _convert_with_docx2pdf(self, docx_path: str, pdf_path: str) -> Tuple[bool, str, Optional[str]]:
        """Convert using docx2pdf (Windows only, requires MS Office)."""
        
        if platform.system().lower() != 'windows':
            return False, "docx2pdf is Windows-only", None
        
        try:
            from docx2pdf import convert
            
            convert(docx_path, pdf_path)
            
            if os.path.exists(pdf_path):
                file_size = os.path.getsize(pdf_path)
                if file_size > 1024:
                    return True, f"docx2pdf conversion successful ({file_size} bytes)", pdf_path
                else:
                    return False, "docx2pdf generated empty PDF", None
            else:
                return False, "docx2pdf did not create PDF file", None
                
        except ImportError:
            return False, "docx2pdf library not installed", None
        except Exception as e:
            error_str = str(e).lower()
            if "word" in error_str or "office" in error_str or "com" in error_str:
                return False, "Microsoft Word/Office not available for docx2pdf", None
            else:
                return False, f"docx2pdf error: {str(e)}", None
    
    def _convert_with_mammoth_wkhtmltopdf(self, docx_path: str, pdf_path: str) -> Tuple[bool, str, Optional[str]]:
        """Convert via HTML intermediate using mammoth + wkhtmltopdf."""
        
        try:
            import mammoth
            
            # Check if wkhtmltopdf is available
            try:
                result = subprocess.run(['wkhtmltopdf', '--version'], 
                                      capture_output=True, timeout=10)
                if result.returncode != 0:
                    return False, "wkhtmltopdf not found", None
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return False, "wkhtmltopdf not available", None
            
            # Convert DOCX to HTML
            with open(docx_path, "rb") as docx_file:
                result = mammoth.convert_to_html(docx_file)
                html_content = result.value
            
            if not html_content.strip():
                return False, "mammoth produced empty HTML", None
            
            # Create temporary HTML file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, 
                                           encoding='utf-8', dir=self.temp_dir) as temp_html:
                # Add proper HTML structure and CSS for better formatting
                full_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: Arial, Calibri, sans-serif;
            font-size: 11pt;
            line-height: 1.4;
            margin: 2cm;
            color: #000;
        }}
        h1 {{ 
            font-size: 14pt; 
            font-weight: bold; 
            text-align: center;
            margin-bottom: 1em;
        }}
        p {{ 
            margin-bottom: 0.8em; 
            text-align: justify;
        }}
        .signature-area {{
            margin-top: 2em;
            page-break-inside: avoid;
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>
                """
                temp_html.write(full_html)
                temp_html_path = temp_html.name
            
            try:
                # Convert HTML to PDF with proper page settings
                cmd = [
                    'wkhtmltopdf',
                    '--page-size', 'A4',
                    '--margin-top', '2cm',
                    '--margin-bottom', '2cm',
                    '--margin-left', '2cm', 
                    '--margin-right', '2cm',
                    '--encoding', 'UTF-8',
                    '--enable-local-file-access',
                    temp_html_path,
                    pdf_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0 and os.path.exists(pdf_path):
                    file_size = os.path.getsize(pdf_path)
                    if file_size > 1024:
                        return True, f"mammoth+wkhtmltopdf conversion successful ({file_size} bytes)", pdf_path
                    else:
                        return False, "wkhtmltopdf generated empty PDF", None
                else:
                    error_msg = result.stderr or "wkhtmltopdf failed"
                    return False, f"wkhtmltopdf error: {error_msg}", None
                    
            finally:
                # Cleanup temp file
                try:
                    os.unlink(temp_html_path)
                except:
                    pass
            
        except ImportError:
            return False, "mammoth library not installed", None
        except Exception as e:
            return False, f"mammoth+wkhtmltopdf error: {str(e)}", None
    
    def _convert_with_pandoc(self, docx_path: str, pdf_path: str) -> Tuple[bool, str, Optional[str]]:
        """Convert using Pandoc (if available)."""
        
        try:
            # Check if pandoc is available
            result = subprocess.run(['pandoc', '--version'], 
                                  capture_output=True, timeout=10)
            if result.returncode != 0:
                return False, "pandoc not found", None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False, "pandoc not available", None
        
        try:
            cmd = [
                'pandoc',
                docx_path,
                '-o', pdf_path,
                '--pdf-engine=wkhtmltopdf',
                '--variable', 'geometry:margin=2cm',
                '--variable', 'fontsize=11pt',
                '--variable', 'linestretch=1.4'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            
            if result.returncode == 0 and os.path.exists(pdf_path):
                file_size = os.path.getsize(pdf_path)
                if file_size > 1024:
                    return True, f"pandoc conversion successful ({file_size} bytes)", pdf_path
                else:
                    return False, "pandoc generated empty PDF", None
            else:
                error_msg = result.stderr or "pandoc conversion failed"
                return False, f"pandoc error: {error_msg}", None
                
        except subprocess.TimeoutExpired:
            return False, "pandoc conversion timed out", None
        except Exception as e:
            return False, f"pandoc error: {str(e)}", None


def convert_docx_to_pdf_enhanced(docx_path: str, pdf_path: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """
    Enhanced DOCX to PDF conversion function.
    
    Args:
        docx_path: Path to DOCX file
        pdf_path: Output PDF path (optional)
        
    Returns:
        Tuple[bool, str, Optional[str]]: (success, message, pdf_path)
    """
    converter = EnhancedPDFConverter()
    return converter.convert_docx_to_pdf(docx_path, pdf_path)